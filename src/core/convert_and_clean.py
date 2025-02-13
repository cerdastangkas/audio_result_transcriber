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
    """Convert a single audio file to WAV using FFmpeg and remove the original OGG."""
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
                os.remove(input_file)  # Remove original OGG file
                return True, output_file
            except Exception as e:
                return False, f"Error removing original file: {str(e)}"
        else:
            return False, f"FFmpeg error: {result.stderr.decode()}"
    except Exception as e:
        return False, str(e)

def update_csv_with_wav_paths(base_filename):
    """Update the CSV file to use WAV file paths instead of OGG."""
    csv_file_path = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, f'{base_filename}_transcripts.csv')
    if not os.path.exists(csv_file_path):
        print(f"Error: Transcript file not found: {csv_file_path}")
        return False
    
    # Read existing rows
    rows = []
    with open(csv_file_path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)
    
    # Update file paths
    updated_rows = []
    for row in rows:
        if 'audio_file' in row:
            # Replace .ogg with .wav in the file path
            row['audio_file'] = row['audio_file'].replace('.ogg', '.wav')
        updated_rows.append(row)
    
    # Write updated CSV
    fieldnames = ['audio_file', 'start_time_seconds', 'end_time_seconds', 'duration_seconds', 'text']
    with open(csv_file_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    print(f"Updated audio file paths in {csv_file_path}")
    return True

def convert_chunks_to_wav(base_filename):
    """Convert all audio chunks to WAV format in parallel and remove original OGG files."""
    input_dir = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, 'split')
    
    # Get list of audio files
    audio_files = [f for f in os.listdir(input_dir) if f.endswith('.ogg') and 'segment' in f]
    if not audio_files:
        print(f"No audio segments found in {input_dir}")
        return
    
    # Prepare conversion arguments
    conversion_args = []
    for audio_file in audio_files:
        input_file = os.path.join(input_dir, audio_file)
        output_file = os.path.join(input_dir, audio_file.replace('.ogg', '.wav'))
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
                success, result = future.result()
                if success:
                    successful_conversions.append(result)
                else:
                    failed_conversions.append(result)
                pbar.update(1)
    
    # Print summary of conversion results
    print(f"\nSuccessfully converted {len(successful_conversions)} files to WAV and removed original OGG files")
    if failed_conversions:
        print(f"Failed to convert {len(failed_conversions)} files:")
        for error in failed_conversions:
            print(f"- {error}")
    
    # Update CSV file with WAV paths
    if successful_conversions:
        update_csv_with_wav_paths(base_filename)
    
    # Clean up temp folder if it exists
    temp_dir = os.path.join(input_dir, 'temp')
    if os.path.exists(temp_dir):
        try:
            import shutil
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            print(f"Warning: Could not remove temp directory: {e}")
    
    return successful_conversions

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert audio chunks to WAV and delete original files')
    parser.add_argument('base_filename', type=str, help='base filename of the audio file')
    args = parser.parse_args()
    
    convert_chunks_to_wav(args.base_filename)
