import os
import click
from audio_splitter import split_audio_at_silence
from transcribe_chunks import transcribe_chunks
from convert_and_clean import convert_chunks_to_wav
from pydub import AudioSegment

# Main function to process audio file

def process_audio_file(input_file):
    # Extract base filename without extension
    base_filename = os.path.splitext(os.path.basename(input_file))[0]
    
    # Load audio file
    audio = AudioSegment.from_file(input_file)
    
    # Split audio into chunks
    print("Splitting audio into chunks...")
    split_audio_at_silence(audio, base_filename)
    
    # Transcribe chunks
    print("Transcribing audio chunks...")
    transcribe_chunks(base_filename)

    # Convert audio chunks to WAV and clean up
    print("Converting audio chunks to WAV and cleaning up...")
    convert_chunks_to_wav(base_filename)

    print("Process complete!")

@click.command()
@click.argument('input_file', type=click.Path(exists=True))
def main(input_file):
    """Process the audio file by splitting it into chunks and transcribing them."""
    process_audio_file(input_file)

if __name__ == '__main__':
    main()
