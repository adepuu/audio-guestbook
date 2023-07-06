import boto3
import os
import pyaudio
import wave
from datetime import datetime
import noisereduce as nr
from scipy.io import wavfile
import RPi.GPIO as GPIO
import atexit

# Set the chunk size, sample format, channel, sample rate, and duration
CHUNK = 4*1024
FORMAT = pyaudio.paInt24
CHANNELS = 1
RATE = 48000
RECORD_SECONDS = 10
USB_DEVICE_INDEX = 1

# Get the current timestamp and format it as a string
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
WAVE_OUTPUT_FILENAME = f"output-{timestamp}.wav"

GPIO.setmode(GPIO.BOARD)
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

isOpen = False
frames = []

# Create a PyAudio instance
p = pyaudio.PyAudio()

# Define the stream variable in the global scope
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=USB_DEVICE_INDEX)

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

def button_callback(channel):
    global isOpen
    global frames
    global stream

    # When the button is pressed, start recording
    if GPIO.input(10): # if pin is HIGH
        isOpen = True
        print("Recording started")

        # Start the stream
        stream.start_stream()

        # Start recording
        while isOpen:
            data = stream.read(CHUNK)
            frames.append(data)

    # When the button is released, stop recording
    else: # if pin is LOW
        isOpen = False
        print("Recording stopped")

        # Stop and close the stream
        stream.stop_stream()

        p.terminate()

        # Save the recorded data to a WAV file
        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        # Load the recorded audio
        rate, data = wavfile.read(WAVE_OUTPUT_FILENAME)

        # Perform noise reduction
        reduced_noise = nr.reduce_noise(y=data, sr=rate)

        # Save the noise-reduced audio to a new WAV file
        reduced_filename = f"reduced-{timestamp}.wav"
        wavfile.write(reduced_filename, rate, reduced_noise.astype(data.dtype))

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
        frames = []

# Use BOTH edge detection and increase bouncetime
GPIO.add_event_detect(10, GPIO.BOTH, callback=button_callback, bouncetime=300)