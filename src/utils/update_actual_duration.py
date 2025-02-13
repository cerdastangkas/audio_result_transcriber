import pandas as pd
import os
from pathlib import Path

def update_actual_duration():
    # Read the Excel file
    excel_path = "data/youtube_videos_submitted.xlsx"
    df = pd.read_excel(excel_path)
    
    success_count = 0
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
                success_count += 1
                print(f"Successfully updated duration for {video_id}")
            except Exception:
                pass
    
    # Save the updated Excel file
    df.to_excel(excel_path, index=False)
    print(f"\nCompleted: Successfully updated {success_count} videos in the Excel file")

def update_actual_duration_by_id(video_id):
    # Read the Excel file
    excel_path = "data/youtube_videos_submitted.xlsx"
    df = pd.read_excel(excel_path)
    
    # Find the row with the matching video_id
    row = df.loc[df['id'] == video_id]
    
    if not row.empty:
        try:
            transcript_path = f"data/result/{video_id}/{video_id}_transcripts.csv"
            if os.path.exists(transcript_path):
                # Read transcript CSV
                transcript_df = pd.read_csv(transcript_path)
                
                # Calculate total duration
                total_duration = transcript_df['duration_seconds'].sum()
                
                # Update the Excel file
                df.loc[df['id'] == video_id, 'actual_duration_seconds'] = total_duration
                df.to_excel(excel_path, index=False)
                print(f"Successfully updated duration for {video_id}")
            else:
                print(f"Transcript file not found for {video_id}")
        except Exception:
            pass
    else:
        print(f"Video ID {video_id} not found in Excel file")


if __name__ == "__main__":
    update_actual_duration()
