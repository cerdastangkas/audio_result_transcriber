import os
import json
import requests
import csv
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)
from tqdm import tqdm
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import multiprocessing
import sys
from pathlib import Path

# Add the parent directory to sys.path to allow importing from sibling modules
src_dir = str(Path(__file__).resolve().parent.parent)
if src_dir not in sys.path:
    sys.path.append(src_dir)

from utils.constants import BASE_DATA_FOLDER, OPENAI_API_KEY
from utils.transcription_stats import TranscriptionStats

# API keys
DEEPINFRA_API_KEY = "your-api-key-here"

# Configure session with retry logic
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  # number of retries
        backoff_factor=5,  # wait 1, 2, 4 seconds between retries
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
                text = response.json().get('text', '')
                duration_seconds = response.json().get('duration', None)
                
                # Check if text has meaningful content
                if not has_meaningful_content(text, duration_seconds):
                    return False, file_path, "Empty or meaningless text", 0.0
                    
                return True, file_path, text, duration_seconds
            elif response.status_code == 429:  # Rate limit
                time.sleep(5)  # Wait 5 seconds before retry
                return False, file_path, "Rate limit exceeded", 0.0
            else:
                return False, file_path, f"Error {response.status_code}: {response.text}", 0.0
    except Exception as e:
        return False, file_path, str(e)

def has_meaningful_content(text, duration_seconds=None):
    """Check if text contains actual words, not just punctuation or spaces.
    Also filters out segments that have less than 2 words AND duration > 2 seconds.
    
    Args:
        text (str): The text to check
        duration_seconds (float, optional): Duration of the audio segment in seconds
    
    Returns:
        bool: True if text has meaningful content, False otherwise
    """
    # Remove common punctuation and whitespace
    import re
    cleaned_text = re.sub(r'[.,!?;:\-\s]+', '', text.strip())
    
    # Basic check for non-empty content
    if len(cleaned_text) == 0:
        return False
        
    # Count words (split by whitespace after stripping punctuation)
    words = [w for w in re.sub(r'[.,!?;:\-]+', '', text.strip()).split() if w]
    word_count = len(words)
    
    # Check if text has actual words
    if word_count == 0:
        return False
    
    # If duration is provided, check for segments with few words but long duration
    if duration_seconds and duration_seconds > 2 and word_count <= 2:
        return False
        
    return True

def has_no_special_characters(text):
    """Check if text doesn't contain special characters like CJK or Cyrillic."""
    # Define ranges for unwanted character sets
    special_ranges = [
        (0x3040, 0x30FF),    # Hiragana and Katakana
        (0x4E00, 0x9FFF),    # CJK Unified Ideographs (Chinese)
        (0xAC00, 0xD7AF),    # Hangul Syllables (Korean)
        (0x0400, 0x04FF),    # Cyrillic
        (0x0500, 0x052F),    # Cyrillic Supplement
    ]
    
    # Check for special characters
    for char in text:
        char_code = ord(char)
        for start, end in special_ranges:
            if start <= char_code <= end:
                return False
    
    return True

def remove_from_csv(base_filename, audio_file):
    """Remove an entry from the transcripts CSV file."""
    result_dir = os.path.join(BASE_DATA_FOLDER, 'result', base_filename)
    csv_file_path = os.path.join(result_dir, f'{base_filename}_transcripts.csv')
    
    if not os.path.exists(csv_file_path):
        print(f"Error: Transcript file not found: {csv_file_path}")
        return False
    
    # Read existing rows
    rows = []
    with open(csv_file_path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)
    
    # Get base name of current audio file without extension
    current_base = os.path.splitext(os.path.basename(audio_file))[0]
    
    # Filter out the matching row
    new_rows = []
    for row in rows:
        row_base = os.path.splitext(os.path.basename(row['audio_file']))[0]
        if row_base != current_base:
            new_rows.append(row)
    
    # Write updated CSV
    fieldnames = ['audio_file', 'start_time_seconds', 'end_time_seconds', 'duration_seconds', 'text']
    with open(csv_file_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)
    
    print(f"Removed entry for {current_base} from {csv_file_path}")
    return True

def cleanup_invalid_transcription(file_path, reason):
    """Clean up invalid transcription by removing CSV entry and audio file."""
    try:
        # Get base filename from path
        base_filename = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
        
        # Remove from CSV
        remove_from_csv(base_filename, file_path)
        
        # Delete audio file if it exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"    Deleted audio file: {file_path}")
            except Exception as e:
                print(f"    Warning: Could not delete audio file {file_path}: {str(e)}")
            
        print(f"    Cleaned up invalid transcription: {reason}")
    except Exception as e:
        print(f"    Warning: Error during cleanup: {str(e)}")
        # Try to remove file even if CSV removal failed
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"    Deleted audio file: {file_path}")
            except Exception as e2:
                print(f"    Warning: Could not delete audio file {file_path}: {str(e2)}")

