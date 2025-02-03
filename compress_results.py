import os
import zipfile
from dotenv import load_dotenv
import logging
from tqdm import tqdm
import shutil
import pandas as pd
from datetime import datetime
from utils.logger_setup import setup_error_logger

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
error_logger = setup_error_logger('compress_results')

# Add file handler for failed processes
def setup_error_logger():
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create log file with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'compression_failures_{timestamp}.log')
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.ERROR)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    error_logger.addHandler(file_handler)
    
    return error_logger

# Get base data folder from environment
BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')

def get_folder_size(folder_path):
    """Calculate total size of a folder in bytes."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            total_size += os.path.getsize(file_path)
    return total_size

def compress_folder(folder_path, zip_path, base_folder_name):
    """
    Compress a folder to a zip file with progress bar.
    
    Args:
        folder_path (str): Path to the folder to compress
        zip_path (str): Path where to save the zip file
        base_folder_name (str): Name of the base folder for relative paths
    """
    total_size = get_folder_size(folder_path)
    processed_size = 0
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Create progress bar
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=f"Compressing {os.path.basename(folder_path)}") as pbar:
            for root, dirs, files in os.walk(folder_path):
                # Calculate relative path from base_folder_name
                rel_path = os.path.relpath(root, os.path.dirname(base_folder_name))
                
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.join(rel_path, file)
                    
                    # Add file to zip
                    zipf.write(file_path, arcname)
                    
                    # Update progress
                    file_size = os.path.getsize(file_path)
                    processed_size += file_size
                    pbar.update(file_size)

def compress_result_folders():
    """Compress each folder under the result directory and update Excel file."""
    result_dir = os.path.join(BASE_DATA_FOLDER, 'result')
    excel_path = os.path.join(BASE_DATA_FOLDER, 'youtube_videos_submitted.xlsx')
    
    # Setup error logger
    failed_items = []
    
    if not os.path.exists(result_dir):
        error_msg = f"Result directory not found: {result_dir}"
        logger.error(error_msg)
        error_logger.error(error_msg)
        return
    
    # Read Excel file
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        error_msg = f"Error reading Excel file: {e}"
        logger.error(error_msg)
        error_logger.error(error_msg)
        return
    
    # Get list of folders to compress
    folders = [f for f in os.listdir(result_dir) 
              if os.path.isdir(os.path.join(result_dir, f))]
    
    if not folders:
        logger.info("No folders found in result directory")
        return
        
    logger.info(f"Found {len(folders)} folders to compress")
    
    # Process each folder
    for folder_name in folders:
        folder_path = os.path.join(result_dir, folder_name)
        zip_path = os.path.join(result_dir, f"{folder_name}_local_processing.zip")
        
        try:
            # Skip if zip already exists
            if os.path.exists(zip_path):
                logger.info(f"Skipping {folder_name}, zip file already exists")
                continue
                
            # Compress the folder
            compress_folder(folder_path, zip_path, folder_path)
            
            # Remove the original folder after successful compression
            shutil.rmtree(folder_path)
            logger.info(f"Compressed {folder_name} to zip")
            
            # Update Excel file
            mask = df['id'] == folder_name
            if any(mask):
                df.loc[mask, 'is_submitted'] = True
                logger.info(f"Updated is_submitted status for {folder_name}")
                
        except Exception as e:
            error_msg = f"Error processing folder {folder_name}: {e}"
            logger.error(error_msg)
            error_logger.error(error_msg)
            failed_items.append(folder_name)
            # If compression fails, don't delete the original folder
            if os.path.exists(zip_path):
                os.remove(zip_path)
    
    # Save the updated Excel file
    try:
        df.to_excel(excel_path, index=False)
        logger.info("Excel file has been updated with submission status")
    except Exception as e:
        error_msg = f"Error saving Excel file: {e}"
        logger.error(error_msg)
        error_logger.error(error_msg)
    
    # Log summary of failures
    if failed_items:
        error_msg = f"\nFailed to process {len(failed_items)} items:\n" + "\n".join(failed_items)
        logger.error(error_msg)
        error_logger.error(error_msg)

if __name__ == "__main__":
    compress_result_folders()
