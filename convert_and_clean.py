import os
import csv
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing

from dotenv import load_dotenv
load_dotenv()

BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')

def convert_audio_file(args):
    """Convert a single audio file to WAV using FFmpeg."""
    input_file, output_file = args
    try:
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files
            '-i', input_file,
            '-acodec', 'pcm_s16le',  # 16-bit WAV
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',  # mono
            output_file
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            try:
                os.remove(input_file)  # Delete original file
                return True, input_file, output_file
            except Exception as e:
                return False, input_file, f"Error deleting original file: {str(e)}"
        else:
            return False, input_file, f"FFmpeg error: {result.stderr.decode()}"
    except Exception as e:
        return False, input_file, str(e)

def convert_chunks_to_wav(base_filename):
    """Convert all audio chunks to WAV format in parallel."""
    input_dir = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, 'split')
    csv_file_path = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, f'{base_filename}_transcripts.csv')
    
    # Read existing CSV data
    with open(csv_file_path, mode='r', newline='') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        fieldnames = csv_reader.fieldnames
        rows = list(csv_reader)
    
    # Prepare conversion arguments
    conversion_args = []
    for row in rows:
        if row['audio_file'].endswith('.ogg'):
            input_file = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, row['audio_file'])
            output_file = input_file.replace('.ogg', '.wav')
            conversion_args.append((input_file, output_file))
    
    if not conversion_args:
        print("No files to convert")
        return
    
    # Process conversions in parallel
    max_workers = min(multiprocessing.cpu_count() * 2, len(conversion_args))
    successful_conversions = []
    failed_conversions = []
    
    print(f"\nConverting {len(conversion_args)} audio files to WAV...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(convert_audio_file, args) for args in conversion_args]
        
        with tqdm(total=len(conversion_args), desc="Converting") as pbar:
            for future in as_completed(futures):
                success, input_file, result = future.result()
                if success:
                    successful_conversions.append((input_file, result))
                else:
                    failed_conversions.append((input_file, result))
                pbar.update(1)
    
    # Update CSV rows
    for row in rows:
        if row['audio_file'].endswith('.ogg'):
            row['audio_file'] = row['audio_file'].replace('.ogg', '.wav')
    
    # Write updated CSV data
    with open(csv_file_path, mode='w', newline='') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)
    
    # Report results
    print(f"\nSuccessfully converted {len(successful_conversions)} files")
    if failed_conversions:
        print(f"Failed to convert {len(failed_conversions)} files:")
        for input_file, error in failed_conversions:
            print(f"- {os.path.basename(input_file)}: {error}")
    
    print(f"CSV file updated with new filenames in {csv_file_path}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert audio chunks to WAV and delete original files')
    parser.add_argument('base_filename', type=str, help='base filename of the audio file')
    args = parser.parse_args()
    
    convert_chunks_to_wav(args.base_filename)
