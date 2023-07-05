import boto3
import os
import pyaudio
import wave

# Set the chunk size, sample format, channel, sample rate, and duration
CHUNK = 4*1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output.wav"
USB_DEVICE_INDEX = 1

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

# Create a session using your AWS credentials
s3 = boto3.resource('s3')

# Name of the S3 bucket
bucket_name = 'your-bucket-name'

# Try to upload the file to the S3 bucket
try:
    s3.Bucket(bucket_name).upload_file(WAVE_OUTPUT_FILENAME, WAVE_OUTPUT_FILENAME)
    print(f'Successfully uploaded {WAVE_OUTPUT_FILENAME} to {bucket_name}')
    
    # If the upload was successful, delete the file
    if os.path.exists(WAVE_OUTPUT_FILENAME):
        os.remove(WAVE_OUTPUT_FILENAME)
        print(f'Successfully deleted local file {WAVE_OUTPUT_FILENAME}')
    
except Exception as e:
    print(f'Failed to upload {WAVE_OUTPUT_FILENAME} to {bucket_name} due to {e}')
    # If the upload failed, the file is not deleted and you can retry the upload later