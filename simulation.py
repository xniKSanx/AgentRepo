"""Core simulation engine for the AI Warehouse game.

Consolidates the game loop, result determination, and game result data
that were previously duplicated across main.py, batch_runner.py, and
game_runner.py.

All agent moves are dispatched through the shared execution contract
(``execution.execute_agent_step``), which clones the environment, runs
the agent in a subprocess with monotonic-clock timing, and enforces
timeouts via process termination.
"""

import logging
import time
import traceback as tb_module
from dataclasses import dataclass
from typing import List, Optional

from WarehouseEnv import WarehouseEnv
from execution import execute_agent_step

logger = logging.getLogger(__name__)


@dataclass
class GameResult:
    """Result of a single completed game.

    When ``error`` is not None the game encountered a failure.  The
    ``error_phase``, ``error_type``, and ``error_traceback`` fields
    provide structured context so callers can distinguish expected
    execution errors from programming errors without parsing a string.

    Errored games must be excluded from aggregate win/loss statistics.
    """
    seed: int
    winner: Optional[int]           # 0, 1, or None for draw
    final_credits: List[int]        # [credit0, credit1]
    steps_taken: int
    timeout_flags: List[bool]       # [agent0_timed_out, agent1_timed_out]
    error: Optional[str]            # Human-readable summary; None if no error
    wall_time_seconds: float
    error_phase: Optional[str] = None       # e.g. "agent_step", "apply_operator", "get_balances"
    error_type: Optional[str] = None        # Exception class name, e.g. "RuntimeError"
    error_traceback: Optional[str] = None   # Full traceback string for diagnostics


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

        error_phase = None
        error_type = None
        error_traceback = None

        try:
            for round_num in range(self.count_steps):
                for agent_index, agent_name in enumerate(self.agent_names):

                    step = execute_agent_step(
                        agent_name, self.env, agent_index, self.time_limit,
                    )

                    if step.error:
                        error_phase = "agent_step"
                        error_type = "AgentExecutionError"
                        error_msg = (
                            f"Agent {agent_index} ({agent_name}) crashed: "
                            f"{step.error}"
                        )
                        error_traceback = step.error
                        logger.warning(
                            "Agent %d (%s) crashed in round %d: %s",
                            agent_index, agent_name, round_num, step.error,
                        )
                        raise RuntimeError(error_msg)

                    if step.timed_out:
                        timeout_flags[agent_index] = True
                        # Timed-out move is NOT applied.  The agent
                        # forfeits this turn; the game continues.
                        steps_taken += 1
                        continue

                    try:
                        self.env.apply_operator(agent_index, step.operator)
                    except Exception as apply_exc:
                        error_phase = "apply_operator"
                        error_type = type(apply_exc).__name__
                        error_msg = (
                            f"apply_operator failed for agent {agent_index} "
                            f"({agent_name}), operator '{step.operator}' in "
                            f"round {round_num}: {apply_exc}"
                        )
                        error_traceback = tb_module.format_exc()
                        logger.warning(
                            "apply_operator failed: agent=%d (%s), "
                            "operator=%s, round=%d: %s",
                            agent_index, agent_name, step.operator,
                            round_num, apply_exc,
                        )
                        raise

                    steps_taken += 1

                    if turn_callback:
                        turn_callback(
                            round_num, agent_index, agent_name,
                            step.operator, self.env,
                        )

                if self.env.done():
                    break

        except Exception as e:
            if error_msg is None:
                # Unexpected exception not already captured above.
                error_phase = "game_loop"
                error_type = type(e).__name__
                error_msg = f"{type(e).__name__}: {e}"
                error_traceback = tb_module.format_exc()
                logger.warning(
                    "Unexpected error in game loop (seed=%d): %s",
                    self.seed, error_msg, exc_info=True,
                )

        wall_time = time.monotonic() - wall_start

        # Retrieve final balances.  If get_balances itself fails, that
        # is an error — do NOT substitute a neutral [0, 0] which would
        # silently produce a draw outcome.
        try:
            balances = self.env.get_balances()
        except Exception as bal_exc:
            bal_tb = tb_module.format_exc()
            logger.warning(
                "get_balances failed (seed=%d): %s",
                self.seed, bal_exc, exc_info=True,
            )
            # If a prior error already exists, keep it.  Otherwise
            # record the get_balances failure as the primary error.
            if error_msg is None:
                error_phase = "get_balances"
                error_type = type(bal_exc).__name__
                error_msg = f"get_balances failed: {type(bal_exc).__name__}: {bal_exc}"
                error_traceback = bal_tb
            balances = [0, 0]

        # Errored games must NOT produce a winner — this prevents
        # silent data corruption in aggregate statistics.
        winner = None if error_msg else determine_winner(balances)

        return GameResult(
            seed=self.seed,
            winner=winner,
            final_credits=balances,
            steps_taken=steps_taken,
            timeout_flags=timeout_flags,
            error=error_msg,
            wall_time_seconds=round(wall_time, 4),
            error_phase=error_phase,
            error_type=error_type,
            error_traceback=error_traceback,
        )
