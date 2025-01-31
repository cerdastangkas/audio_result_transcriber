#!/usr/bin/env python3

import os
import numpy as np
from pydub import AudioSegment
import click
import csv
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing

from dotenv import load_dotenv
load_dotenv()

BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')

def detect_silence_ranges(audio_segment, silence_thresh=-40, min_silence_len=500):
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


def detect_silence_ffmpeg(input_file, silence_thresh=-40, min_silence_len=500):
    """Detect silence using FFmpeg's silencedetect filter."""
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-af', f'silencedetect=noise={silence_thresh}dB:d={min_silence_len/1000}',
        '-f', 'null',
        '-'
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stderr
        
        silence_starts = []
        silence_ends = []
        
        for line in output.splitlines():
            if 'silence_start' in line:
                time = float(re.search(r'silence_start: ([\d.]+)', line).group(1))
                silence_starts.append(time)
            elif 'silence_end' in line:
                time = float(re.search(r'silence_end: ([\d.]+)', line).group(1))
                silence_ends.append(time)
        
        silence_points = list(zip(silence_starts, silence_ends))
        print(f"Detected {len(silence_points)} silence points")
        return silence_points
    
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg error: {e.stderr}")
    except Exception as e:
        raise RuntimeError(f"Error detecting silence: {str(e)}")

def export_segment(args):
    """Export a single audio segment using FFmpeg."""
    input_file, start, end, output_path = args
    
    try:
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files
            '-ss', str(start),  # Seek to position (put before -i for faster seeking)
            '-i', input_file,
            '-t', str(end - start),  # Duration instead of -to for more accurate cutting
            '-c', 'copy',  # Use copy codec for faster processing
            '-avoid_negative_ts', '1',  # Shift timestamps to positive values
            '-max_muxing_queue_size', '1024',  # Increase queue size for better performance
            output_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            return False, output_path, f"Error: {result.stderr.decode()}"
        return True, output_path, end - start
    except Exception as e:
        return False, output_path, str(e)

def split_audio_ffmpeg(input_file, output_dir, base_filename, min_duration=10, max_duration=15, silence_thresh=-40, min_silence_len=500):
    """Split audio file using FFmpeg based on silence detection with parallel processing."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare CSV file
    csv_file_path = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, f'{base_filename}_transcripts.csv')
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    
    # Detect silence points
    print("Detecting silence points...")
    silence_ranges = detect_silence_ffmpeg(input_file, silence_thresh, min_silence_len)
    
    if not silence_ranges:
        print("No silence points detected, adjusting threshold...")
        silence_ranges = detect_silence_ffmpeg(input_file, silence_thresh + 10, min_silence_len)
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
    
    # Create segments based on silence points
    segments = []
    current_start = 0
    
    for silence_start, silence_end in silence_ranges:
        segment_duration = silence_start - current_start
        
        if min_duration <= segment_duration <= max_duration:
            segments.append((current_start, silence_start))
            current_start = silence_end
        elif segment_duration > max_duration:
            # Split into multiple segments
            num_segments = int(np.ceil(segment_duration / max_duration))
            segment_size = segment_duration / num_segments
            
            for i in range(num_segments):
                seg_start = current_start + (i * segment_size)
                seg_end = min(seg_start + segment_size, silence_start)
                segments.append((seg_start, seg_end))
            
            current_start = silence_end
    
    # Handle the last segment
    if current_start < total_duration:
        remaining_duration = total_duration - current_start
        if remaining_duration >= min_duration:
            segments.append((current_start, total_duration))
    
    print(f"Created {len(segments)} segments")
    
    # Prepare export arguments
    export_args = []
    segment_info = {}  # Store segment information for CSV
    
    for i, (start, end) in enumerate(segments):
        output_path = os.path.join(output_dir, f'{base_filename}_segment_{i:03d}.ogg')
        export_args.append((input_file, start, end, output_path))
        segment_info[output_path] = {'start': start, 'end': end}
    
    # Process segments in parallel
    max_workers = min(multiprocessing.cpu_count() * 2, len(segments))  # Use 2x CPU cores
    successful_segments = []
    failed_segments = []
    
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


def split_audio_at_silence(audio_or_path, base_filename, min_duration=10000, max_duration=15000, silence_thresh=-40, min_silence_len=500, crossfade=500):
    """Split audio into chunks between 10-15 seconds at silence points."""
    output_dir = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, 'split')
    
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
@click.option('--min-silence-len', default=500, help='Minimum length of silence (in ms) to split on')
@click.option('--silence-thresh', default=-40, help='Silence threshold in dB')
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
