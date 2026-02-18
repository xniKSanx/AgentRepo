"""Log replay module for AI Warehouse game.

Parses game log files (from both GameLogger and batch_runner formats)
and provides a ReplayEngine that pre-computes all game states for
instant random-access navigation.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from WarehouseEnv import WarehouseEnv


@dataclass
class ReplayData:
    seed: int
    count_steps: int
    agent_names: List[str]
    moves: List[Tuple[int, str]]
    source_file: str


class LogParser:
    """Parses game log files from both GameLogger and batch_runner formats."""

    # Game runner format patterns (game_runner.py GameLogger)
    _GR_SEED = re.compile(r'Seed:\s+(\d+)')
    _GR_STEPS = re.compile(r'Max Rounds:\s+(\d+)')
    _GR_AGENT0 = re.compile(r'Agent 0 \(Blue\):\s+(.+)')
    _GR_AGENT1 = re.compile(r'Agent 1 \(Red\):\s+(.+)')
    _GR_MOVE = re.compile(r'\[Round \d+\] Agent (\d+) \(.+?\): (.+)')
    _GR_ERROR = re.compile(r'\[Round \d+\] Agent \d+ \(.+?\): ERROR')

    # Batch runner format patterns (batch_runner.py)
    _BR_SEED = re.compile(r'Seed:\s+(\d+)')
    _BR_STEPS = re.compile(r'count_steps=(\d+)')
    _BR_AGENTS = re.compile(r'Agents:\s+(.+?)\s+vs\s+(.+)')
    _BR_MOVE = re.compile(r'Round \d+, Agent (\d+) \(.+?\): (.+)')

    @staticmethod
    def parse(filepath: str) -> ReplayData:
        with open(filepath, 'r') as f:
            text = f.read()

        if "AI WAREHOUSE GAME LOG" in text:
            return LogParser._parse_game_runner(text, filepath)
        elif "=== Game" in text:
            return LogParser._parse_batch_runner(text, filepath)
        else:
            raise ValueError(
                "Unrecognized log format. Expected a GameLogger or batch_runner log file."
            )

    @staticmethod
    def _parse_game_runner(text: str, filepath: str) -> ReplayData:
        seed_m = LogParser._GR_SEED.search(text)
        steps_m = LogParser._GR_STEPS.search(text)
        agent0_m = LogParser._GR_AGENT0.search(text)
        agent1_m = LogParser._GR_AGENT1.search(text)

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
        for line in text.splitlines():
            if LogParser._GR_ERROR.match(line):
                continue
            m = LogParser._GR_MOVE.match(line)
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
        )

    @staticmethod
    def _parse_batch_runner(text: str, filepath: str) -> ReplayData:
        seed_m = LogParser._BR_SEED.search(text)
        steps_m = LogParser._BR_STEPS.search(text)
        agents_m = LogParser._BR_AGENTS.search(text)

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
        for line in text.splitlines():
            m = LogParser._BR_MOVE.search(line)
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
        )


class ReplayEngine:
    """Pre-computes all game states for instant random-access navigation."""

    def __init__(self, replay_data: ReplayData):
        self.data = replay_data
        self.states: List[WarehouseEnv] = []
        self.current_index: int = 0
        self._precompute_states()

    def _precompute_states(self):
        env = WarehouseEnv()
        env.generate(self.data.seed, 2 * self.data.count_steps)
        self.states.append(env.clone())

        for agent_idx, operator in self.data.moves:
            legal = env.get_legal_operators(agent_idx)
            if operator not in legal:
                break
            env.apply_operator(agent_idx, operator)
            self.states.append(env.clone())

    @property
    def total_moves(self) -> int:
        return len(self.states) - 1

    @property
    def current_env(self) -> WarehouseEnv:
        return self.states[self.current_index]

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

    def step_forward(self) -> bool:
        if self.current_index < self.total_moves:
            self.current_index += 1
            return True
        return False

    def step_backward(self) -> bool:
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def go_to_start(self):
        self.current_index = 0

    def go_to_end(self):
        self.current_index = self.total_moves

    def go_to_index(self, index: int):
        self.current_index = max(0, min(index, self.total_moves))

    def is_at_start(self) -> bool:
        return self.current_index == 0

    def is_at_end(self) -> bool:
        return self.current_index == self.total_moves
