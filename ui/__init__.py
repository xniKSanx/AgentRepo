"""UI package for the AI Warehouse Game Runner.

Provides the ``ScreenId`` enum for typed screen routing and the
``Screen`` abstract base class that all screen controllers implement.
"""

from enum import Enum, auto
from abc import ABC, abstractmethod


class ScreenId(Enum):
    """Typed identifiers for every screen in the application."""
    OPENING = auto()
    SINGLE_SETUP = auto()
    MAP_BUILDER = auto()
    BATCH_SETUP = auto()
    GAME = auto()
    BATCH = auto()
    FILE_SELECT = auto()
    REPLAY = auto()


class Screen(ABC):
    """Interface that every screen controller must implement.

    Lifecycle:
        on_enter  -> (handle_event | update | draw)* -> on_exit
    """

    @abstractmethod
    def handle_event(self, event):
        """Process a pygame event.

        Returns ``None`` to stay on this screen, or a transition signal:
        - ``ScreenId``              – navigate with no data
        - ``(ScreenId, dict)``      – navigate with keyword data
        """
        ...

    @abstractmethod
    def draw(self, surface):
        """Render this screen onto *surface*."""
        ...

    def update(self):
        """Per-frame update (animation, polling).  Default is no-op."""
        pass

    def on_enter(self, **kwargs):
        """Called when this screen becomes active."""
        pass

    def on_exit(self):
        """Called when transitioning away from this screen."""
        pass
