import pandas as pd
import argparse

def update_excel_data(source_file, target_file):
    """Update target Excel file with data from source Excel file based on matching IDs.

    Args:
        source_file (str): Path to the source Excel file
        target_file (str): Path to the target Excel file that will be updated
    """
    try:
        # Read both Excel files
        source_df = pd.read_excel(source_file)
        target_df = pd.read_excel(target_file)

        # Verify that required columns exist in both files
        required_columns = ['id', 'actual_duration_seconds', 'processing_status']
        for col in required_columns:
            if col not in source_df.columns:
                raise ValueError(f"Column '{col}' not found in source file")
            if col not in target_df.columns:
                raise ValueError(f"Column '{col}' not found in target file")

        # Create a dictionary from source file with id as key
        source_data = source_df.set_index('id')[['actual_duration_seconds', 'processing_status']].to_dict('index')

        # Update values in target dataframe
        updated_count = 0
        for idx, row in target_df.iterrows():
            if row['id'] in source_data:
                target_df.at[idx, 'actual_duration_seconds'] = source_data[row['id']]['actual_duration_seconds']
                target_df.at[idx, 'processing_status'] = source_data[row['id']]['processing_status']
                updated_count += 1

        # Save the updated dataframe back to the target file
        target_df.to_excel(target_file, index=False)
        print(f"Successfully updated {updated_count} rows in {target_file}")

    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Update Excel file with data from another Excel file based on matching IDs')
    parser.add_argument('source_file', help='Path to the source Excel file')
    parser.add_argument('target_file', help='Path to the target Excel file to be updated')
    
    args = parser.parse_args()
    update_excel_data(args.source_file, args.target_file)

if __name__ == "__main__":
    main()
