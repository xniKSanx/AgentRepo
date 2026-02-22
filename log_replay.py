"""Log replay module for AI Warehouse game.

Parses game log files (from both GameLogger and batch_runner formats)
and provides a ReplayEngine with checkpoint-based state reconstruction
for memory-efficient random-access navigation.

Parsing prefers the structured JSONL sidecar when available.  Text-based
regex parsing is used only for legacy logs that lack a sidecar.
"""

import bisect
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from WarehouseEnv import WarehouseEnv
from logging_contract import (
    detect_version, read_jsonl_sidecar,
    GUI_SEED, GUI_STEPS, GUI_AGENT0, GUI_AGENT1, GUI_MOVE, GUI_ERROR,
    BATCH_SEED, BATCH_STEPS, BATCH_AGENTS, BATCH_MOVE,
)

# ── Diagnostics ──────────────────────────────────────────────────────

@dataclass
class ReplayDiagnostics:
    """Records issues encountered during replay parsing and state
    reconstruction.  Callers can inspect ``warnings``, ``truncated``,
    and ``truncation_reason`` to surface problems in the UI."""

    warnings: list = field(default_factory=list)
    truncated: bool = False
    truncation_reason: Optional[str] = None

    def add_warning(self, kind, message, *, round_num=None, agent=None,
                    line_number=None):
        self.warnings.append({
            "kind": kind,
            "message": message,
            "round": round_num,
            "agent": agent,
            "line_number": line_number,
        })


# ── Replay Data ──────────────────────────────────────────────────────

@dataclass
class ReplayData:
    seed: int
    count_steps: int
    agent_names: List[str]
    moves: List[Tuple[int, str]]
    source_file: str
    diagnostics: ReplayDiagnostics = field(default_factory=ReplayDiagnostics)
    custom_map_data: Optional[Dict] = None


# ── Log Parser ───────────────────────────────────────────────────────

class LogParser:
    """Parses game log files from both GameLogger and batch_runner
    formats.

    Parsing priority:
    1. Structured JSONL sidecar (no regex, no version detection needed).
    2. Versioned text log (LOG_VERSION header present).
    3. Legacy text log (sentinel-based format detection).
    """

    @staticmethod
    def parse(filepath: str) -> ReplayData:
        # 1. Try structured JSONL sidecar first
        sidecar = read_jsonl_sidecar(filepath)
        if sidecar is not None:
            header, moves, _result = sidecar
            return ReplayData(
                seed=header["seed"],
                count_steps=header["count_steps"],
                agent_names=list(header["agent_names"]),
                moves=moves,
                source_file=filepath,
                custom_map_data=header.get("custom_map_data"),
            )

        # 2. Fall back to text parsing
        with open(filepath, 'r') as f:
            text = f.read()

        version = detect_version(text)

        # Versioned or legacy — detect format and parse
        if "AI WAREHOUSE GAME LOG" in text:
            return LogParser._parse_game_runner(text, filepath, version)
        elif "=== Game" in text:
            return LogParser._parse_batch_runner(text, filepath, version)
        else:
            raise ValueError(
                "Unrecognized log format. Expected a GameLogger or "
                "batch_runner log file, or a JSONL sidecar."
            )

    @staticmethod
    def _parse_game_runner(text: str, filepath: str,
                           version: Optional[str]) -> ReplayData:
        diag = ReplayDiagnostics()

        seed_m = GUI_SEED.search(text)
        steps_m = GUI_STEPS.search(text)
        agent0_m = GUI_AGENT0.search(text)
        agent1_m = GUI_AGENT1.search(text)

        if not seed_m:
            raise ValueError("Could not find Seed in log file")
        if not steps_m:
            raise ValueError("Could not find Max Rounds in log file")
        if not agent0_m or not agent1_m:
            raise ValueError("Could not find agent names in log file")

        seed = int(seed_m.group(1))
        count_steps = int(steps_m.group(1))
        agent_names = [agent0_m.group(1).strip(), agent1_m.group(1).strip()]

        moves = []
        for line_num, line in enumerate(text.splitlines(), start=1):
            if GUI_ERROR.match(line):
                diag.add_warning(
                    "error_line", f"Error logged at line {line_num}",
                    line_number=line_num,
                )
                continue
            m = GUI_MOVE.match(line)
            if m:
                agent_idx = int(m.group(1))
                operator = m.group(2).strip()
                moves.append((agent_idx, operator))

        return ReplayData(
            seed=seed,
            count_steps=count_steps,
            agent_names=agent_names,
            moves=moves,
            source_file=filepath,
            diagnostics=diag,
        )

    @staticmethod
    def _parse_batch_runner(text: str, filepath: str,
                            version: Optional[str]) -> ReplayData:
        diag = ReplayDiagnostics()

        seed_m = BATCH_SEED.search(text)
        steps_m = BATCH_STEPS.search(text)
        agents_m = BATCH_AGENTS.search(text)

        if not seed_m:
            raise ValueError("Could not find Seed in log file")
        if not steps_m:
            raise ValueError("Could not find count_steps in log file")
        if not agents_m:
            raise ValueError("Could not find agent names in log file")

        seed = int(seed_m.group(1))
        count_steps = int(steps_m.group(1))
        agent_names = [agents_m.group(1).strip(), agents_m.group(2).strip()]

        moves = []
        for line_num, line in enumerate(text.splitlines(), start=1):
            # Use .match() on the line (anchored pattern) instead of
            # .search() to prevent false positives from substring matches.
            m = BATCH_MOVE.match(line)
            if m:
                agent_idx = int(m.group(1))
                operator = m.group(2).strip()
                moves.append((agent_idx, operator))

        return ReplayData(
            seed=seed,
            count_steps=count_steps,
            agent_names=agent_names,
            moves=moves,
            source_file=filepath,
            diagnostics=diag,
        )


