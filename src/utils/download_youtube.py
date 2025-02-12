import os
import pandas as pd
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
from tqdm import tqdm
import logging
import multiprocessing
import time
from utils.logger_setup import setup_error_logger
import requests
import re

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
error_logger = setup_error_logger('youtube_download')

# Get environment variables
BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

def sanitize_error_message(error_msg):
    """
    Sanitize error message for Excel compatibility.
    Remove or replace characters that cause issues in Excel.
    """
    if not error_msg:
        return ""
    
    # Convert to string if not already
    error_msg = str(error_msg)
    
    # Remove URLs and file paths
    error_msg = re.sub(r'http[s]?://\S+', '[URL]', error_msg)
    error_msg = re.sub(r'See\s+\S+\s+for', 'See documentation for', error_msg)
    
    # Remove any non-printable characters
    error_msg = ''.join(char for char in error_msg if char.isprintable())
    
    # Truncate long messages
    if len(error_msg) > 250:
        error_msg = error_msg[:247] + "..."
    
    return error_msg

def setup_download_directory():
    """Create download directory if it doesn't exist."""
    download_dir = os.path.join(BASE_DATA_FOLDER, 'download')
    os.makedirs(download_dir, exist_ok=True)
    return download_dir

def format_time(seconds):
    """Format seconds into MM:SS format."""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

def check_video_availability(video_id):
    """
    Check if a video is available and accessible using YouTube Data API.
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        tuple: (is_available (bool), error_message (str))
    """
    if not YOUTUBE_API_KEY:
        logger.warning("No YouTube API key found. Skipping availability check.")
        return True, None
        
    url = f"https://www.googleapis.com/youtube/v3/videos"
    params = {
        'id': video_id,
        'key': YOUTUBE_API_KEY,
        'part': 'status,contentDetails'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if response.status_code != 200:
            error = data.get('error', {}).get('message', 'Unknown error')
            return False, f"YouTube API error: {error}"
        
        # Check if video exists
        if not data.get('items'):
            return False, "Video not found or is private"
        
        video = data['items'][0]
        
        # Check video status
        status = video.get('status', {})
        if status.get('privacyStatus') == 'private':
            return False, "This video is private"
        if status.get('uploadStatus') != 'processed':
            return False, "Video is not fully processed"
        
        # Check content details
        content_details = video.get('contentDetails', {})
        if content_details.get('licensedContent') and not YOUTUBE_API_KEY:
            return False, "This video requires authentication"
            
        return True, None
        
    except Exception as e:
        return False, f"Error checking video availability: {str(e)}"

def get_youtube_options(youtube_id, download_dir):
    """
    Get YouTube-DL options with cookie file from parent directory.
    
    Args:
        youtube_id (str): YouTube video ID
        download_dir (str): Directory to save the downloaded audio
        
    Returns:
        dict: YouTube-DL options
    """
    output_template = os.path.join(download_dir, f"{youtube_id}.%(ext)s")
    
    # Create progress bar
    pbar = None
    last_update = {'time': 0}
    
    def progress_hook(d):
        nonlocal pbar
        
        if d['status'] == 'downloading':
            # Update progress at most once per second
            current_time = time.time()
            if current_time - last_update['time'] < 0.1:  # Update every 100ms
                return
                
            try:
                if 'total_bytes' in d and 'downloaded_bytes' in d:
                    total = d['total_bytes']
                    downloaded = d['downloaded_bytes']
                    speed = d.get('speed', 0)
                    
                    # Initialize progress bar if not exists
                    if pbar is None:
                        pbar = tqdm(
                            total=total,
                            unit='B',
                            unit_scale=True,
                            unit_divisor=1024,
                            desc=f"Downloading {youtube_id}"
                        )
                    
                    # Update progress
                    if speed:
                        pbar.set_postfix({
                            'Speed': f"{speed/1024/1024:.1f}MB/s",
                            'ETA': format_time((total - downloaded) / speed)
                        }, refresh=False)
                    
                    pbar.update(downloaded - pbar.n)
                    last_update['time'] = current_time
                    
            except Exception:
                pass
                
        elif d['status'] == 'finished':
            if pbar:
                pbar.set_description(f"Converting {youtube_id} to OGG")
                
    # Check for cookies file in the same directory as the script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cookies_file = os.path.join(current_dir, 'youtube.cookies')
    
    if not os.path.exists(cookies_file):
        raise FileNotFoundError(f"Required cookies file not found at {cookies_file}. Please ensure youtube.cookies file exists.")
        
    ydl_opts = {
        'format': 'bestaudio[ext=opus]/bestaudio[ext=m4a]/bestaudio',  # Try opus first, then m4a, then any audio
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'vorbis',
            'preferredquality': '128',
        }],
        'outtmpl': output_template,
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'extract_audio': True,
        'postprocessor_args': [
            '-threads', str(multiprocessing.cpu_count()),
            '-codec:a', 'libvorbis',
            '-q:a', '3',
            '-ar', '44100',
        ],
        'cookiefile': cookies_file,  # Use cookies file for authentication
        'ignoreerrors': False  # Don't ignore errors to ensure we know if authentication fails
    }
    
    return ydl_opts, pbar

