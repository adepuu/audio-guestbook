import boto3
import os
import pyaudio
import wave
from datetime import datetime
import soundfile as sf
import numpy as np
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