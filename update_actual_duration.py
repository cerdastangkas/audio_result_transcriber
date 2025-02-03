import pandas as pd
import os
from pathlib import Path

def update_actual_duration():
    # Read the Excel file
    excel_path = "data/youtube_videos_submitted.xlsx"
    df = pd.read_excel(excel_path)
    
    # Iterate through each row
    for index, row in df.iterrows():
        video_id = row['id']  # Assuming 'id' is the column name
        transcript_path = f"data/result/{video_id}/{video_id}_transcripts.csv"
        
        if os.path.exists(transcript_path):
            try:
                # Read transcript CSV
                transcript_df = pd.read_csv(transcript_path)
                
                # Calculate total duration
                total_duration = transcript_df['duration_seconds'].sum()
                
                # Update the Excel file
                df.at[index, 'actual_duration_seconds'] = total_duration
            except Exception as e:
                print(f"Error processing {video_id}: {str(e)}")
        else:
            print(f"Transcript file not found for {video_id}")
    
    # Save the updated Excel file
    df.to_excel(excel_path, index=False)
    print("Excel file has been updated with actual durations")

if __name__ == "__main__":
    update_actual_duration()
