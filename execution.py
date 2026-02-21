"""Shared agent execution contract for the AI Warehouse game.

Provides a unified entrypoint for running agent moves in both batch and GUI
modes. Key properties:

- **Env-view policy: CLONE.** The agent always receives a clone of the
  environment, never the live game state. This prevents agents from
  mutating the actual game and makes batch/GUI behaviour identical.

- **Timeout enforcement: SUBPROCESS.** Each agent move runs in a child
  process. If the agent exceeds the time limit, the process is terminated
  (SIGTERM) then killed (SIGKILL) as a fallback. Timed-out moves return
  ``StepResult(operator=None, timed_out=True)``.

- **Monotonic timing.** All elapsed-time measurements use
  ``time.monotonic()`` to avoid wall-clock jumps (NTP, suspend/resume).

- **Stateless agents.** Because each move spawns a fresh process, agents
  are instantiated via ``create_agent(name)`` inside the subprocess. Any
  state accumulated across moves is lost. Agents must derive all
  information from ``(env, agent_id, time_limit)``.

Usage::

    from execution import execute_agent_step

    result = execute_agent_step("alphabeta", env, agent_index, 1.0)
    if result.timed_out or result.error:
        # do NOT apply the move
        ...
    else:
        env.apply_operator(agent_index, result.operator)
"""

import multiprocessing
import queue
import time
import traceback
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Grace period (seconds) added to time_limit before hard-killing the
# subprocess.  Accounts for process startup overhead so agents that finish
# just at the deadline are not spuriously terminated.
# ---------------------------------------------------------------------------
GRACE_PERIOD = 0.5


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Outcome of a single agent move execution."""

    operator: Optional[str]   # The move string, or None on timeout / error.
    elapsed: float            # Wall-clock seconds (monotonic) for the step.
    timed_out: bool           # True if the time limit was exceeded.
    error: Optional[str]      # Exception description if the agent crashed.


@dataclass
class TimeoutPolicy:
    """Timeout configuration for agent execution."""

    time_limit: float                    # Seconds allowed per move.
    enforcement: str = "subprocess"      # "subprocess" (hard-kill) is the
                                         # only production-grade option.
    grace_period: float = GRACE_PERIOD   # Extra seconds before terminate().


# ---------------------------------------------------------------------------
# Subprocess worker
# ---------------------------------------------------------------------------

def _subprocess_worker(agent_name, env_clone, agent_id, time_limit,
                       result_queue):
    """Run *one* agent step inside a child process.

    The agent is instantiated fresh from the registry so we never need to
    pickle an agent object.  The result (operator string or error) is sent
    back via *result_queue*.
    """
    # Import inside the worker so the child process picks up the registry
    # without requiring it to be picklable at the call-site.
    from agent_registry import create_agent  # noqa: PLC0415

    try:
        agent = create_agent(agent_name)
        op = agent.run_step(env_clone, agent_id, time_limit)
        result_queue.put({"operator": op, "error": None})
    except Exception as exc:
        result_queue.put({
            "operator": None,
            "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        })


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute_agent_step(agent_name, env, agent_id, time_limit):
    """Execute a single agent move with subprocess-based timeout enforcement.

    Parameters
    ----------
    agent_name : str
        Name of the agent in the registry (e.g. ``"alphabeta"``).
    env : WarehouseEnv
        The **live** game environment.  A clone is made internally; the
        caller's env is never mutated by the agent.
    agent_id : int
        Index of the robot (0 or 1).
    time_limit : float
        Seconds the agent is allowed to compute.

    Returns
    -------
    StepResult
        Contains the operator (or ``None``), elapsed time, timeout flag,
        and any error message.
    """
    start = time.monotonic()

    # ---- Clone env so the agent cannot mutate the live game state ----
    env_clone = env.clone()

    # ---- Launch subprocess ----
    result_queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=_subprocess_worker,
        args=(agent_name, env_clone, agent_id, time_limit, result_queue),
    )
    proc.start()

    # ---- Wait with hard timeout ----
    join_timeout = time_limit + GRACE_PERIOD
    proc.join(timeout=join_timeout)
    elapsed = time.monotonic() - start

    # ---- Handle still-running process (hard timeout) ----
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=1.0)
        if proc.is_alive():
            proc.kill()
            proc.join()
        return StepResult(
            operator=None,
            elapsed=elapsed,
            timed_out=True,
            error=None,
        )

    # ---- Process finished — retrieve result ----
    try:
        result = result_queue.get_nowait()
    except queue.Empty:
        return StepResult(
            operator=None,
            elapsed=elapsed,
            timed_out=False,
            error=(
                f"Agent '{agent_name}' subprocess exited with code "
                f"{proc.exitcode} but produced no result"
            ),
        )

    if result["error"]:
        return StepResult(
            operator=None,
            elapsed=elapsed,
            timed_out=False,
            error=result["error"],
        )

    # Process finished before the hard deadline (time_limit + GRACE_PERIOD).
    # The agent completed its work in time — accept the result.
    # NOTE: We do NOT compare elapsed vs time_limit here because elapsed
    # includes subprocess overhead (fork, pickle, imports) which is NOT
    # the agent's fault.  The hard timeout (process.join + terminate)
    # is the sole enforcement mechanism.
    return StepResult(
        operator=result["operator"],
        elapsed=elapsed,
        timed_out=False,
        error=None,
    )
