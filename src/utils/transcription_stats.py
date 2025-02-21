import os
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TranscriptionStats:
    """Class to track and record transcription statistics."""
    
    def __init__(self, base_filename):
        """Initialize transcription statistics tracker.
        
        Args:
            base_filename (str): Base filename for the transcription process
        """
        self.base_filename = base_filename
        self.start_time = None
        self.end_time = None
        self.total_segments = 0
        self.successful_segments = 0
        self.failed_segments = 0
        self.total_duration = 0.0
        self.successful_duration = 0.0
        self.failed_segments_details = []
        self.api_errors = {}
        self.processing_time = 0.0
        self.average_segment_duration = 0.0
        self.average_processing_time_per_segment = 0.0
        
    def start(self):
        """Start tracking transcription process."""
        self.start_time = datetime.now()
        
    def finish(self):
        """Finish tracking transcription process and calculate final statistics."""
        self.end_time = datetime.now()
        self.processing_time = (self.end_time - self.start_time).total_seconds()
        
        if self.successful_segments > 0:
            self.average_segment_duration = self.successful_duration / self.successful_segments
            self.average_processing_time_per_segment = self.processing_time / self.successful_segments
            
    def add_successful_transcription(self, file_path, duration):
        """Record a successful transcription.
        
        Args:
            file_path (str): Path to the transcribed file
            duration (float): Duration of the audio segment in seconds
        """
        self.successful_segments += 1
        self.successful_duration += duration
        
    def add_failed_transcription(self, file_path, error):
        """Record a failed transcription.
        
        Args:
            file_path (str): Path to the failed file
            error (str): Error message
        """
        self.failed_segments += 1
        self.failed_segments_details.append({
            'file': os.path.basename(file_path),
            'error': str(error)
        })
        
        # Track API error types
        error_type = str(error).split(':')[0] if ':' in str(error) else str(error)
        self.api_errors[error_type] = self.api_errors.get(error_type, 0) + 1
        
    def set_total_segments(self, total):
        """Set the total number of segments to be processed.
        
        Args:
            total (int): Total number of segments
        """
        self.total_segments = total
        
    def save_stats(self, output_dir):
        """Save statistics to a JSON file.
        
        Args:
            output_dir (str): Directory to save the statistics file
        """
        stats = {
            'base_filename': self.base_filename,
            'timestamp': datetime.now().isoformat(),
            'total_segments': self.total_segments,
            'successful_segments': self.successful_segments,
            'failed_segments': self.failed_segments,
            'total_duration': self.total_duration,
            'successful_duration': self.successful_duration,
            'processing_time_seconds': self.processing_time,
            'average_segment_duration': self.average_segment_duration,
            'average_processing_time_per_segment': self.average_processing_time_per_segment,
            'success_rate': (self.successful_segments / self.total_segments * 100) if self.total_segments > 0 else 0,
            'api_errors': self.api_errors,
            'failed_segments_details': self.failed_segments_details
        }
        
        # Create stats directory if it doesn't exist
        stats_dir = os.path.join('data', 'stats')
        os.makedirs(stats_dir, exist_ok=True)
        
        # Save stats to JSON file
        stats_file = os.path.join(stats_dir, f'{self.base_filename}_transcription_stats.json')
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
            
        logger.info(f"Transcription statistics saved to {stats_file}")
        
    def print_summary(self):
        """Print a summary of the transcription statistics."""
        logger.info("\nTranscription Statistics Summary:")
        logger.info(f"Total segments processed: {self.total_segments}")
        logger.info(f"Successfully transcribed: {self.successful_segments}")
        logger.info(f"Failed transcriptions: {self.failed_segments}")
        logger.info(f"Total processing time: {self.processing_time:.2f} seconds")
        logger.info(f"Average segment duration: {self.average_segment_duration:.2f} seconds")
        logger.info(f"Average processing time per segment: {self.average_processing_time_per_segment:.2f} seconds")
        
        if self.api_errors:
            logger.info("\nAPI Errors Summary:")
            for error_type, count in self.api_errors.items():
                logger.info(f"{error_type}: {count} occurrences")