# ── Replay Engine (checkpoint-based) ─────────────────────────────────

CHECKPOINT_INTERVAL = 50


class ReplayEngine:
    """Checkpoint-based replay engine for memory-efficient random-access
    navigation.

    Instead of cloning the full environment for every single move,
    checkpoints are stored every ``CHECKPOINT_INTERVAL`` moves.
    Intermediate states are reconstructed on demand by replaying from the
    nearest checkpoint.

    Sequential forward stepping (``step_forward``) avoids full
    reconstruction by advancing the cached current env by one move.
    """

    def __init__(self, replay_data: ReplayData):
        self.data = replay_data
        self.diagnostics: ReplayDiagnostics = ReplayDiagnostics()
        self._checkpoints: dict = {}  # state_index -> cloned WarehouseEnv
        self._checkpoint_indices: list = []  # sorted list for bisect lookup
        self._valid_move_count: int = 0
        self.current_index: int = 0
        self._current_env: Optional[WarehouseEnv] = None
        self._build_checkpoints()

    def _build_checkpoints(self):
        """Validate all moves and store checkpoints every N steps."""
        env = WarehouseEnv()
        if self.data.custom_map_data:
            env.load_from_map_data(self.data.custom_map_data,
                                   2 * self.data.count_steps)
            env.seed = self.data.seed
        else:
            env.generate(self.data.seed, 2 * self.data.count_steps)
        self._checkpoints[0] = env.clone()

        for i, (agent_idx, operator) in enumerate(self.data.moves):
            legal = env.get_legal_operators(agent_idx)
            if operator not in legal:
                self.diagnostics.truncated = True
                self.diagnostics.truncation_reason = (
                    f"Illegal operator '{operator}' for agent {agent_idx} "
                    f"at move {i} (round {i // 2 + 1}). "
                    f"Legal operators: {legal}"
                )
                self.diagnostics.add_warning(
                    "illegal_operator",
                    f"Move {i}: operator '{operator}' not in {legal}",
                    round_num=i // 2 + 1,
                    agent=agent_idx,
                )
                break

            env.apply_operator(agent_idx, operator)
            state_index = i + 1  # index of state *after* this move
            if state_index % CHECKPOINT_INTERVAL == 0:
                self._checkpoints[state_index] = env.clone()
            self._valid_move_count = state_index

        # Always checkpoint the final validated state
        if self._valid_move_count not in self._checkpoints:
            self._checkpoints[self._valid_move_count] = env.clone()

        # Build sorted index list for efficient lookup
        self._checkpoint_indices = sorted(self._checkpoints.keys())

        # Initialise current position to the start
        self._current_env = self._checkpoints[0].clone()

    def _reconstruct_state(self, target_index: int) -> WarehouseEnv:
        """Reconstruct the env at *target_index* from the nearest
        preceding checkpoint."""
        # bisect_right gives the insertion point; subtract 1 for the
        # highest checkpoint <= target_index.
        pos = bisect.bisect_right(self._checkpoint_indices, target_index)
        best_cp = self._checkpoint_indices[pos - 1]

        env = self._checkpoints[best_cp].clone()
        for i in range(best_cp, target_index):
            agent_idx, operator = self.data.moves[i]
            env.apply_operator(agent_idx, operator)
        return env

    # ── Properties (backward-compatible with ReplayScreen) ───────────

    @property
    def total_moves(self) -> int:
        return self._valid_move_count

    @property
    def current_env(self) -> WarehouseEnv:
        if self._current_env is None:
            self._current_env = self._reconstruct_state(self.current_index)
        return self._current_env

    @property
    def current_move_info(self) -> Optional[Tuple[int, str]]:
        if self.current_index == 0:
            return None
        return self.data.moves[self.current_index - 1]

    @property
    def current_round(self) -> int:
        if self.current_index == 0:
            return 0
        return (self.current_index - 1) // 2 + 1

    # ── Navigation ───────────────────────────────────────────────────

    def step_forward(self) -> bool:
        if self.current_index < self.total_moves:
            # Optimisation: advance the cached env by one move instead
            # of reconstructing from a checkpoint.
            agent_idx, operator = self.data.moves[self.current_index]
            env = self.current_env.clone()
            env.apply_operator(agent_idx, operator)
            self.current_index += 1
            self._current_env = env
            return True
        return False

    def step_backward(self) -> bool:
        if self.current_index > 0:
            self.current_index -= 1
            self._current_env = self._reconstruct_state(self.current_index)
            return True
        return False

    def go_to_start(self):
        if self.current_index != 0:
            self.current_index = 0
            self._current_env = self._checkpoints[0].clone()

    def go_to_end(self):
        target = self.total_moves
        if self.current_index != target:
            self.current_index = target
            self._current_env = self._reconstruct_state(target)

    def go_to_index(self, index: int):
        index = max(0, min(index, self.total_moves))
        if index != self.current_index:
            self.current_index = index
            self._current_env = self._reconstruct_state(index)

    def is_at_start(self) -> bool:
        return self.current_index == 0

    def is_at_end(self) -> bool:
        return self.current_index == self.total_moves