def transcribe_audio_with_openai(args):
    """Transcribe a single audio file using OpenAI's Whisper API."""
    session, file_path = args
    max_retries = 3
    retry_count = 0
    retry_delay = 20  # Initial delay in seconds
    file_name = os.path.basename(file_path)

    while retry_count < max_retries:
        try:
            if retry_count > 0:
                logger.warning(f"[{file_name}] Retry attempt {retry_count}/{max_retries} after waiting {retry_delay}s")

            url = 'https://api.openai.com/v1/audio/transcriptions'
            headers = {
                'Authorization': f'Bearer {OPENAI_API_KEY}'
            }
            logger.info(f"[{file_name}] Starting transcription attempt {retry_count + 1}/{max_retries}")
        
            # Get video ID from file path
            video_id = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
            
            # Create centralized responses directory
            responses_dir = os.path.join(BASE_DATA_FOLDER, 'openai_responses', video_id)
            os.makedirs(responses_dir, exist_ok=True)
            
            with open(file_path, 'rb') as f:
                files = {
                    'file': f,
                    'model': (None, 'whisper-1'),
                    'response_format': (None, 'verbose_json'),  # Get detailed response including language
                    'prompt': (None, 'This is mainly a conversation in Indonesian language audio file.'),
                    'temperature': (None, '0.13')
                }
                response = session.post(url, headers=headers, files=files)
                
                if response.status_code == 200:
                    response_data = response.json()
                    
                    # Save full response to JSON file
                    response_file = os.path.join(responses_dir, f'{os.path.basename(file_path)}_response.json')
                    with open(response_file, 'w', encoding='utf-8') as f:
                        json.dump(response_data, f, indent=2, ensure_ascii=False)
                    # print(f"    Full response saved to: {response_file}")
                    
                    text = response_data.get('text', '')
                    detected_language = response_data.get('language')
                    duration_seconds = response_data.get('duration', None)
                    
                    # First check if text has meaningful content
                    if not has_meaningful_content(text, duration_seconds):
                        cleanup_invalid_transcription(file_path, f"Empty or meaningless text: {text}")
                        return False, file_path, '', 0.0
                    
                    # Handle case where language detection failed
                    if not detected_language:
                        cleanup_invalid_transcription(file_path, f"Language detection failed")
                        return False, file_path, '', 0.0
                    
                    detected_language = detected_language.lower()
                    
                    # Then check if OpenAI detected Indonesian
                    if detected_language == 'indonesian':
                        # Finally check for special characters
                        if has_no_special_characters(text):
                            logger.info(f"[{file_name}] Success: Valid Indonesian text detected ({len(text)} chars, {duration_seconds:.1f}s)")
                            return True, file_path, text, duration_seconds
                        else:
                            cleanup_invalid_transcription(file_path, f"Contains special characters: {text}")
                            return False, file_path, '', 0.0
                    else:
                        cleanup_invalid_transcription(file_path, f"Non-Indonesian language: {detected_language}")
                        return False, file_path, '', 0.0
                        
                elif response.status_code == 429:  # Rate limit
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"[{file_name}] Rate limit hit. Waiting {retry_delay}s before retry {retry_count + 1}/{max_retries}")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error(f"[{file_name}] Failed: Rate limit exceeded after {max_retries} retries")
                        return False, file_path, "Rate limit exceeded after max retries", 0.0
                else:
                    error_msg = f"OpenAI API error: {response.status_code} - {response.text}"
                    logger.error(f"[{file_name}] Failed: {error_msg}")
                    return False, file_path, error_msg, 0.0

        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"[{file_name}] Error: {str(e)}. Waiting {retry_delay}s before retry {retry_count + 1}/{max_retries}")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error(f"[{file_name}] Failed: Error after {max_retries} retries - {str(e)}")
                return False, file_path, f"Error after max retries: {str(e)}", 0.0

    return False, file_path, "Failed after all retries", 0.0

