from enum import Enum, auto

class ApplicationState(Enum):
    STARTING = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()
