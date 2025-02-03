import os
import logging
from datetime import datetime

def setup_error_logger(process_name):
    """
    Setup a file logger for error tracking.
    
    Args:
        process_name (str): Name of the process for the log file
        
    Returns:
        logging.Logger: Configured logger instance
    """
    error_logger = logging.getLogger(f'error_logger_{process_name}')
    error_logger.setLevel(logging.ERROR)
    
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create log file with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'{process_name}_failures_{timestamp}.log')
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.ERROR)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    error_logger.addHandler(file_handler)
    
    return error_logger
