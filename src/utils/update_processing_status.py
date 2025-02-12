import os
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
import logging

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

def get_filenames_without_extension(directory):
    """
    Get list of filenames without extensions from a directory.
    
    Args:
        directory (str): Directory path to scan
        
    Returns:
        set: Set of filenames without extensions
    """
    if not os.path.exists(directory):
        return set()
        
    filenames = set()
    for file in os.listdir(directory):
        # Get filename without extension
        filename = os.path.splitext(file)[0]
        filenames.add(filename)
    
    return filenames

def update_processing_status(excel_path):
    """
    Update processing_status in Excel file based on files in download and archive folders.
    
    Args:
        excel_path (str): Path to Excel file containing YouTube IDs
    """
    try:
        # Read Excel file
        logger.info(f"Reading Excel file: {excel_path}")
        df = pd.read_excel(excel_path)
        
        if 'id' not in df.columns:
            raise ValueError("Excel file must contain a column named 'id'")
            
        # Initialize processing_status column if it doesn't exist
        if 'processing_status' not in df.columns:
            df['processing_status'] = ''
            logger.info("Added 'processing_status' column to Excel file")
        
        # Get filenames from download and archive folders
        download_dir = os.path.join(BASE_DATA_FOLDER, 'download')
        archive_dir = os.path.join(BASE_DATA_FOLDER, 'archive')
        
        downloaded_files = get_filenames_without_extension(download_dir)
        archived_files = get_filenames_without_extension(archive_dir)
        
        logger.info(f"Found {len(downloaded_files)} files in download folder")
        logger.info(f"Found {len(archived_files)} files in archive folder")
        
        # Update counts
        updated_downloaded = 0
        updated_transcribed = 0
        
        # Update processing status for each row
        for idx, row in df.iterrows():
            youtube_id = str(row['id']).strip()
            current_status = str(row.get('processing_status', '')).lower()
            
            if youtube_id in archived_files and current_status != 'transcribed':
                df.at[idx, 'processing_status'] = 'transcribed'
                updated_transcribed += 1
            elif youtube_id in downloaded_files and current_status != 'downloaded':
                df.at[idx, 'processing_status'] = 'downloaded'
                updated_downloaded += 1
        
        # Save updated Excel file
        df.to_excel(excel_path, index=False)
        
        logger.info(f"Updated {updated_downloaded} rows to 'downloaded' status")
        logger.info(f"Updated {updated_transcribed} rows to 'transcribed' status")
        logger.info(f"Excel file saved: {excel_path}")
        
    except Exception as e:
        logger.error(f"Error updating processing status: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Update processing status in Excel file based on files in download and archive folders')
    parser.add_argument('excel_path', help='Path to Excel file containing YouTube IDs')
    
    args = parser.parse_args()
    update_processing_status(args.excel_path)
