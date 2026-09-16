import sounddevice as sd
from typing import List, Dict, Optional
from app.utils.errors import DeviceError

class AudioDeviceManager:
    """
    Manages discovery and selection of audio input devices.
    """
    def list_input_devices(self) -> List[Dict]:
        """Returns a list of available input devices."""
        try:
            devices = sd.query_devices()
            input_devices = []
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': d['name'],
                        'channels': d['max_input_channels'],
                        'default_samplerate': d['default_samplerate']
                    })
            return input_devices
        except Exception as e:
            raise DeviceError(f"Failed to query audio devices: {e}")

    def get_default_input_device(self) -> Optional[Dict]:
        """Returns the default input device."""
        try:
            default_input_index = sd.default.device[0]
            if default_input_index is not None and default_input_index >= 0:
                devices = sd.query_devices()
                d = devices[default_input_index]
                return {
                    'index': default_input_index,
                    'name': d['name'],
                    'channels': d['max_input_channels'],
                    'default_samplerate': d['default_samplerate']
                }
            return None
        except Exception as e:
            raise DeviceError(f"Failed to get default input device: {e}")
