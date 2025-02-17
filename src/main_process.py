import os
import click
import time
import subprocess
import logging
from datetime import datetime
from core.audio_splitter import split_audio_at_silence
from core.transcribe_chunks import transcribe_chunks
from core.convert_and_clean import convert_chunks_to_wav
from utils.logger_setup import setup_error_logger
from utils.constants import BASE_DATA_FOLDER
from utils.update_actual_duration import update_actual_duration
from utils.update_processing_status import update_processing_status
from utils.compress_results import compress_result_folders

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProcessingStats:
    def __init__(self):
        self.total_files = 0
        self.processed_files = 0
        self.failed_files = []
        self.total_duration = 0
        self.start_time = None
        self.end_time = None
        self.error_logger = setup_error_logger('main_process')
    
    def start(self):
        self.start_time = time.time()
        logger.info("Starting audio processing")
    
    def finish(self):
        self.end_time = time.time()
        logger.info("Finished audio processing")
    
    def add_file(self, file_path, duration_seconds):
        self.total_files += 1
        self.total_duration += duration_seconds
        logger.info(f"Added file {os.path.basename(file_path)} for processing (duration: {duration_seconds:.2f}s)")
    
    def mark_success(self):
        self.processed_files += 1
    
    def mark_failure(self, file_path, error):
        error_msg = f"Failed to process {os.path.basename(file_path)}: {str(error)}"
        self.failed_files.append((file_path, str(error)))
        logger.error(error_msg)
        self.error_logger.error(error_msg)
    
    def print_summary(self):
        processing_time = self.end_time - self.start_time
        success_rate = (self.processed_files / self.total_files * 100) if self.total_files > 0 else 0
        
        summary = [
            "\n=== Processing Summary ===",
            f"Start Time: {datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')}",
            f"End Time: {datetime.fromtimestamp(self.end_time).strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Processing Time: {processing_time:.2f} seconds",
            f"\nFiles Processed: {self.processed_files}/{self.total_files}",
            f"Success Rate: {success_rate:.1f}%",
            f"Total Audio Duration: {self.total_duration:.2f} seconds",
            f"Average Processing Speed: {self.total_duration/processing_time:.2f}x realtime"
        ]
        
        # Log summary
        summary_text = "\n".join(summary)
        logger.info(summary_text)
        
        if self.failed_files:
            failures = ["\nFailed Files:"]
            for file_path, error in self.failed_files:
                failures.append(f"- {os.path.basename(file_path)}: {error}")
            
            failures_text = "\n".join(failures)
            logger.error(failures_text)
            self.error_logger.error(failures_text)
        
        # Print to console as well
        print(summary_text)
        if self.failed_files:
            print(failures_text)

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

def cleanup_temp_files(base_filename):
    """Clean up all temporary files and directories after processing."""
    result_dir = os.path.join(BASE_DATA_FOLDER, 'result', base_filename)
    
    # Find and clean up all temp directories
    for root, dirs, files in os.walk(result_dir):
        if 'temp' in dirs:
            temp_dir = os.path.join(root, 'temp')
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Could not remove temp directory {temp_dir}: {e}")

def process_audio_file(file_path, stats, use_openai=False, split_audio_only=False, transcribe_only=False):
    """Process a single audio file and update statistics."""
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    logger.info(f"\nProcessing {base_filename}...")
    
    try:
        # Get duration for statistics
        duration = get_audio_duration(file_path)
        stats.add_file(file_path, duration)

        if not transcribe_only:
            # Split audio into chunks (pass file path directly)
            logger.info("Splitting audio into chunks...")
            split_audio_at_silence(file_path, base_filename)

            # Convert OGG to WAV and remove OGG files
            logger.info("Converting chunks to WAV format...")
            convert_chunks_to_wav(base_filename)

            if split_audio_only:
                stats.mark_success()
                logger.info(f"Completed processing {base_filename} for split audio only")
                return
        
        # Transcribe chunks (using OGG files)
        logger.info("Transcribing audio chunks...")
        transcribe_chunks(base_filename, use_openai=use_openai)
        
        stats.mark_success()
        logger.info(f"Completed processing {base_filename}")
        
    except Exception as e:
        stats.mark_failure(file_path, e)

def process_directory(source_dir, archive_dir=None, use_openai=False, split_audio_only=False, transcribe_only=False):
    """Process all audio files in the source directory and track statistics."""
    stats = ProcessingStats()
    stats.start()
    
    # Create archive directory if specified
    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)
        logger.info(f"Created archive directory: {archive_dir}")
    
    # Process each audio file
    for filename in sorted(os.listdir(source_dir)):
        if filename.endswith(('.ogg', '.mp3', '.m4a')):
            file_path = os.path.join(source_dir, filename)
            
            # Process the file
            process_audio_file(file_path, stats, use_openai, split_audio_only, transcribe_only)
            
            # Move to archive only if processing was successful and archive_dir is specified
            if archive_dir and file_path not in [f[0] for f in stats.failed_files]:
                archive_path = os.path.join(archive_dir, filename)
                os.rename(file_path, archive_path)
                logger.info(f"Archived {filename}")
    
    stats.finish()
    stats.print_summary()

@click.command()
@click.argument('source_dir', type=click.Path(exists=True))
@click.option('--archive-dir', type=click.Path(), help='Optional directory to move processed files to')
@click.option('--use-openai', is_flag=True, help='Use OpenAI Whisper API instead of DeepInfra')
@click.option('--split-audio-only', is_flag=True, help='Only split audio, do not transcribe')
@click.option('--transcribe-only', is_flag=True, help='Only transcribe audio, do not split')
def main(source_dir, archive_dir, use_openai, split_audio_only, transcribe_only):
    """Process all audio files in the source directory and generate statistics."""
    process_directory(source_dir, archive_dir, use_openai, split_audio_only, transcribe_only)
    update_actual_duration()

    if not split_audio_only:
        update_processing_status(os.path.join(BASE_DATA_FOLDER, 'youtube_videos_submitted.xlsx'))
        compress_result_folders()

if __name__ == '__main__':
    main()
