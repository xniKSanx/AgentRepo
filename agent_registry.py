"""Centralized agent registry for the AI Warehouse game.

Single source of truth for agent instantiation and valid agent names,
eliminating duplication across main.py, batch_runner.py, and game_runner.py.
"""

import Agent
import submission


def build_agents():
    """Build and return a fresh agent name-to-instance dictionary.

    Each call returns new instances to avoid state leakage between games
    (e.g. AgentHardCoded.step counter).
    """
    return {
        "random": Agent.AgentRandom(),
        "greedy": Agent.AgentGreedy(),
        "greedyImproved": submission.AgentGreedyImproved(),
        "minimax": submission.AgentMinimax(),
        "alphabeta": submission.AgentAlphaBeta(),
        "expectimax": submission.AgentExpectimax(),
        "hardcoded": submission.AgentHardCoded(),
    }


VALID_AGENT_NAMES = list(build_agents().keys())
