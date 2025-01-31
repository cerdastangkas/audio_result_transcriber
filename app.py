import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import time
from pathlib import Path
import humanize
from datetime import datetime
import threading
import queue
import yt_dlp

# Import our processing modules
from download_youtube import process_excel_file
from update_processing_status import update_processing_status
from compress_results import compress_result_folders
from main_process import process_directory, ProcessingStats

# Load environment variables
load_dotenv()

# Get base data folder from environment
BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER', 'data')

# Make sure the data folders exist
for folder in ['download', 'result', 'archive']:
    os.makedirs(os.path.join(BASE_DATA_FOLDER, folder), exist_ok=True)

# Set page config
st.set_page_config(
    page_title="YouTube Audio Processing",
    page_icon="🎵",
    layout="wide"
)

# Initialize session state for progress
if 'download_progress' not in st.session_state:
    st.session_state.download_progress = {}
if 'current_file' not in st.session_state:
    st.session_state.current_file = None
if 'download_complete' not in st.session_state:
    st.session_state.download_complete = False
if 'download_started' not in st.session_state:
    st.session_state.download_started = False

def progress_hook(d):
    """Progress hook for youtube-dl"""
    if d['status'] == 'downloading':
        video_id = d.get('filename', '').split('/')[-1].split('.')[0]
        total = d.get('total_bytes')
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
        
        if total:
            progress = (downloaded / total) * 100
            st.session_state.download_progress[video_id] = {
                'progress': progress,
                'speed': humanize.naturalsize(speed, binary=True) + '/s' if speed else 'N/A'
            }
            st.session_state.current_file = video_id
    elif d['status'] == 'finished':
        video_id = d.get('filename', '').split('/')[-1].split('.')[0]
        st.session_state.download_progress[video_id] = {
            'progress': 100,
            'speed': 'Complete'
        }

def process_videos_with_progress(excel_path):
    """Process videos with progress tracking"""
    try:
        df = pd.read_excel(excel_path)
        total_videos = len(df)
        
        st.session_state.download_started = True
        st.session_state.download_complete = False
        st.session_state.download_progress = {}
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestaudio[ext=opus]/bestaudio[ext=ogg]/bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'vorbis',
                'preferredquality': '128',
            }],
            'progress_hooks': [progress_hook],
            'outtmpl': os.path.join(BASE_DATA_FOLDER, 'download', '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True
        }
        
        # Process each video
        for _, row in df.iterrows():
            video_id = str(row['id']).strip()
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                st.error(f"Error downloading {video_id}: {str(e)}")
        
        st.session_state.download_complete = True
        
    except Exception as e:
        st.error(f"Error processing videos: {str(e)}")
        st.session_state.download_complete = True

def get_folder_stats():
    """Get statistics about files in different folders."""
    stats = {}
    for folder in ['download', 'result', 'archive']:
        folder_path = os.path.join(BASE_DATA_FOLDER, folder)
        total_size = 0
        file_count = 0
        
        if os.path.exists(folder_path):
            for root, _, files in os.walk(folder_path):
                file_count += len(files)
                total_size += sum(os.path.getsize(os.path.join(root, f)) for f in files)
        
        stats[folder] = {
            'count': file_count,
            'size': humanize.naturalsize(total_size)
        }
    
    return stats

