import pyaudio

p = pyaudio.PyAudio()

print("\n--- Audio Devices ---")
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')

# PERF-041: Avoid redundant device info lookups
for i in range(0, numdevices):
    device_info = p.get_device_info_by_host_api_device_index(0, i)
    if device_info.get('maxInputChannels') > 0:
        name = device_info.get('name')
        print(f"Device ID {i}: {name}")

p.terminate()
