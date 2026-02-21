"""Core simulation engine for the AI Warehouse game.

Consolidates the game loop, result determination, and game result data
that were previously duplicated across main.py, batch_runner.py, and
game_runner.py.

All agent moves are dispatched through the shared execution contract
(``execution.execute_agent_step``), which clones the environment, runs
the agent in a subprocess with monotonic-clock timing, and enforces
timeouts via process termination.
"""

import time
from dataclasses import dataclass
from typing import List, Optional

from WarehouseEnv import WarehouseEnv
from execution import execute_agent_step


@dataclass
class GameResult:
    """Result of a single completed game."""
    seed: int
    winner: Optional[int]           # 0, 1, or None for draw
    final_credits: List[int]        # [credit0, credit1]
    steps_taken: int
    timeout_flags: List[bool]       # [agent0_timed_out, agent1_timed_out]
    error: Optional[str]            # None if no error
    wall_time_seconds: float


def determine_winner(balances):
    """Determine the winner from final credit balances.

    Returns 0 if agent 0 wins, 1 if agent 1 wins, None for a draw.
    """
    if balances[0] > balances[1]:
        return 0
    elif balances[1] > balances[0]:
        return 1
    return None


class GameSimulator:
    """Runs a single game between two agents to completion.

    Consolidates the game loop that was duplicated in main.py (single game,
    tournament), batch_runner.py, and the conceptual loop in game_runner.py.

    Every agent turn is executed through the shared execution contract
    (``execute_agent_step``), which:

    * Clones the environment so the agent cannot mutate the live state.
    * Runs the agent in a subprocess with hard-kill timeout enforcement.
    * Uses ``time.monotonic()`` for elapsed measurement.

    If an agent times out, the move is **not** applied to the environment
    and ``timeout_flags`` is set for that agent.  The game continues with
    the next turn (the timed-out agent forfeits that move).

    Usage::

        sim = GameSimulator(
            agent_names=["alphabeta", "greedy"],
            seed=42,
            count_steps=4761,
            time_limit=1.0,
        )
        result = sim.run()

    The optional *turn_callback* is invoked after each **successful** move::

        turn_callback(round_num, agent_index, agent_name, operator, env)
    """

    def __init__(self, agent_names, seed, count_steps, time_limit,
                 env=None, custom_map_data=None):
        """
        Args:
            agent_names: List of two agent name strings.
            seed: Random seed for environment generation.
            count_steps: Max number of rounds (each round = 2 agent turns).
            time_limit: Time limit per agent turn in seconds.
            env: Optional pre-configured WarehouseEnv. If None, one is created.
            custom_map_data: Optional map data dict for custom maps.
        """
        self.agent_names = agent_names
        self.seed = seed
        self.count_steps = count_steps
        self.time_limit = time_limit

        # Build environment
        if env is not None:
            self.env = env
        else:
            self.env = WarehouseEnv()
            if custom_map_data:
                self.env.load_from_map_data(custom_map_data, 2 * count_steps)
            else:
                self.env.generate(seed, 2 * count_steps)

    def run(self, turn_callback=None):
        """Run the game to completion and return a GameResult.

        Args:
            turn_callback: Optional callable(round_num, agent_index,
                          agent_name, operator, env) called after each
                          successful (non-timed-out, non-errored) move.

        Returns:
            GameResult with the outcome of the game.
        """
        timeout_flags = [False, False]
        error_msg = None
        steps_taken = 0

        wall_start = time.monotonic()

        try:
            for round_num in range(self.count_steps):
                for agent_index, agent_name in enumerate(self.agent_names):

                    step = execute_agent_step(
                        agent_name, self.env, agent_index, self.time_limit,
                    )

                    if step.error:
                        raise RuntimeError(
                            f"Agent {agent_index} ({agent_name}) crashed: "
                            f"{step.error}"
                        )

                    if step.timed_out:
                        timeout_flags[agent_index] = True
                        # Timed-out move is NOT applied.  The agent
                        # forfeits this turn; the game continues.
                        steps_taken += 1
                        continue

                    self.env.apply_operator(agent_index, step.operator)
                    steps_taken += 1

                    if turn_callback:
                        turn_callback(
                            round_num, agent_index, agent_name,
                            step.operator, self.env,
                        )

                if self.env.done():
                    break

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"

        wall_time = time.monotonic() - wall_start

        try:
            balances = self.env.get_balances()
        except Exception:
            balances = [0, 0]

        winner = None if error_msg else determine_winner(balances)

        return GameResult(
            seed=self.seed,
            winner=winner,
            final_credits=balances,
            steps_taken=steps_taken,
            timeout_flags=timeout_flags,
            error=error_msg,
            wall_time_seconds=round(wall_time, 4),
        )
