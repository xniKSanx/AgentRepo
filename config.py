"""Typed configuration objects and centralized defaults.

All shared magic constants and configuration schemas live here so that
batch_runner, game_runner (GUI), and main.py all reference a single
source of truth.
"""

from dataclasses import dataclass, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Centralized defaults
# ---------------------------------------------------------------------------

DEFAULT_COUNT_STEPS = 4761
"""Maximum number of rounds per game.  Each round consists of two agent
moves (one per robot).  The value 4761 allows sufficient exploration on
the default 5x5 board with typical battery constraints."""

DEFAULT_TIME_LIMIT = 1.0
"""Seconds allowed per agent move."""

DEFAULT_OUTPUT_DIR = "batch_results"
"""Default output directory for batch run results."""

DEFAULT_NUM_GAMES = 100
"""Default number of games in a batch run."""


# ---------------------------------------------------------------------------
# Typed config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GameConfig:
    """Configuration for a single GUI game."""

    agent0: str
    agent1: str
    time_limit: float = DEFAULT_TIME_LIMIT
    seed: int = 0
    count_steps: int = DEFAULT_COUNT_STEPS
    logging_enabled: bool = False
    custom_map_data: Optional[dict] = None

    def __post_init__(self):
        if self.time_limit <= 0:
            raise ValueError(
                f"time_limit must be positive, got {self.time_limit}"
            )
        if self.count_steps <= 0:
            raise ValueError(
                f"count_steps must be positive, got {self.count_steps}"
            )


@dataclass
class BatchConfig:
    """Configuration for a batch run."""

    agent0: str
    agent1: str
    num_games: int = DEFAULT_NUM_GAMES
    time_limit: float = DEFAULT_TIME_LIMIT
    count_steps: int = DEFAULT_COUNT_STEPS
    seed_start: Optional[int] = None
    seed_list_file: Optional[str] = None
    output_dir: str = DEFAULT_OUTPUT_DIR
    log_sampling_rate: int = 0
    fail_fast: bool = False
    csv: bool = False
    command: str = ""

    def __post_init__(self):
        if self.time_limit <= 0:
            raise ValueError(
                f"time_limit must be positive, got {self.time_limit}"
            )
        if self.count_steps <= 0:
            raise ValueError(
                f"count_steps must be positive, got {self.count_steps}"
            )
        if self.num_games <= 0:
            raise ValueError(
                f"num_games must be positive, got {self.num_games}"
            )
        if self.log_sampling_rate < 0:
            raise ValueError(
                f"log_sampling_rate must be non-negative, "
                f"got {self.log_sampling_rate}"
            )

    def to_dict(self):
        """Convert to plain dict for backward compatibility."""
        return asdict(self)
