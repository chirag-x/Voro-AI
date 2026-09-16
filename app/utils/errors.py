class VoroError(Exception):
    """Base exception for all Voro application errors."""
    pass

class ConfigError(VoroError):
    """Raised when there is a configuration error."""
    pass

class AudioError(VoroError):
    """Raised when there is a general audio error."""
    pass

class DeviceError(AudioError):
    """Raised when there is an issue with an audio device."""
    pass

class ApplicationError(VoroError):
    """Raised for general application logic errors."""
    pass
