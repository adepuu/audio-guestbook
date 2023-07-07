import wave
import time
import soundfile as sf
import pyaudio
import os
import numpy as np
import noisereduce as nr
import boto3
import atexit
import RPi.GPIO as GPIO
import threading
from scipy.io import wavfile
from datetime import datetime

# Set the chunk size, sample format, channel, sample rate, and duration
CHUNK = 4*1024
FORMAT = pyaudio.paInt24
CHANNELS = 1
RATE = 48000
RECORD_SECONDS = 10
USB_DEVICE_INDEX = 1



GPIO.setmode(GPIO.BOARD)
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

isOpen = threading.Event()
frames = []

# Create a PyAudio instance
p = pyaudio.PyAudio()

# Define the stream variable in the global scope
stream = None

def exit_handler():
    global stream
    global p
    
    print("Gracefully Exiting")
    if stream.is_active():
        stream.stop_stream()
    stream.close()

    # Terminate the PortAudio interface
    p.terminate()
    GPIO.cleanup()

# Register the exit handler to be called when the program is about to exit
atexit.register(exit_handler)

def process_and_upload(frames, timestamp):
    # Save the recorded data to a WAV file
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
    for i in range(0, len(data), CHUNK):
        chunk_data = data[i:i + CHUNK]

        # Perform noise reduction on the chunk
        reduced_noise_chunk = nr.reduce_noise(y=chunk_data, sr=rate)
            
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
        WAVE_OUTPUT_FILENAME = f"output-{timestamp}.wav"
        
        isOpen.set()
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
            print("recording ...")
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

# Use BOTH edge detection and increase bouncetime
GPIO.add_event_detect(10, GPIO.BOTH, callback=button_callback, bouncetime=10)

print("Listening for GPIO.BOTH event")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Program stopped by user")