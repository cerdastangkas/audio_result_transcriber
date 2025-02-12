#!/usr/bin/env python3

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')

def convert_audio_file(args):
    """Convert a single audio file to OGG format using FFmpeg."""
    input_file, output_file = args
    
    try:
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files
            '-i', input_file,
            '-c:a', 'libvorbis',  # Use Vorbis codec for OGG
            '-q:a', '4',  # Quality setting (0-10, 4 is good quality)
            '-ar', '44100',  # Sample rate
            output_file
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            return False, input_file, f"Error: {result.stderr.decode()}"
        return True, input_file, None
    except Exception as e:
        return False, input_file, str(e)

def convert_mp3_to_ogg(input_dir=None):
    """
    Convert all MP3 files in the input directory to OGG format.
    If input_dir is not provided, uses BASE_DATA_FOLDER/download.
    """
    if input_dir is None:
        input_dir = os.path.join(BASE_DATA_FOLDER, 'download')
    
    # Find all MP3 files
    mp3_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.mp3'):
                mp3_files.append(os.path.join(root, file))
    
    if not mp3_files:
        print("No MP3 files found in the directory.")
        return
    
    print(f"Found {len(mp3_files)} MP3 files to convert")
    
    # Prepare conversion arguments
    conversion_args = []
    for mp3_file in mp3_files:
        output_file = os.path.splitext(mp3_file)[0] + '.ogg'
        conversion_args.append((mp3_file, output_file))
    
    # Process files in parallel
    max_workers = min(multiprocessing.cpu_count() * 2, len(mp3_files))  # Use 2x CPU cores
    successful_conversions = []
    failed_conversions = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(convert_audio_file, args) for args in conversion_args]
        
        with tqdm(total=len(mp3_files), desc="Converting files") as pbar:
            for future in as_completed(futures):
                success, input_file, error = future.result()
                if success:
                    successful_conversions.append(input_file)
                else:
                    failed_conversions.append((input_file, error))
                pbar.update(1)
    
    # Report results
    print(f"\nSuccessfully converted {len(successful_conversions)} files")
    if failed_conversions:
        print(f"Failed to convert {len(failed_conversions)} files:")
        for path, error in failed_conversions:
            print(f"- {os.path.basename(path)}: {error}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert MP3 files to OGG format')
    parser.add_argument('--input-dir', help='Directory containing MP3 files (default: BASE_DATA_FOLDER/download)')
    
    args = parser.parse_args()
    convert_mp3_to_ogg(args.input_dir)