def download_audio(youtube_id, download_dir):
    """
    Download audio from YouTube video.
    
    Args:
        youtube_id (str): YouTube video ID
        download_dir (str): Directory to save the downloaded audio
    
    Returns:
        tuple: (success (bool), output_file (str), error_message (str))
    """
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    ydl_opts, pbar = get_youtube_options(youtube_id, download_dir)
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            if pbar:
                pbar.close()
            return True, f"{youtube_id}.ogg", None
            
    except Exception as e:
        if pbar:
            pbar.close()
        error_msg = str(e)
        logger.error(f"Error downloading {youtube_id}: {error_msg}")
        error_logger.error(f"Error downloading {youtube_id}: {error_msg}")
        return False, None, error_msg

def process_excel_file(excel_path):
    """
    Process an Excel file containing YouTube video IDs.
    
    Args:
        excel_path (str): Path to Excel file containing YouTube video IDs
    """
    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        
        if 'id' not in df.columns:
            raise ValueError("Excel file must contain a column named 'id'")
        
        # Initialize processing_status column if it doesn't exist
        if 'processing_status' not in df.columns:
            df['processing_status'] = 'pending'
        
        # Get only pending videos
        pending_videos = df[df['processing_status'].fillna('').str.lower() == 'pending']
        
        if pending_videos.empty:
            logger.info("No pending videos found in Excel file")
            return
        
        logger.info(f"Found {len(pending_videos)} pending videos to process")
        
        # Create download directory if it doesn't exist
        download_dir = setup_download_directory()
        
        # Process each video
        success_count = 0
        for index, row in pending_videos.iterrows():
            video_id = row['id']
            logger.info(f"\nProcessing video {video_id}")
            
            success, output_file, error = download_audio(video_id, download_dir)
            
            # Update Excel with sanitized status
            if success:
                df.at[index, 'processing_status'] = 'downloaded'
                success_count += 1
            else:
                # Sanitize error message before writing to Excel
                sanitized_error = sanitize_error_message(error)
                df.at[index, 'processing_status'] = f'failed: {sanitized_error}'
            
            # Save after each video in case of interruption
            try:
                df.to_excel(excel_path, index=False)
            except Exception as e:
                logger.error(f"Error saving Excel file: {e}")
                error_logger.error(f"Error saving Excel file: {e}")
        
        logger.info(f"\nProcessing complete. Successfully downloaded {success_count} out of {len(pending_videos)} videos")
        
    except Exception as e:
        logger.error(f"Error processing Excel file: {e}")
        error_logger.error(f"Error processing Excel file: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Download YouTube audio from IDs in Excel file')
    parser.add_argument('excel_path', help='Path to Excel file containing YouTube IDs')
    
    args = parser.parse_args()
    process_excel_file(args.excel_path)
