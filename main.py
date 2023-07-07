import RPi.GPIO as GPIO
import atexit
import boto3
import noisereduce as nr
import numpy as np
import os
import pyaudio
import pygame.mixer
import soundfile as sf
import sys
import threading
import time
import wave
from scipy.io import wavfile
from datetime import datetime
from scipy.signal import iirnotch, lfilter

# Set the chunk size, sample format, channel, sample rate, and duration
CHUNK = 4*1024
# Chunk size for noise reduction, each chunk will have max 100kb size
NR_CHUNK = 100000
FORMAT = pyaudio.paInt24
CHANNELS = 1
RATE = 48000
RECORD_SECONDS = 10
USB_DEVICE_INDEX = 1

GPIO.setmode(GPIO.BOARD)
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

isOpen = threading.Event()
frames = []

# Initialize pygame mixer
pygame.mixer.init()

# Create a PyAudio instance
p = pyaudio.PyAudio()

# Function to check if the desired device is available
def is_device_available():
    device_count = p.get_device_count()
    for i in range(device_count):
        device_info = p.get_device_info_by_index(i)
        if (device_info['index'] == USB_DEVICE_INDEX and 
            device_info['maxInputChannels'] >= CHANNELS):
            return True
    return False

while not is_device_available():
    if tries <= 0:
        print("Error: The correct audio device is not available after several attempts.")
        sys.exit(1)  # exit the program with an error code

    print("Waiting for the correct audio device to be available...")
    time.sleep(1)  # wait for 1 second before checking again
    tries -= 1  # decrement the number of tries

print("Audio device found")

# Define the stream variable in the global scope
stream = None

global isPlaying
isPlaying = False

def play_sound(filename):
    global isPlaying
    try:
        if not pygame.mixer.music.get_busy(): # Check if any music stream is playing
           pygame.mixer.music.load(filename) # Load the sound file
           pygame.mixer.music.play() # Play the sound file
           isPlaying = True
           print(f'Successfully started playing {filename}')
    except Exception as e:
        print(f'Failed to play {filename} due to {e}')

def stop_sound():
    global isPlaying
    if pygame.mixer.music.get_busy(): # Check if any music stream is playing
        pygame.mixer.music.stop() # Stop playing the sound file
        isPlaying = False
        print('Stopped playing sound.')

def exit_handler():
    global stream
    global p
    
    print("Gracefully Exiting")
    if stream is not None:
        if stream.is_active():
            stream.stop_stream()
        stream.close()

    # Terminate the PortAudio interface
    p.terminate()
    GPIO.cleanup()

# Register the exit handler to be called when the program is about to exit
atexit.register(exit_handler)

def create_notch_filter(sample_rate, frequency, Q):
    """Creates a notch (bandstop) filter at the given frequency."""
    nyquist_rate = sample_rate / 2.0
    normalized_frequency = frequency / nyquist_rate
    b, a = iirnotch(normalized_frequency, Q)
    return b, a

def apply_notch_filter(data, sample_rate, frequency=60, Q=30):
    """Applies a notch filter to the data."""
    b, a = create_notch_filter(sample_rate, frequency, Q)
    filtered_data = lfilter(b, a, data)
    return filtered_data

def process_and_upload(frames, timestamp):
    # Save the recorded data to a WAV file
    WAVE_OUTPUT_FILENAME = f"output-{timestamp}.wav"

    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    # Read and convert the 24-bit audio to 16-bit
    data, rate = sf.read(WAVE_OUTPUT_FILENAME, dtype='float32')
    # We'll now process the audio data in chunks using the noisereduce library
    reduced_noise_chunks = []
    for i in range(0, len(data), NR_CHUNK):
        chunk_data = data[i:i + NR_CHUNK]

        # replace 'chunk_data' with the data chunk you want to filter
        filetered_chunk_data = apply_notch_filter(chunk_data, RATE)

        # And subsequently replace 'reduced_noise_chunk' with the filtered data before noise reduction
        reduced_noise_chunk = nr.reduce_noise(y=filetered_chunk_data, sr=RATE)
            
        # Append reduced noise chunk to list
        reduced_noise_chunks.append(reduced_noise_chunk)

    # Concatenate all the processed chunks
    reduced_noise = np.concatenate(reduced_noise_chunks)
    reduced_filename = f"reduced-{timestamp}.wav"

    # Save the result (Optionally use soundfile library if you want to retain the original file properties)
    sf.write(reduced_filename, reduced_noise, rate)

    # If the original file exists, delete it
    if os.path.exists(WAVE_OUTPUT_FILENAME):
        os.remove(WAVE_OUTPUT_FILENAME)
        print(f'Successfully deleted local file {WAVE_OUTPUT_FILENAME}')

    # Create a session using your AWS credentials
    s3 = boto3.resource('s3')

    # Name of the S3 bucket
    bucket_name = 'audio-guestbook'

    # Try to upload the .wav file to the S3 bucket
    try:
        s3.Bucket(bucket_name).upload_file(reduced_filename, reduced_filename)
        print(f'Successfully uploaded {reduced_filename} to {bucket_name}')

        # If the upload was successful, delete the file
        if os.path.exists(reduced_filename):
            os.remove(reduced_filename)
            print(f'Successfully deleted local file {reduced_filename}')

    except Exception as e:
        print(f'Failed to upload {reduced_filename} to {bucket_name} due to {e}')

def button_callback(channel):
    global isOpen
    global frames
    global stream
    global p

    # When the button is pressed, start recording
    if GPIO.input(10): # if pin is HIGH
        # Get the current timestamp and format it as a string
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        isOpen.set()
        threading.Thread(target=play_sound, args=('welcome.wav',)).start()
        print("Recording started")

        # Open the stream
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK,
                        input_device_index=USB_DEVICE_INDEX)

        # Start the stream
        stream.start_stream()

        # Start recording
        while isOpen.is_set() and GPIO.input(10):
            data = stream.read(CHUNK)
            frames.append(data)

        isOpen.clear()
        print("Recording stopped")

       # Stop and close the stream
        stream.stop_stream()
        stream.close()
        stream = None

        # Start a new thread to process and upload the recording
        threading.Thread(target=process_and_upload, args=(frames, timestamp)).start()

        frames = []

        if isPlaying:
            stop_sound()

# Use BOTH edge detection and increase bouncetime
GPIO.add_event_detect(10, GPIO.BOTH, callback=button_callback, bouncetime=10)

print("Listening for GPIO.BOTH event")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Program stopped by user")