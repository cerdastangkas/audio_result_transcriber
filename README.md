# Audio Splitter

A command-line tool to split audio files based on silence detection with configurable minimum and maximum durations.

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Make the script executable (optional):
```bash
chmod +x audio_splitter.py
```

## Usage

Basic usage:
```bash
python audio_splitter.py input_audio_file
```

With options:
```bash
python audio_splitter.py input_audio_file \
    --min-silence-len 1000 \
    --silence-thresh -40 \
    --min-duration 1000 \
    --max-duration 30000 \
    --output-dir output
```

### Options

- `--min-silence-len`: Minimum length of silence (in milliseconds) to split on (default: 1000ms)
- `--silence-thresh`: Silence threshold in dB (default: -40dB)
- `--min-duration`: Minimum duration of each split (in milliseconds) (default: 1000ms)
- `--max-duration`: Maximum duration of each split (in milliseconds) (default: 30000ms)
- `--output-dir`: Output directory for split files (default: 'output')

## Example

To split an audio file with custom parameters:
```bash
python audio_splitter.py my_audio.mp3 --min-silence-len 500 --silence-thresh -45 --min-duration 2000
```

This will create split audio files in the 'output' directory.
