from abc import ABC, abstractmethod

class Lifecycle(ABC):
    """
    Interface for components that have a defined lifecycle.
    """
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the component (allocate resources, setup)."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the component's operation."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the component."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up resources before termination."""
        pass
