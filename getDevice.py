import pyaudio

p = pyaudio.PyAudio()
for index in range(p.get_device_count()): 
    desc = p.get_device_info_by_index(index)
    if 'usb' in desc['name'].lower():
        print('DEVICE: %s  INDEX:  %s  RATE:  %s ' %  (desc['name'], index,  int(desc['defaultSampleRate'])))
