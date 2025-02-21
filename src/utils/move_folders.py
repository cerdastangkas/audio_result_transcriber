import os
import shutil
import pandas as pd
import argparse
from pathlib import Path

def move_folders(excel_file, source_dir, destination_dir):
    """
    Move folders from source_dir to destination_dir based on matching IDs in excel_file.
    
    Args:
        excel_file (str): Path to Excel file containing IDs
        source_dir (str): Path to source directory containing folders to move
        destination_dir (str): Path to destination directory where folders will be moved
    """
    try:
        # Read the Excel file
        df = pd.read_excel(excel_file)
        
        # Ensure 'id' column exists
        if 'id' not in df.columns:
            raise ValueError("Excel file must contain an 'id' column")
        
        # Convert source and destination to Path objects
        source_path = Path(source_dir)
        dest_path = Path(destination_dir)
        
        # Create destination directory if it doesn't exist
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # Get list of all folders in source directory
        moved_count = 0
        not_found_count = 0
        
        # Convert IDs to strings and store in a set for faster lookup
        id_set = set(str(id_) for id_ in df['id'])
        
        for item in source_path.iterdir():
            if item.is_dir():
                # Extract the ID from the folder name (assuming it's at the start of the name)
                folder_id = item.name.split('_')[0]
                
                if folder_id in id_set:
                    # Create destination folder
                    destination_folder = dest_path / item.name
                    
                    # Move the folder
                    try:
                        shutil.move(str(item), str(destination_folder))
                        print(f"Moved: {item.name} -> {destination_folder}")
                        moved_count += 1
                    except Exception as e:
                        print(f"Error moving {item.name}: {str(e)}")
                else:
                    print(f"No matching ID found for folder: {item.name}")
                    not_found_count += 1
        
        print(f"\nSummary:")
        print(f"Total folders moved: {moved_count}")
        print(f"Folders without matching IDs: {not_found_count}")

    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Move folders based on matching IDs in Excel file')
    parser.add_argument('excel_file', help='Path to Excel file containing IDs')
    parser.add_argument('source_dir', help='Source directory containing folders to move')
    parser.add_argument('destination_dir', help='Destination directory where folders will be moved')
    
    args = parser.parse_args()
    move_folders(args.excel_file, args.source_dir, args.destination_dir)

if __name__ == "__main__":
    main()
