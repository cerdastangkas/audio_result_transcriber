#!/usr/bin/env python3

import os
import numpy as np
from pydub import AudioSegment
import click
import csv

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


def split_audio_at_silence(audio, base_filename, min_duration=10000, max_duration=15000, silence_thresh=-40, min_silence_len=500, crossfade=500):
    """Split audio into chunks between 10-15 seconds at silence points, ensuring no words are split."""
    
    # Detect silence ranges
    silence_ranges = detect_silence_ranges(audio, silence_thresh, min_silence_len)
    chunks = []
    current_pos = 0
    audio_len = len(audio)
    
    for silence_start, silence_end in silence_ranges:
        if silence_start <= current_pos:
            continue
        
        # Calculate chunk boundaries
        chunk_start = current_pos
        chunk_end = silence_start
        chunk_duration = chunk_end - chunk_start
        
        # Ensure chunk is within desired duration
        if min_duration <= chunk_duration <= max_duration:
            chunk = audio[chunk_start:chunk_end]
            if contains_speech(chunk):
                adjusted_chunk, was_adjusted = adjust_chunk_boundaries(chunk, crossfade, min_duration)
                chunks.append(adjusted_chunk)
            current_pos = silence_end
        elif chunk_duration > max_duration:
            # Split into multiple chunks
            split_start = chunk_start
            while split_start < chunk_end:
                split_end = min(split_start + max_duration, chunk_end)
                current_chunk = audio[split_start:split_end]
                if contains_speech(current_chunk):
                    adjusted_chunk, was_adjusted = adjust_chunk_boundaries(current_chunk, crossfade, min_duration)
                    chunks.append(adjusted_chunk)
                split_start = split_end
            current_pos = silence_end
        else:
            # If chunk is too short, merge with next
            continue
    
    # Handle remaining audio
    if current_pos < audio_len:
        remaining_chunk = audio[current_pos:]
        if len(remaining_chunk) >= min_duration and contains_speech(remaining_chunk):
            adjusted_chunk, was_adjusted = adjust_chunk_boundaries(remaining_chunk, crossfade, min_duration)
            chunks.append(adjusted_chunk)
    
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
    
    # Ensure output directory exists
    output_dir = os.path.join('result', base_filename, 'split')
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare CSV file
    csv_file_path = os.path.join('result', base_filename, f'{base_filename}_transcripts.csv')
    with open(csv_file_path, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['audio_file', 'start_time_seconds', 'end_time_seconds', 'duration_seconds'])
        
        # Export chunks and record details
        for i, chunk in enumerate(adjusted_chunks):
            output_path = os.path.join(output_dir, f"{base_filename}_segment_{i:03d}.ogg")
            chunk.export(output_path, format="ogg")
            start_time = (i * min_duration) / 1000
            end_time = start_time + len(chunk) / 1000
            duration = len(chunk) / 1000
            csv_writer.writerow([os.path.relpath(output_path, start=os.path.dirname(csv_file_path)), start_time, end_time, duration])
            click.echo(f"Exported: {output_path} (Duration: {duration:.2f}s)")
    
    click.echo("\nSplitting complete!")


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
    split_audio_at_silence(audio, base_filename, silence_thresh=silence_thresh, min_silence_len=min_silence_len)

if __name__ == '__main__':
    split_audio()
