# Audio Processing and Transcription Pipeline

A robust Python-based pipeline for processing large audio files, including splitting based on silence detection, transcription using the DeepInfra Whisper API, and format conversion to WAV. The pipeline is optimized for performance with parallel processing and efficient memory usage.

## Features

- **Audio Splitting**: Intelligent silence-based audio splitting using FFmpeg
- **Parallel Processing**: Multi-threaded operations for both splitting and transcription
- **Transcription**: Audio transcription using DeepInfra's Whisper API or OpenAI Whisper API
- **Format Handling**: 
  - Processes OGG files for transcription
  - Converts to WAV format after transcription
  - Automatic cleanup of temporary files
- **Progress Tracking**: Real-time progress bars for all operations
- **Error Handling**: Comprehensive error logging and recovery

## Prerequisites

- Python 3.8 or higher
- FFmpeg installed on your system
- DeepInfra API key

### System Dependencies

```bash
# For macOS (using Homebrew)
brew install ffmpeg

# For Ubuntu/Debian
sudo apt-get update
sudo apt-get install ffmpeg
```

## Installation

1. Clone the repository:
```bash
git clone git@github.com:cerdastangkas/audio_result_transcriber.git
cd audio_result_transcriber
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp env.example .env
```
Edit `.env` and add your DeepInfra API key.

## Project Structure

```
src/
├── core/
│   ├── audio_splitter.py     # Audio splitting with silence detection
│   ├── convert_and_clean.py  # Audio format conversion and cleanup
│   └── transcribe_chunks.py  # Audio transcription handling
├── utils/
│   ├── compress_results.py   # Results compression utilities
│   ├── download_youtube.py   # YouTube download functionality
│   ├── logger_setup.py       # Logging configuration
│   └── constants.py          # Shared constants and settings
├── main_process.py          # Main pipeline orchestration
└── requirements.txt         # Python dependencies

data/
├── source/                  # Input audio files
├── result/                  # Processed results
└── silence_points/          # Silence detection data
```

## Command-Line Operations

### 1. Process Audio Files
Split audio files into chunks and transcribe them using OpenAI Whisper API:
```bash
python src/main_process.py data/download --archive-dir data/archive --use-openai
```
Options:
- `--archive-dir`: Directory to move processed files to
- `--use-openai`: Use OpenAI's Whisper API instead of DeepInfra

### 2. Download YouTube Videos
Download videos from a list in Excel:
```bash
python src/utils/download_youtube.py data/youtube_videos_submitted.xlsx
```
The Excel file should contain video IDs and other metadata for processing.

### 3. Update Duration Data
Update the actual duration information for processed files:
```bash
python src/utils/update_actual_duration.py
```

### 4. Update Processing Status
Update the processing status in the Excel tracking file:
```bash
python src/utils/update_processing_status.py data/youtube_videos_submitted.xlsx
```

### 5. Compress Results
Compress processed folders to save space:
```bash
python src/utils/compress_results.py
```

### Processing Flow
1. Download videos using the Excel list
2. Process the audio files with OpenAI transcription
3. Update duration data in tracking files
4. Update processing status in Excel
5. Compress results for storage

### Output Structure

```
data/
├── result/
│   └── [video_id]/
│       ├── split/
│       │   ├── [video_id]_segment_000.wav
│       │   ├── [video_id]_segment_001.wav
│       │   └── ...
│       └── [video_id]_transcripts.csv
└── silence_points/
    └── [video_id]_silence_points.json
```

### Output Files

1. **Transcription CSV** (`[video_id]_transcripts.csv`):
   - `audio_file`: Path to the audio segment
   - `start_time_seconds`: Start time in original audio
   - `end_time_seconds`: End time in original audio
   - `duration_seconds`: Segment duration
   - `text`: Transcribed text

2. **Silence Points** (`[video_id]_silence_points.json`):
   - Detailed information about detected silence points
   - Segment timing and duration data
   - Processing parameters used
- `duration_seconds`: Duration of the segment
- `text`: Transcribed text

## Run in Background

1. Run main_process.py in the background using nohup
2. Redirect all output (both stdout and stderr) to processing.log
3. Save the process ID to process.pid for easy management
4. Provide helpful feedback about how to:
   - Check the progress: tail -f processing`.log
   - Stop the process: kill $(cat process.pid)

### Command-Line Usage
## staging
Process started with PID: 4153823
Output is being logged to: processing.log
To check the progress, use: tail -f processing.log
To stop the process, use: kill 4153823

## Lukman
Process started with PID: 2245747
Output is being logged to: processing.log
To check the progress, use: tail -f processing.log
To stop the process, use: kill 2245747

## kevin
Process started with PID: 887110
Output is being logged to: processing.log
To check the progress, use: tail -f processing.log
To stop the process, use: kill 887110

## download muslim
Process started with PID: 1555719
Output is being logged to: processing.log
To check the progress, use: tail -f processing.log
To stop the process, use: kill 1555719

## Configuration

### Environment Variables (.env)
```bash
BASE_DATA_FOLDER=data           # Base directory for all data
DEEPINFRA_API_KEY=your_key     # DeepInfra API key
OPENAI_API_KEY=your_key        # Optional: OpenAI API key
```

### Adjustable Parameters

1. **Audio Splitting** (audio_splitter.py):
   - `min_silence_len`: Minimum silence length (default: 700ms)
   - `silence_thresh`: Silence threshold (default: -35dB)
   - `min_duration`: Minimum segment length (default: 2s)
   - `max_duration`: Maximum segment length (default: 15s)

2. **Transcription** (transcribe_chunks.py):
   - `model`: Whisper model to use (default: 'openai/whisper-large-v3')
   - `use_openai`: Whether to use OpenAI API (default: False)  

## Process Flow

1. **Audio Splitting**:
   - Detect silence points using FFmpeg
   - Split audio into optimal chunks (2-15 seconds)
   - Save timing information in silence_points.json

2. **Transcription**:
   - Process OGG chunks in parallel
   - Use DeepInfra or OpenAI Whisper API
   - Save transcriptions with timing data

3. **Format Conversion**:
   - Convert OGG chunks to WAV format
   - Remove original OGG files
   - Clean up temporary directories

## Error Handling

- Comprehensive logging with error details
- Automatic retry for API failures
- Progress preservation on interruption
- Failed files tracking for review

## Performance Features

- Multi-threaded processing for:
  - Audio splitting
  - Transcription
  - Format conversion
- Progress bars for all operations
- Memory-efficient streaming operations
- Parallel API requests with rate limiting

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
