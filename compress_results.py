import os
import zipfile
from dotenv import load_dotenv
import logging
from tqdm import tqdm
import shutil

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
    """Compress each folder under the result directory."""
    result_dir = os.path.join(BASE_DATA_FOLDER, 'result')
    
    if not os.path.exists(result_dir):
        logger.error(f"Result directory not found: {result_dir}")
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
        zip_path = os.path.join(result_dir, f"{folder_name}.zip")
        
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
                
        except Exception as e:
            logger.error(f"Error processing folder {folder_name}: {e}")
            # If compression fails, don't delete the original folder
            if os.path.exists(zip_path):
                os.remove(zip_path)
            continue

if __name__ == "__main__":
    compress_result_folders()