def main():
    st.title("YouTube Audio Processing Dashboard")
    
    # Display folder statistics
    stats = get_folder_stats()
    st.header("Storage Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Download Folder",
            value=f"{stats['download']['count']} files",
            delta=stats['download']['size']
        )
    
    with col2:
        st.metric(
            label="Result Folder",
            value=f"{stats['result']['count']} files",
            delta=stats['result']['size']
        )
    
    with col3:
        st.metric(
            label="Archive Folder",
            value=f"{stats['archive']['count']} files",
            delta=stats['archive']['size']
        )
    
    # Create tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["YouTube Downloads", "Audio Processing", "File Management"])
    
    with tab1:
        # Processing Section
        st.header("Process YouTube Videos")
        
        uploaded_file = st.file_uploader(
            "Upload Excel file containing YouTube IDs",
            type=['xlsx'],
            help="Excel file should contain a column named 'id' with YouTube video IDs"
        )
        
        if uploaded_file:
            # Save the uploaded file
            temp_file = os.path.join(BASE_DATA_FOLDER, uploaded_file.name)
            with open(temp_file, "wb") as f:
                f.write(uploaded_file.getvalue())
                
            # Show file preview
            st.subheader("File Preview")
            df = pd.read_excel(temp_file)
            st.dataframe(df.head())
            
            if st.button("Start Processing", type="primary"):
                # Start processing in a separate thread
                thread = threading.Thread(
                    target=process_videos_with_progress,
                    args=(temp_file,)
                )
                thread.start()
        
        # Display download progress
        if st.session_state.download_started and not st.session_state.download_complete:
            st.header("Download Progress")
            
            # Display current file
            if st.session_state.current_file:
                st.subheader(f"Currently Processing: {st.session_state.current_file}")
            
            # Display progress for all files
            for video_id, progress_data in st.session_state.download_progress.items():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.progress(progress_data['progress'] / 100)
                with col2:
                    st.write(f"Speed: {progress_data['speed']}")
        
        elif st.session_state.download_complete:
            st.success("All downloads completed!")
            if st.button("Clear Progress"):
                st.session_state.download_started = False
                st.session_state.download_progress = {}
                st.session_state.current_file = None
                st.experimental_rerun()
    
    with tab2:
        st.header("Audio Processing")
        
        # Initialize session state for audio processing
        if 'audio_processing_stats' not in st.session_state:
            st.session_state.audio_processing_stats = None
        if 'processing_complete' not in st.session_state:
            st.session_state.processing_complete = False
        
        # Audio Processing Options
        st.subheader("Process Audio Files")
        
        # Source directory selection (download folder by default)
        source_dir = os.path.join(BASE_DATA_FOLDER, 'download')
        archive_dir = os.path.join(BASE_DATA_FOLDER, 'archive')
        
        # Show available audio files
        audio_files = [f for f in os.listdir(source_dir) 
                      if f.endswith(('.ogg', '.mp3', '.m4a', '.wav'))]
        
        if audio_files:
            st.write(f"Found {len(audio_files)} audio files in download folder:")
            for file in audio_files:
                st.text(f"• {file}")
            
            if st.button("Start Audio Processing", type="primary"):
                # Create progress placeholder
                progress_placeholder = st.empty()
                stats_placeholder = st.empty()
                
                try:
                    # Process files and update progress
                    stats = ProcessingStats()
                    stats.start()
                    
                    with progress_placeholder.container():
                        st.write("Processing audio files...")
                        progress_bar = st.progress(0)
                        
                        # Process directory and update progress
                        process_directory(source_dir, archive_dir)
                        
                        stats.finish()
                        progress_bar.progress(100)
                    
                    # Store stats in session state
                    st.session_state.audio_processing_stats = stats
                    st.session_state.processing_complete = True
                    
                    # Show completion message
                    st.success("Audio processing completed!")
                    
                except Exception as e:
                    st.error(f"Error during audio processing: {str(e)}")
        else:
            st.warning("No audio files found in the download folder. Please download some videos first.")
        
        # Display processing statistics if available
        if st.session_state.processing_complete and st.session_state.audio_processing_stats:
            stats = st.session_state.audio_processing_stats
            
            st.subheader("Processing Summary")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Files Processed", f"{stats.processed_files}/{stats.total_files}")
                st.metric("Success Rate", f"{(stats.processed_files / stats.total_files * 100):.1f}%")
            
            with col2:
                st.metric("Total Duration", f"{stats.total_duration:.2f}s")
                processing_time = stats.end_time - stats.start_time
                st.metric("Processing Speed", f"{stats.total_duration/processing_time:.2f}x realtime")
            
            if stats.failed_files:
                st.error("Failed Files:")
                for file_path, error in stats.failed_files:
                    st.text(f"• {os.path.basename(file_path)}: {error}")
    
    with tab3:
        # Status Update Section
        st.header("Update Processing Status")
        status_file = st.file_uploader(
            "Upload Excel file to update status",
            type=['xlsx'],
            key="status_upload",
            help="This will update the processing_status column based on files in download and archive folders"
        )
        
        if status_file:
            temp_status_file = os.path.join(BASE_DATA_FOLDER, status_file.name)
            with open(temp_status_file, "wb") as f:
                f.write(status_file.getvalue())
                
            if st.button("Update Status", type="primary"):
                with st.spinner("Updating status..."):
                    try:
                        update_processing_status(temp_status_file)
                        st.success("Status updated successfully!")
                        # Show updated file
                        st.subheader("Updated File Preview")
                        updated_df = pd.read_excel(temp_status_file)
                        st.dataframe(updated_df)
                    except Exception as e:
                        st.error(f"Error updating status: {str(e)}")
        
        # Compression Section
        st.header("Compress Result Folders")
        
        if st.button("Compress Results", type="primary"):
            with st.spinner("Compressing result folders..."):
                try:
                    compress_result_folders()
                    st.success("Compression completed successfully!")
                    # Refresh stats
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error during compression: {str(e)}")
        
        # File Browser Section
        st.header("File Browser")
        folder_to_browse = st.selectbox(
            "Select folder to browse",
            ['download', 'result', 'archive']
        )
        
        folder_path = os.path.join(BASE_DATA_FOLDER, folder_to_browse)
        if os.path.exists(folder_path):
            files = []
            for root, _, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    size = os.path.getsize(file_path)
                    modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                    files.append({
                        'Name': filename,
                        'Size': humanize.naturalsize(size),
                        'Modified': modified.strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            if files:
                st.dataframe(
                    pd.DataFrame(files),
                    hide_index=True,
                    column_config={
                        'Name': st.column_config.TextColumn('File Name'),
                        'Size': st.column_config.TextColumn('Size'),
                        'Modified': st.column_config.TextColumn('Last Modified')
                    }
                )
            else:
                st.info(f"No files found in {folder_to_browse} folder")

if __name__ == "__main__":
    main()
