"""Centralized agent registry for the AI Warehouse game.

Single source of truth for agent names and creation. Uses a factory
pattern (name -> class) so agents are only instantiated on demand,
and each call to create_agent() returns a fresh instance.
"""

import Agent
import submission

# Registry maps name -> zero-arg callable that returns a fresh Agent.
# The class itself IS the factory (all agent constructors are zero-arg).
AGENT_REGISTRY = {
    "random": Agent.AgentRandom,
    "greedy": Agent.AgentGreedy,
    "greedyImproved": submission.AgentGreedyImproved,
    "minimax": submission.AgentMinimax,
    "alphabeta": submission.AgentAlphaBeta,
    "expectimax": submission.AgentExpectimax,
    "hardcoded": submission.AgentHardCoded,
}

# Canonical list of valid agent names. No instantiation at import time.
VALID_AGENT_NAMES = list(AGENT_REGISTRY.keys())


def create_agent(name):
    """Create and return a fresh agent instance by name.

    Raises KeyError if name is not in the registry.
    """
    if name not in AGENT_REGISTRY:
        raise KeyError(
            f"Unknown agent '{name}'. Valid agents: {VALID_AGENT_NAMES}"
        )
    return AGENT_REGISTRY[name]()
