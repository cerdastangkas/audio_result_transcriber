import os
import csv
from pydub import AudioSegment

# Function to convert audio chunks to WAV and delete original files

def convert_chunks_to_wav(base_filename):
    input_dir = os.path.join('result', base_filename, 'split')
    csv_file_path = os.path.join('result', base_filename, f'{base_filename}_transcripts.csv')
    
    # Read existing CSV data
    with open(csv_file_path, mode='r', newline='') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        fieldnames = csv_reader.fieldnames
        rows = list(csv_reader)

    # Convert files and update CSV rows
    for row in rows:
        original_file = row['audio_file']
        if original_file.endswith('.ogg'):
            file_path = os.path.join('result', base_filename, original_file)
            # Load the original audio file
            audio = AudioSegment.from_file(file_path)
            # Define the new file path with .wav extension
            wav_file_path = file_path.replace('.ogg', '.wav')
            # Export the audio as 16-bit WAV
            audio.export(wav_file_path, format='wav', parameters=['-acodec', 'pcm_s16le'])
            print(f"Converted {file_path} to {wav_file_path}")
            # Delete the original file
            os.remove(file_path)
            print(f"Deleted original file {file_path}")
            # Update the row with the new file path
            row['audio_file'] = row['audio_file'].replace('.ogg', '.wav')

    # Write updated CSV data
    with open(csv_file_path, mode='w', newline='') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)

    print(f"CSV file updated with new filenames in {csv_file_path}")

# Example usage
# convert_chunks_to_wav('your_audio_file_name')
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Convert audio chunks to WAV and delete original files')
    parser.add_argument('base_filename', type=str, help='base filename of the audio file')
    args = parser.parse_args()

    convert_chunks_to_wav(args.base_filename)
