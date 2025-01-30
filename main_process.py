import os
import click
import time
import subprocess
from datetime import datetime
from audio_splitter import split_audio_at_silence
from transcribe_chunks import transcribe_chunks
from convert_and_clean import convert_chunks_to_wav
from pydub import AudioSegment

class ProcessingStats:
    def __init__(self):
        self.total_files = 0
        self.processed_files = 0
        self.failed_files = []
        self.total_duration = 0
        self.start_time = None
        self.end_time = None
    
    def start(self):
        self.start_time = time.time()
    
    def finish(self):
        self.end_time = time.time()
    
    def add_file(self, file_path, duration_seconds):
        self.total_files += 1
        self.total_duration += duration_seconds
    
    def mark_success(self):
        self.processed_files += 1
    
    def mark_failure(self, file_path, error):
        self.failed_files.append((file_path, str(error)))
    
    def print_summary(self):
        processing_time = self.end_time - self.start_time
        success_rate = (self.processed_files / self.total_files * 100) if self.total_files > 0 else 0
        
        print("\n=== Processing Summary ===")
        print(f"Start Time: {datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"End Time: {datetime.fromtimestamp(self.end_time).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Processing Time: {processing_time:.2f} seconds")
        print(f"\nFiles Processed: {self.processed_files}/{self.total_files}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Total Audio Duration: {self.total_duration:.2f} seconds")
        print(f"Average Processing Speed: {self.total_duration/processing_time:.2f}x realtime")
        
        if self.failed_files:
            print("\nFailed Files:")
            for file_path, error in self.failed_files:
                print(f"- {os.path.basename(file_path)}: {error}")

def get_audio_duration(file_path):
    """Get audio duration using FFmpeg."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error getting duration: {e.stderr}")

def process_audio_file(file_path, stats):
    """Process a single audio file and update statistics."""
    try:
        # Extract base filename without extension
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        print(f"\nProcessing {base_filename}...")
        
        # Get duration for statistics
        duration = get_audio_duration(file_path)
        stats.add_file(file_path, duration)
        
        # Split audio into chunks (pass file path directly)
        print("Splitting audio into chunks...")
        split_audio_at_silence(file_path, base_filename)
        
        # Transcribe chunks
        print("Transcribing audio chunks...")
        transcribe_chunks(base_filename)
        
        # Convert chunks to wav format
        print("Converting chunks to wav format...")
        convert_chunks_to_wav(base_filename)
        
        stats.mark_success()
        print(f"Completed processing {base_filename}")
        
    except Exception as e:
        stats.mark_failure(file_path, e)
        print(f"Error processing {file_path}: {str(e)}")

def process_directory(source_dir, archive_dir=None):
    """Process all audio files in the source directory and track statistics."""
    stats = ProcessingStats()
    stats.start()
    
    # Create archive directory if specified
    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)
    
    # Process each audio file
    for filename in sorted(os.listdir(source_dir)):
        if filename.endswith(('.ogg', '.mp3')):
            file_path = os.path.join(source_dir, filename)
            
            # Process the file
            process_audio_file(file_path, stats)
            
            # Move to archive only if processing was successful and archive_dir is specified
            if archive_dir and file_path not in [f[0] for f in stats.failed_files]:
                archive_path = os.path.join(archive_dir, filename)
                os.rename(file_path, archive_path)
                print(f"Archived {filename}")
    
    stats.finish()
    stats.print_summary()

@click.command()
@click.argument('source_dir', type=click.Path(exists=True))
@click.option('--archive-dir', type=click.Path(), help='Optional directory to move processed files to')
def main(source_dir, archive_dir):
    """Process all audio files in the source directory and generate statistics."""
    process_directory(source_dir, archive_dir)

if __name__ == '__main__':
    main()
