#!/usr/bin/env python3

import os
import json
import requests
import argparse
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get environment variables
BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def has_meaningful_content(text):
    """Check if text contains actual words, not just punctuation or spaces."""
    if not text or len(text.strip()) == 0:
        return False
    
    # Remove punctuation and spaces
    cleaned_text = ''.join(c for c in text if c.isalnum())
    return len(cleaned_text) > 0

def transcribe_audio_with_openai(file_path, output_dir=None):
    """
    Transcribe a single audio file using OpenAI's Whisper API.
    
    Args:
        file_path (str): Path to the audio file to transcribe
        output_dir (str, optional): Directory to save the JSON output. 
                                  If not provided, will create a 'transcriptions' directory
                                  in the same directory as the input file.
    
    Returns:
        tuple: (success (bool), output_file (str), error_message (str))
    """
    try:
        if not os.path.exists(file_path):
            return False, None, f"File not found: {file_path}"
            
        if not OPENAI_API_KEY:
            return False, None, "OpenAI API key not found in environment variables"
            
        # Create session with retry strategy
        session = requests.Session()
        
        # Setup API request
        url = 'https://api.openai.com/v1/audio/transcriptions'
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}'
        }
        
        # Determine output directory
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(file_path), 'transcriptions')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output filename based on input filename and timestamp
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f'{base_name}_{timestamp}_transcription.json')
        
        logger.info(f"Transcribing {file_path}...")
        
        with open(file_path, 'rb') as f:
            files = {
                'file': f,
                'model': (None, 'whisper-1'),
                'response_format': (None, 'verbose_json'),
                'prompt': (None, 'This is mainly a conversation in Indonesian language audio file.'),
                'temperature': (None, '0.13')
            }
            response = session.post(url, headers=headers, files=files)
            
            if response.status_code == 200:
                response_data = response.json()
                text = response_data.get('text', '')
                
                # Check if text has meaningful content
                if not has_meaningful_content(text):
                    return False, None, f"Empty or meaningless text detected: {text}"
                
                # Add metadata to response
                response_data['metadata'] = {
                    'input_file': file_path,
                    'transcription_time': datetime.now().isoformat(),
                    'model': 'whisper-1'
                }
                
                # Save full response to JSON file
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(response_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Transcription saved to: {output_file}")
                return True, output_file, None
            else:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                return False, None, error_msg
                
    except Exception as e:
        return False, None, f"Error during transcription: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description='Transcribe a single audio file using OpenAI Whisper')
    parser.add_argument('file_path', help='Path to the audio file to transcribe')
    parser.add_argument('--output-dir', help='Directory to save the transcription JSON (optional)')
    
    args = parser.parse_args()
    
    success, output_file, error = transcribe_audio_with_openai(args.file_path, args.output_dir)
    
    if success:
        logger.info("Transcription completed successfully!")
        logger.info(f"Output file: {output_file}")
    else:
        logger.error(f"Transcription failed: {error}")
        exit(1)

if __name__ == "__main__":
    main()
