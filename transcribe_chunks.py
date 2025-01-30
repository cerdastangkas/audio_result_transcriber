import os
import requests
import csv
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import multiprocessing

# Load environment variables from .env file
load_dotenv()

# Get DeepInfra API key from environment variables
DEEPINFRA_API_KEY = os.getenv('DEEPINFRA_API_KEY')

# Configure session with retry logic
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  # number of retries
        backoff_factor=1,  # wait 1, 2, 4 seconds between retries
        status_forcelist=[429, 500, 502, 503, 504]  # HTTP status codes to retry on
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.headers.update({'Authorization': f'Bearer {DEEPINFRA_API_KEY}'})
    return session

def transcribe_audio_with_session(args):
    """Transcribe a single audio file using DeepInfra API with session."""
    session, file_path, model = args
    try:
        url = 'https://api.deepinfra.com/v1/openai/audio/transcriptions'
        
        with open(file_path, 'rb') as f:
            files = {
                'file': f,
                'model': (None, model)
            }
            response = session.post(url, files=files)
            
            if response.status_code == 200:
                return True, file_path, response.json().get('text', '')
            elif response.status_code == 429:  # Rate limit
                time.sleep(5)  # Wait 5 seconds before retry
                return False, file_path, "Rate limit exceeded"
            else:
                return False, file_path, f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return False, file_path, str(e)

def transcribe_chunks(base_filename, model='openai/whisper-large'):
    """Transcribe all audio chunks in parallel and save to CSV."""
    input_dir = os.path.join('result', base_filename, 'split')
    csv_file_path = os.path.join('result', base_filename, f'{base_filename}_transcripts.csv')
    
    # Read existing CSV
    with open(csv_file_path, mode='r', newline='') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        fieldnames = csv_reader.fieldnames + ['text']
        rows = list(csv_reader)
    
    # Prepare transcription arguments
    session = create_session()
    transcription_args = []
    for row in rows:
        audio_file_path = os.path.join('result', base_filename, row['audio_file'])
        transcription_args.append((session, audio_file_path, model))
    
    # Process transcriptions in parallel
    max_workers = min(multiprocessing.cpu_count() * 2, len(rows))  # Use 2x CPU cores
    successful_transcriptions = {}
    failed_transcriptions = []
    
    print(f"\nTranscribing {len(rows)} audio segments...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(transcribe_audio_with_session, args) for args in transcription_args]
        
        with tqdm(total=len(rows), desc="Transcribing") as pbar:
            for future in as_completed(futures):
                success, file_path, result = future.result()
                if success:
                    successful_transcriptions[file_path] = result
                else:
                    failed_transcriptions.append((file_path, result))
                pbar.update(1)
                
                # Add small delay to avoid rate limiting
                time.sleep(0.1)
    
    # Update rows with transcriptions
    for row in rows:
        audio_file_path = os.path.join('result', base_filename, row['audio_file'])
        row['text'] = successful_transcriptions.get(audio_file_path, '')
    
    # Write updated CSV
    with open(csv_file_path, mode='w', newline='') as updated_csv_file:
        csv_writer = csv.DictWriter(updated_csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)
    
    # Report results
    print(f"\nSuccessfully transcribed {len(successful_transcriptions)} segments")
    if failed_transcriptions:
        print(f"Failed to transcribe {len(failed_transcriptions)} segments:")
        for path, error in failed_transcriptions:
            print(f"- {os.path.basename(path)}: {error}")
    
    print(f"Transcriptions updated in {csv_file_path}")

# Example usage
# transcribe_chunks('your_audio_file_name')
