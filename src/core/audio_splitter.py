#!/usr/bin/env python3

import os
import numpy as np
from pydub import AudioSegment
import click
import csv
import json
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing
from datetime import datetime

import sys
from pathlib import Path

# Add the parent directory to sys.path to allow importing from sibling modules
src_dir = str(Path(__file__).resolve().parent.parent)
if src_dir not in sys.path:
    sys.path.append(src_dir)

from utils.constants import BASE_DATA_FOLDER

def detect_silence_ranges(audio_segment, silence_thresh=-35, min_silence_len=700):
    """Detect silence ranges in the audio segment."""
    silence_ranges = []
    current_silence_start = None
    for i in range(len(audio_segment)):
        if audio_segment[i].dBFS < silence_thresh:
            if current_silence_start is None:
                current_silence_start = i
        else:
            if current_silence_start is not None:
                if i - current_silence_start >= min_silence_len:
                    silence_ranges.append((current_silence_start, i))
                current_silence_start = None
    return silence_ranges

def adjust_chunk_boundaries(chunk, crossfade, min_duration):
    """Adjust chunk boundaries to avoid cutting words."""
    return chunk, False  # Simplified for this implementation

def contains_speech(chunk):
    """Determine if a chunk contains speech based on energy levels."""
    # Simple energy threshold for speech detection
    # This can be improved with more sophisticated analysis
    return chunk.dBFS > -30

def find_word_boundaries(audio_segment, threshold=-35, window_ms=20):
    """Find potential word boundaries in the audio segment."""
    boundaries = []
    window_size = int(audio_segment.frame_rate * window_ms / 1000)
    samples = np.array(audio_segment.get_array_of_samples())
    
    for i in range(0, len(samples) - window_size, window_size):
        window = samples[i:i + window_size]
        rms = np.sqrt(np.mean(window ** 2))
        if rms < threshold:
            boundaries.append(i)
    return boundaries


def adjust_split_points_for_words(chunks, audio):
    """Adjust split points to ensure words are not cut off."""
    adjusted_chunks = []
    for chunk in chunks:
        word_boundaries = find_word_boundaries(chunk)
        if word_boundaries:
            # Adjust to the last boundary within the chunk
            last_boundary = word_boundaries[-1]
            adjusted_chunk = chunk[:last_boundary]
            adjusted_chunks.append(adjusted_chunk)
        else:
            adjusted_chunks.append(chunk)
    return adjusted_chunks


def get_audio_stats(input_file, start_time, duration):
    """Get audio statistics for a segment using FFmpeg."""
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-ss', str(start_time),
        '-t', str(duration),
        '-af', 'volumedetect,astats',
        '-f', 'null',
        '-'
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stderr
        
        # Extract mean volume
        mean_volume = None
        rms_match = re.search(r'mean_volume: ([-\d.]+) dB', output)
        if rms_match:
            mean_volume = float(rms_match.group(1))
        
        return mean_volume
    except Exception as e:
        print(f"Error getting audio stats: {e}")
        return None

def is_segment_valid(input_file, start_time, duration, min_mean_volume=-35):
    """Check if an audio segment has good quality (not just background noise)."""
    mean_volume = get_audio_stats(input_file, start_time, duration)
    
    if mean_volume is None:
        return True  # If we can't get stats, assume it's valid
    
    # Check if the segment's volume is above our threshold
    return mean_volume > min_mean_volume

