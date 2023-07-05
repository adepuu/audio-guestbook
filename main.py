import boto3
import os
import pyaudio
import wave
from datetime import datetime
import noisereduce as nr
from scipy.io import wavfile

# MIC ----
# Hijau - Biru
# Hitam - Ungu

# Earpiece ----
#
#

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

# Create a PyAudio instance
p = pyaudio.PyAudio()

# Open a stream
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=USB_DEVICE_INDEX)  # replace with your device index

print("* recording")

# Read and store audio data in a list
frames = []

for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)

print("* done recording")

# Stop and close the stream
stream.stop_stream()
stream.close()

# Terminate the PortAudio interface
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

# Create a session using your AWS credentials
s3 = boto3.resource('s3')

# Name of the S3 bucket
bucket_name = 'audio-guestbook'

# Try to upload all .wav files in the current directory to the S3 bucket
for filename in os.listdir('.'):
    if filename.endswith('.wav'):
        try:
            s3.Bucket(bucket_name).upload_file(filename, filename)
            print(f'Successfully uploaded {filename} to {bucket_name}')
            
            # If the upload was successful, delete the file
            if os.path.exists(filename):
                os.remove(filename)
                print(f'Successfully deleted local file {filename}')
        
        except Exception as e:
            print(f'Failed to upload {filename} to {bucket_name} due to {e}')
            # If the upload failed, the file is not deleted and you can retry the upload later
