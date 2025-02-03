# Audio Processing and Transcription Pipeline

A robust Python-based pipeline for processing large audio files, including splitting based on silence detection, format conversion, and transcription using the DeepInfra Whisper API.

## Features

- **Audio Splitting**: Intelligent silence-based audio splitting using FFmpeg
- **Parallel Processing**: Optimized performance with multi-threaded operations
- **Format Conversion**: Automatic conversion from OGG to WAV format
- **Transcription**: Audio transcription using DeepInfra's Whisper API
- **Progress Tracking**: Real-time progress bars for long-running operations
- **Error Handling**: Robust error handling and reporting

## Prerequisites

- Python 3.8 or higher
- FFmpeg installed on your system
- DeepInfra API key

### System Dependencies

```bash
# For macOS (using Homebrew)
brew install ffmpeg

# For Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg
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

- `main_process.py`: Main entry point for the audio processing pipeline
- `audio_splitter.py`: Handles audio file splitting using silence detection
- `convert_and_clean.py`: Converts audio formats and cleans up temporary files
- `transcribe_chunks.py`: Manages audio transcription using DeepInfra API
- `requirements.txt`: Python package dependencies
- `.env`: Configuration for API keys and settings

## Usage

1. Place your audio files in the `source` directory.

2. Run the main processing script:

    ```bash
    python main_process.py [filename]
    ```

    Example:

    ```bash
    python main_process.py my_audio_file.ogg
    ```

3. The script will:
   - Split the audio file based on silence detection
   - Convert the chunks to WAV format
   - Transcribe each chunk using DeepInfra's Whisper API
   - Generate a CSV file with transcriptions

### Output Structure

```
result/
└── [filename]/
    ├── split/
    │   ├── [filename]_segment_000.wav
    │   ├── [filename]_segment_001.wav
    │   └── ...
    └── [filename]_transcripts.csv
```

### CSV Format

The generated CSV file contains:

- `audio_file`: Path to the audio segment
- `start_time_seconds`: Start time of the segment
- `end_time_seconds`: End time of the segment
- `duration_seconds`: Duration of the segment
- `text`: Transcribed text

## Configuration

You can adjust various parameters in the scripts:

- `min_silence_len`: Minimum length of silence (in ms)
- `silence_thresh`: Silence threshold in dB
- `min_duration`: Minimum segment duration
- `max_duration`: Maximum segment duration

## Error Handling

- Failed operations are logged and reported
- Original files are preserved until successful conversion
- Detailed error messages for debugging

## Performance Optimization

The pipeline is optimized for performance:

- Parallel processing for file operations
- Direct FFmpeg usage for audio processing
- Efficient memory usage with streaming operations
- Progress tracking for long-running tasks

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