def detect_silence_ffmpeg(input_file, silence_thresh=-35, min_silence_len=700):
    """Detect silence using FFmpeg's silencedetect filter."""
    if not os.path.exists(input_file):
        raise RuntimeError(f"Input file not found: {input_file}")
        
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-af', f'silencedetect=noise={silence_thresh}dB:d={min_silence_len/1000}',
        '-f', 'null',
        '-'
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")
            
        output = result.stderr
        if not output:
            raise RuntimeError("No output from FFmpeg silencedetect")
            
        silence_starts = []
        silence_ends = []
        
        for line in output.splitlines():
            try:
                if 'silence_start:' in line:
                    match = re.search(r'silence_start:\s*([\d.]+)', line)
                    if match:
                        time = float(match.group(1))
                        silence_starts.append(time)
                elif 'silence_end:' in line:
                    match = re.search(r'silence_end:\s*([\d.]+)', line)
                    if match:
                        time = float(match.group(1))
                        silence_ends.append(time)
            except (ValueError, AttributeError) as e:
                print(f"Warning: Could not parse line: {line}")
                continue
        
        if not silence_starts or not silence_ends:
            print("Warning: No silence points detected. Using default split points.")
            # Get audio duration
            duration_cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                input_file
            ]
            duration_result = subprocess.run(duration_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if duration_result.returncode == 0:
                duration = float(duration_result.stdout.strip())
                # Create artificial split points every 10 seconds
                split_interval = 10
                silence_starts = list(range(0, int(duration), split_interval))[1:]
                silence_ends = silence_starts
            else:
                raise RuntimeError(f"Could not get audio duration: {duration_result.stderr}")
        
        # Ensure ends list is same length as starts list
        if len(silence_ends) < len(silence_starts):
            silence_ends.extend([silence_ends[-1]] * (len(silence_starts) - len(silence_ends)))
        elif len(silence_starts) < len(silence_ends):
            silence_starts.extend([silence_starts[-1]] * (len(silence_ends) - len(silence_starts)))
        
        silence_points = list(zip(silence_starts, silence_ends))
        print(f"Detected {len(silence_points)} silence points")
        return silence_points
    
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg error: {e.stderr}")
    except Exception as e:
        raise RuntimeError(f"Error detecting silence: {str(e)}")

def export_segment(args):
    """Export a single audio segment using FFmpeg."""
    input_file, start, end, output_path, min_silence_len = args
    
    try:
        # Add padding at the end based on half of min_silence_len
        padding_duration = min_silence_len / 2000  # Convert from ms to seconds
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files
            '-ss', str(start),  # Start time
            '-i', input_file,
            '-t', str(end - start + padding_duration),  # Duration plus padding
            '-c:a', 'libvorbis',  # Use Vorbis codec for better quality
            '-q:a', '4',  # Quality setting (0-10, 4 is good quality)
            '-avoid_negative_ts', '1',  # Shift timestamps to positive values
            output_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            return False, output_path, f"Error: {result.stderr.decode()}"
        return True, output_path, end - start
    except Exception as e:
        return False, output_path, str(e)

def split_audio_ffmpeg(input_file, output_dir, base_filename, min_duration=2, max_duration=15, silence_thresh=-35, min_silence_len=700):
    """Split audio file using FFmpeg based on silence detection with parallel processing."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare CSV file and silence points directory
    csv_file_path = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, f'{base_filename}_transcripts.csv')
    silence_points_dir = os.path.join(BASE_DATA_FOLDER, 'silence_points')
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    os.makedirs(silence_points_dir, exist_ok=True)
    
    # Detect silence points
    print("Detecting silence points...")
    # First try with stricter threshold for clear silence
    print(f"First pass: Detecting clear silence points with threshold {silence_thresh}dB...")
    silence_ranges = detect_silence_ffmpeg(input_file, silence_thresh, min_silence_len)
    
    if not silence_ranges or len(silence_ranges) < 5:  # If we found very few silence points
        print("Few silence points found, analyzing audio dynamics...")
        # Try progressively less strict thresholds to find natural pauses
        thresholds = [-40, -35, -32]
        min_silence_lens = [500, 400, 300]  # Adjust silence length as we get less strict
        
        for thresh, silence_len in zip(thresholds, min_silence_lens):
            print(f"Attempting with threshold {thresh}dB and minimum silence {silence_len}ms...")
            silence_ranges = detect_silence_ffmpeg(input_file, thresh, silence_len)
            if silence_ranges and len(silence_ranges) >= 5:
                print(f"Found {len(silence_ranges)} potential pause points")
                break
            
        if not silence_ranges:
            # Last resort: look for any significant drops in volume
            print("Looking for relative volume drops...")
            silence_ranges = detect_silence_ffmpeg(input_file, -8, 200)
        if not silence_ranges:
            raise ValueError("No silence points detected. Try adjusting silence threshold or minimum silence length.")
    
    # Get total duration
    duration_cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        input_file
    ]
    result = subprocess.run(duration_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Error getting duration: {result.stderr}")
    total_duration = float(result.stdout)
    
    # Create segments based on silence points, excluding silence parts
    segments = []
    valid_segments = []
    
    # Process segments between silence points
    print(f"Processing {len(silence_ranges)} silence ranges...")
    
    # Handle the first segment (from start to first silence)
    potential_segments = []
    if silence_ranges:
        first_silence_start = silence_ranges[0][0]
        if first_silence_start > 0:  # Only add if there's content before first silence
            potential_segments.append((0, first_silence_start))
    
    # Process segments between silence points
    for i in range(len(silence_ranges) - 1):  # Stop before the last silence range
        silence_start, silence_end = silence_ranges[i]
        next_silence_start = silence_ranges[i + 1][0]
        potential_segments.append((silence_end, next_silence_start))
    
    # Process all potential segments
    current_segment_start = None
    current_duration = 0
    
    for i, (start, end) in enumerate(potential_segments):
        segment_duration = end - start
        print(f"Checking segment {i}: {start:.2f}s to {end:.2f}s (duration: {segment_duration:.2f}s)")
        
        # If segment is too long, try to find more silence points with less strict parameters
        if segment_duration > max_duration:
            # First, add any accumulated segments if they meet min_duration
            if current_segment_start is not None and current_duration >= min_duration:
                print(f"Adding accumulated segments: {current_segment_start:.2f}s to {start:.2f}s (duration: {current_duration:.2f}s)")
                segments.append((current_segment_start, start))
                current_segment_start = None
                current_duration = 0
            
            print(f"Analyzing long segment {i} for additional silence points...")
            
            # Create temporary file for the segment
            temp_dir = os.path.join(output_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f'temp_segment_{i}.ogg')
            
            # Extract the segment to analyze
            export_segment((input_file, start, end, temp_file, min_silence_len))
            
            # Try progressively less strict silence detection
            silence_params = [
                (-30, 500),  # Less strict threshold, shorter duration
                (-25, 400),  # Even less strict
                (-20, 300)   # Most lenient
            ]
            
            sub_segments_found = False
            valid_sub_segments = []
            best_sub_segments = []
            best_coverage = 0
            
            for thresh, silence_len in silence_params:
                print(f"  Trying threshold {thresh}dB, duration {silence_len}ms...")
                sub_silence_ranges = detect_silence_ffmpeg(temp_file, silence_thresh=thresh, min_silence_len=silence_len)
                
                if len(sub_silence_ranges) > 1:  # Found some silence points
                    print(f"  Found {len(sub_silence_ranges)} silence points with threshold {thresh}dB")
                    current_sub_segments = []
                    total_duration = 0
                    temp_segments = []
                    
                    # First pass: collect all segments
                    for j in range(len(sub_silence_ranges) - 1):
                        sub_start = start + sub_silence_ranges[j][1]  # Use end of silence
                        sub_end = start + sub_silence_ranges[j + 1][0]  # Use start of next silence
                        sub_duration = sub_end - sub_start
                        temp_segments.append((sub_start, sub_end, sub_duration))
                    
                    # Second pass: try to combine short segments
                    i = 0
                    while i < len(temp_segments):
                        combined_start = temp_segments[i][0]
                        combined_duration = temp_segments[i][2]
                        end_idx = i
                        
                        # Try to combine with next segments if current is too short
                        while (combined_duration < min_duration and 
                               end_idx + 1 < len(temp_segments) and 
                               combined_duration + temp_segments[end_idx + 1][2] <= max_duration):
                            end_idx += 1
                            combined_duration += temp_segments[end_idx][2]
                        
                        combined_end = temp_segments[end_idx][1]
                        print(f"    Checking segment(s) {i}-{end_idx}: {combined_start:.2f}s to {combined_end:.2f}s (duration: {combined_duration:.2f}s)")
                        
                        if min_duration <= combined_duration <= max_duration:
                            print(f"      Valid duration, adding combined segment")
                            current_sub_segments.append((combined_start, combined_end))
                            total_duration += combined_duration
                        elif combined_duration > max_duration:
                            # If single segment is too long, split it
                            num_parts = int(np.ceil(combined_duration / max_duration))
                            part_duration = combined_duration / num_parts
                            for p in range(num_parts):
                                part_start = combined_start + (p * part_duration)
                                part_end = min(combined_start + ((p + 1) * part_duration), combined_end)
                                part_size = part_end - part_start
                                if part_size >= min_duration:
                                    print(f"      Adding split part {p}: {part_start:.2f}s to {part_end:.2f}s (duration: {part_size:.2f}s)")
                                    current_sub_segments.append((part_start, part_end))
                                    total_duration += part_size
                        else:
                            print(f"      Invalid duration (not between {min_duration}s and {max_duration}s)")
                        
                        i = end_idx + 1
                    
                    coverage = total_duration / segment_duration
                    print(f"  Coverage with threshold {thresh}dB: {coverage*100:.1f}% of original segment")
                    
                    if coverage > best_coverage and current_sub_segments:
                        best_coverage = coverage
                        best_sub_segments = current_sub_segments
                        print(f"  New best coverage found: {len(best_sub_segments)} segments")
                    
                    if coverage > 0.8:  # If we have good coverage, use these segments
                        valid_sub_segments = current_sub_segments
                        sub_segments_found = True
                        print(f"  Good coverage found ({coverage*100:.1f}%), using these segments")
                        break
            
            # Use the best segments we found, or fall back to duration-based splitting
            if sub_segments_found:
                print(f"  Using {len(valid_sub_segments)} segments from silence detection")
                segments.extend(valid_sub_segments)
            elif best_sub_segments:  # Use best segments we found even if coverage wasn't ideal
                print(f"  Using best segments found ({len(best_sub_segments)} segments, {best_coverage*100:.1f}% coverage)")
                segments.extend(best_sub_segments)
            else:
                print(f"  No suitable silence points found, falling back to duration-based splitting")
                num_chunks = int(np.ceil(segment_duration / max_duration))
                chunk_duration = segment_duration / num_chunks
                
                for j in range(num_chunks):
                    chunk_start = start + (j * chunk_duration)
                    chunk_end = min(start + ((j + 1) * chunk_duration), end)
                    chunk_size = chunk_end - chunk_start
                    if chunk_size >= min_duration:
                        print(f"    Adding chunk {j}: {chunk_start:.2f}s to {chunk_end:.2f}s (duration: {chunk_size:.2f}s)")
                        segments.append((chunk_start, chunk_end))
                print(f"  Added {num_chunks} duration-based segments")
            
            # Clean up temporary file
            try:
                os.remove(temp_file)
            except:
                pass
        
        # If segment is within range, add it directly
        elif min_duration <= segment_duration <= max_duration:
            # First, add any accumulated segments if they exist
            if current_segment_start is not None:
                print(f"Adding accumulated segments: {current_segment_start:.2f}s to {start:.2f}s (duration: {current_duration:.2f}s)")
                segments.append((current_segment_start, start))
                current_segment_start = None
                current_duration = 0
            
            print(f"Adding segment {i}: {start:.2f}s to {end:.2f}s")
            segments.append((start, end))
        
        # If segment is too short, accumulate it
        else:
            if current_segment_start is None:
                current_segment_start = start
            current_duration += segment_duration
            
            # If accumulated duration exceeds max_duration, split it
            if current_duration > max_duration:
                print(f"Splitting accumulated segments (duration: {current_duration:.2f}s)")
                num_chunks = int(np.ceil(current_duration / max_duration))
                chunk_duration = current_duration / num_chunks
                
                for j in range(num_chunks):
                    chunk_start = current_segment_start + (j * chunk_duration)
                    chunk_end = min(current_segment_start + ((j + 1) * chunk_duration), end)
                    chunk_size = chunk_end - chunk_start
                    if chunk_size >= min_duration:
                        print(f"  Adding accumulated chunk {j}: {chunk_start:.2f}s to {chunk_end:.2f}s (duration: {chunk_size:.2f}s)")
                        segments.append((chunk_start, chunk_end))
                
                current_segment_start = None
                current_duration = 0
            # If accumulated duration is within range, add it
            elif current_duration >= min_duration:
                print(f"Adding accumulated segments: {current_segment_start:.2f}s to {end:.2f}s (duration: {current_duration:.2f}s)")
                segments.append((current_segment_start, end))
                current_segment_start = None
                current_duration = 0
            else:
                print(f"Accumulating segment {i} (current total duration: {current_duration:.2f}s)")
    
    # Handle any remaining accumulated segments
    if current_segment_start is not None and current_duration >= min_duration:
        last_end = potential_segments[-1][1] if potential_segments else silence_ranges[-1][1]
        print(f"Adding final accumulated segments: {current_segment_start:.2f}s to {last_end:.2f}s (duration: {current_duration:.2f}s)")
        segments.append((current_segment_start, last_end))
    
    print(f"Found {len(segments)} segments between silence points")
            
    # Save silence points and segments information to JSON
    silence_info = {
        'filename': os.path.basename(input_file),
        'total_duration': total_duration,
        'processing_timestamp': datetime.now().isoformat(),
        'parameters': {
            'min_duration': min_duration,
            'max_duration': max_duration,
            'silence_thresh': silence_thresh,
            'min_silence_len': min_silence_len
        },
        'silence_ranges': [
            {
                'start': start,
                'end': end,
                'duration': end - start
            } for start, end in silence_ranges
        ],
        'segments': [
            {
                'start': start,
                'end': end,
                'duration': end - start
            } for start, end in segments
        ]
    }
    
    # Save to JSON file in centralized silence_points directory
    silence_points_dir = os.path.join(BASE_DATA_FOLDER, 'silence_points')
    os.makedirs(silence_points_dir, exist_ok=True)
    json_output_path = os.path.join(silence_points_dir, f'{base_filename}_silence_points.json')
    with open(json_output_path, 'w') as f:
        json.dump(silence_info, f, indent=2)
    
    print(f"Saved silence points and segments information to {json_output_path}")
    
    # Export the segments
    
    print(f"Created {len(segments)} segments")
    
    # Prepare export arguments
    export_args = []
    segment_info = {}  # Store segment information for CSV
    
    for i, (start, end) in enumerate(segments):
        output_path = os.path.join(output_dir, f'{base_filename}_segment_{i:03d}.ogg')
        export_args.append((input_file, start, end, output_path, min_silence_len))
        segment_info[output_path] = {'start': start, 'end': end}
    
    # Process segments in parallel
    successful_segments = []
    failed_segments = []
    
    # Ensure we have at least 1 worker, but no more than 2x CPU cores or number of segments
    max_workers = max(1, min(multiprocessing.cpu_count() * 2, len(segments)))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(export_segment, args) for args in export_args]
        
        with tqdm(total=len(segments), desc="Exporting segments") as pbar:
            for future in as_completed(futures):
                success, output_path, result = future.result()
                if success:
                    successful_segments.append((output_path, result))  # result is duration
                else:
                    failed_segments.append((output_path, result))  # result is error message
                pbar.update(1)
    
    # Write CSV file
    with open(csv_file_path, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['audio_file', 'start_time_seconds', 'end_time_seconds', 'duration_seconds'])
        
        for output_path, duration in successful_segments:
            info = segment_info[output_path]
            rel_path = os.path.relpath(output_path, start=os.path.dirname(csv_file_path))
            csv_writer.writerow([rel_path, info['start'], info['end'], duration])
    
    # Report results
    print(f"\nSuccessfully exported {len(successful_segments)} segments")
    if failed_segments:
        print(f"Failed to export {len(failed_segments)} segments:")
        for path, error in failed_segments:
            print(f"- {os.path.basename(path)}: {error}")
    
    return len(successful_segments)


def split_audio_at_silence(audio_or_path, base_filename, min_duration=2000, max_duration=15000, silence_thresh=-35, min_silence_len=700, crossfade=500):
    """Split audio into chunks between 2-15 seconds at silence points."""
    # Create output directories
    result_dir = os.path.join(BASE_DATA_FOLDER, 'result', base_filename)
    output_dir = os.path.join(result_dir, 'split')
    os.makedirs(result_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Created output directory: {output_dir}")
    
    if isinstance(audio_or_path, str):
        # If input is a file path, use FFmpeg-based splitting
        return split_audio_ffmpeg(
            audio_or_path, 
            output_dir, 
            base_filename,
            min_duration=min_duration/1000,  # Convert to seconds
            max_duration=max_duration/1000,  # Convert to seconds
            silence_thresh=silence_thresh,
            min_silence_len=min_silence_len
        )
    else:
        # If input is AudioSegment, use pydub-based splitting
        audio = audio_or_path
        silence_ranges = detect_silence_ranges(audio, silence_thresh, min_silence_len)
        chunks = []
        current_pos = 0
        
        for silence_start, silence_end in silence_ranges:
            if silence_start <= current_pos:
                continue
            
            chunk = audio[current_pos:silence_start]
            if len(chunk) >= min_duration:
                chunks.append(chunk)
            current_pos = silence_end
        
        # Handle remaining audio
        if current_pos < len(audio):
            remaining_chunk = audio[current_pos:]
            if len(remaining_chunk) >= min_duration:
                chunks.append(remaining_chunk)
        
        # Merge short chunks
        merged_chunks = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            if len(chunk) < min_duration:
                # Always merge with the next chunk
                if i + 1 < len(chunks):
                    next_chunk = chunks[i + 1]
                    combined = chunk + next_chunk
                    merged_chunks.append(combined)
                    i += 2  # Skip the next chunk
                    continue
                else:
                    # If it's the last chunk, just add it
                    merged_chunks.append(chunk)
            else:
                merged_chunks.append(chunk)
            i += 1
        
        # Adjust split points for word boundaries
        adjusted_chunks = adjust_split_points_for_words(merged_chunks, audio)
        
        # Export chunks
        os.makedirs(output_dir, exist_ok=True)
        
        csv_file_path = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, f'{base_filename}_transcripts.csv')
        with open(csv_file_path, mode='w', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['audio_file', 'start_time_seconds', 'end_time_seconds', 'duration_seconds'])
            
            for i, chunk in enumerate(adjusted_chunks):
                output_path = os.path.join(output_dir, f'{base_filename}_segment_{i:03d}.ogg')
                chunk.export(output_path, format="ogg")
                
                duration = len(chunk) / 1000
                start_time = (i * max_duration) / 1000
                end_time = start_time + duration
                
                rel_path = os.path.relpath(output_path, start=os.path.dirname(csv_file_path))
                csv_writer.writerow([rel_path, start_time, end_time, duration])
                click.echo(f"Exported: {output_path} (Duration: {duration:.2f}s)")
        
        return len(adjusted_chunks)


@click.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--min-silence-len', default=700, help='Minimum length of silence (in ms) to split on')
@click.option('--silence-thresh', default=-35, help='Silence threshold in dB')
def split_audio(input_file, min_silence_len, silence_thresh):
    """Split audio file based on silence detection."""
    
    # Get the filename without extension
    base_filename = os.path.splitext(os.path.basename(input_file))[0]
    
    # Load audio file
    click.echo(f"Loading audio file: {input_file}")
    audio = AudioSegment.from_file(input_file)
    click.echo(f"Audio duration: {len(audio)}ms")
    
    # Split audio at silence
    click.echo("\nSplitting audio into chunks...")
    split_audio_at_silence(input_file, base_filename, silence_thresh=silence_thresh, min_silence_len=min_silence_len)

if __name__ == '__main__':
    split_audio()
