import os
import pandas as pd
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
from tqdm import tqdm
import logging
import multiprocessing
import time

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get base data folder from environment
BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')

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
    
    ydl_opts = {
        # Try to get opus/ogg format directly, fallback to any audio
        'format': 'bestaudio[ext=opus]/bestaudio[ext=ogg]/bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'vorbis',  # This will create .ogg file
            'preferredquality': '128',
        }],
        'outtmpl': output_template,
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'extract_audio': True,
        # Optimize for speed
        'postprocessor_args': [
            '-threads', str(multiprocessing.cpu_count()),
            '-codec:a', 'libvorbis',
            '-q:a', '3',  # Vorbis quality setting (0-10, 3 is good quality)
            '-ar', '44100',
        ],
    }
    
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
            logger.info("No pending videos found to process")
            return
            
        logger.info(f"Found {len(pending_videos)} pending videos to process")
        
        # Create download directory if it doesn't exist
        download_dir = os.path.join(BASE_DATA_FOLDER, 'download')
        os.makedirs(download_dir, exist_ok=True)
        
        # Process each video
        success_count = 0
        for _, row in pending_videos.iterrows():
            video_id = str(row['id']).strip()
            
            try:
                success, output_file, error = download_audio(video_id, download_dir)
                
                if success:
                    success_count += 1
                    # Update status to 'downloaded' in the dataframe
                    df.loc[df['id'] == video_id, 'processing_status'] = 'downloaded'
                else:
                    # Update status to 'failed' and store error message
                    df.loc[df['id'] == video_id, 'processing_status'] = f'failed: {error}'
                    
            except Exception as e:
                logger.error(f"Error processing video {video_id}: {str(e)}")
                df.loc[df['id'] == video_id, 'processing_status'] = f'failed: {str(e)}'
        
        # Save updated Excel file
        df.to_excel(excel_path, index=False)
        logger.info(f"Successfully downloaded {success_count} out of {len(pending_videos)} pending videos")
        
    except Exception as e:
        logger.error(f"Error processing Excel file: {str(e)}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Download YouTube audio from IDs in Excel file')
    parser.add_argument('excel_path', help='Path to Excel file containing YouTube IDs')
    
    args = parser.parse_args()
    process_excel_file(args.excel_path)