def transcribe_chunks(base_filename, model='openai/whisper-large-v3', use_openai=False):
    """Transcribe all audio chunks in parallel and save to CSV."""
    if not base_filename:
        print("Error: No base filename provided")
        return False
        
    # Initialize transcription statistics
    stats = TranscriptionStats(base_filename)
    stats.start()
        
    try:
        # Setup directories
        result_dir = os.path.join(BASE_DATA_FOLDER, 'result', base_filename)
        if not os.path.exists(result_dir):
            print(f"Error: Result directory not found: {result_dir}")
            return False
            
        input_dir = os.path.join(result_dir, 'split')
        if not os.path.exists(input_dir):
            print(f"Error: Split directory not found: {input_dir}")
            return False
            
        csv_file_path = os.path.join(result_dir, f'{base_filename}_transcripts.csv')
    except Exception as e:
        print(f"Error setting up directories: {str(e)}")
        stats.add_failed_transcription('setup', str(e))
        stats.finish()
        stats.save_stats(result_dir)
        return False
    
    # Create result directory if it doesn't exist
    os.makedirs(result_dir, exist_ok=True)
    
    # Get list of audio files to transcribe
    if not os.path.exists(input_dir):
        print(f"Error: Split directory not found: {input_dir}")
        return
        
    audio_files = [f for f in os.listdir(input_dir) if f.endswith('.wav') and 'segment' in f]
    if not audio_files:
        print(f"Error: No audio segments found in {input_dir}")
        stats.finish()
        stats.save_stats(result_dir)
        return
        
    audio_files.sort(key=lambda x: int(''.join(filter(str.isdigit, x))))
    print(f"Found {len(audio_files)} audio segments to transcribe")
    
    # Create rows directly from audio files in split directory
    rows = []
    for audio_file in sorted(audio_files):
        audio_file_path = os.path.join(input_dir, audio_file)
        rows.append({
            'audio_file': f'split/{audio_file}',
            'start_time_seconds': '0',
            'end_time_seconds': '0',  # We don't need exact timing for transcription
            'duration_seconds': '0',
            'text': '',
            'accepted_by_asix': '',
            'rejected_reason': '',
            'hyperjump_response': ''
        })
            
    if not rows:
        print("Error: No valid audio segments found")
        return False
    
    # Prepare transcription arguments
    session = create_session()
    transcription_args = []
    valid_rows = []
    
    for row in rows:
        # Use OGG file for transcription
        audio_file_path = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, row['audio_file'])
        
        # Skip if audio file doesn't exist
        if not os.path.exists(audio_file_path):
            print(f"\nSkipping missing audio file: {row['audio_file']}")
            continue
            
        if use_openai:
            transcription_args.append((session, audio_file_path))
        else:
            transcription_args.append((session, audio_file_path, model))
        valid_rows.append(row)
    
    # Update rows to only include those with existing audio files
    rows = valid_rows
    
    if not transcription_args:
        print("No valid audio files found for transcription")
        stats.finish()
        stats.save_stats(result_dir)
        return False
        
    # Set total segments for statistics
    stats.set_total_segments(len(transcription_args))
    
    # Process transcriptions in parallel
    max_workers = min(multiprocessing.cpu_count() * 2, len(rows))  # Use 2x CPU cores
    successful_transcriptions = {}
    successful_durations = {}
    failed_transcriptions = []
    
    print(f"\nTranscribing {len(rows)} audio segments...")
    if len(rows) == 0:
        print("No audio segments to transcribe")
        return False
        
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if use_openai:
            print("Using OpenAI Whisper API for transcription...")
            futures = [executor.submit(transcribe_audio_with_openai, args) for args in transcription_args]
        else:
            print("Using DeepInfra API for transcription...")
            futures = [executor.submit(transcribe_audio_with_session, args) for args in transcription_args]
        
        with tqdm(total=len(rows), desc="Transcribing") as pbar:
            for future in as_completed(futures):
                success, file_path, result, duration_seconds = future.result()
                if success:
                    successful_transcriptions[file_path] = result
                    successful_durations[file_path] = duration_seconds
                    stats.add_successful_transcription(file_path, duration_seconds)
                else:
                    failed_transcriptions.append((file_path, result))
                    stats.add_failed_transcription(file_path, result)
                pbar.update(1)
                
                # Add small delay to avoid rate limiting
                time.sleep(0.1)
    
    # Update rows, excluding failed transcriptions
    valid_rows = []
    for row in rows:
        audio_file_path = os.path.join(BASE_DATA_FOLDER, 'result', base_filename, row['audio_file'])
        if audio_file_path in successful_transcriptions:
            row['text'] = successful_transcriptions[audio_file_path]
            row['duration_seconds'] = successful_durations[audio_file_path]
            row['accepted_by_asix'] = ''
            row['rejected_reason'] = ''
            row['hyperjump_response'] = ''
            valid_rows.append(row)

    # Replace rows with only valid ones
    rows = valid_rows
    
    # Sort rows by audio_file name
    def extract_segment_number(filename):
        import re
        match = re.search(r'segment_(\d+)', filename)
        return int(match.group(1)) if match else 0
    
    sorted_rows = sorted(rows, key=lambda x: extract_segment_number(x['audio_file']))
    
    # Write updated CSV
    fieldnames = ['audio_file', 'start_time_seconds', 'end_time_seconds', 'duration_seconds', 'text', 'accepted_by_asix', 'rejected_reason', 'hyperjump_response']
    with open(csv_file_path, mode='w', newline='') as updated_csv_file:
        csv_writer = csv.DictWriter(updated_csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)
    
    # Update statistics and save
    stats.finish()
    stats.save_stats(result_dir)
    stats.print_summary()
    
    # Report results
    print(f"\nTranscriptions updated in {csv_file_path}")
    return True

# Example usage
# transcribe_chunks('your_audio_file_name')
