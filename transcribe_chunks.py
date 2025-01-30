import os
import requests
import csv
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get DeepInfra API key from environment variables
DEEPINFRA_API_KEY = os.getenv('DEEPINFRA_API_KEY')

# Function to transcribe audio using DeepInfra API

def transcribe_audio(file_path, model='openai/whisper-large'):
    url = 'https://api.deepinfra.com/v1/openai/audio/transcriptions'
    headers = {
        'Authorization': f'Bearer {DEEPINFRA_API_KEY}',
    }
    files = {
        'file': open(file_path, 'rb'),
        'model': (None, model)
    }
    response = requests.post(url, headers=headers, files=files)
    if response.status_code == 200:
        return response.json().get('text', '')
    else:
        print(f"Error transcribing {file_path}: {response.status_code} {response.text}")
        return ''

# Transcribe all audio chunks and save to CSV

def transcribe_chunks(base_filename):
    input_dir = os.path.join('result', base_filename, 'split')
    csv_file_path = os.path.join('result', base_filename, f'{base_filename}_transcripts.csv')
    
    with open(csv_file_path, mode='r', newline='') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        fieldnames = csv_reader.fieldnames + ['text']
        rows = list(csv_reader)
        
        for row in rows:
            audio_file_path = os.path.join('result', base_filename, row['audio_file'])  
            transcription = transcribe_audio(audio_file_path)
            row['text'] = transcription
            print(f"Transcribed {audio_file_path}")

    # Update existing CSV with transcriptions
    with open(csv_file_path, mode='w', newline='') as updated_csv_file:
        csv_writer = csv.DictWriter(updated_csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)

    print(f"Transcriptions updated in {csv_file_path}")

# Example usage
# transcribe_chunks('your_audio_file_name')
