"""Shared versioned logging contract for game logs.

Both GameLogger (GUI) and batch_runner use this module for format
templates, parsing rules, and JSONL sidecar I/O, ensuring a single
source of truth for log schema.

LOG_VERSION is bumped whenever the log format changes.  Parsers branch
on the detected version so old logs remain replayable.
"""

import json
import os
import re
from datetime import datetime


# ── Version ──────────────────────────────────────────────────────────
LOG_VERSION = "1.0"

# ── Text format templates (used by writers) ──────────────────────────

_BANNER = "=" * 60


def format_gui_header(config: dict) -> list:
    """Return header lines for a GUI game log (v1.0)."""
    return [
        _BANNER,
        "AI WAREHOUSE GAME LOG",
        _BANNER,
        f"LOG_VERSION: {LOG_VERSION}",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Agent 0 (Blue): {config['agent0']}",
        f"Agent 1 (Red):  {config['agent1']}",
        f"Time Limit:     {config['time_limit']}s",
        f"Seed:           {config['seed']}",
        f"Max Rounds:     {config['count_steps']}",
        _BANNER,
        "",
    ]


def format_batch_header(game_index, agent0, agent1, time_limit, count_steps, seed):
    """Return header lines for a batch game log (v1.0)."""
    return [
        f"=== Game {game_index} ===",
        f"LOG_VERSION: {LOG_VERSION}",
        f"Agents: {agent0} vs {agent1}",
        f"Config: time_limit={time_limit}, count_steps={count_steps}",
        f"Seed: {seed}",
        "",
    ]


def format_move_line_gui(round_num, agent_index, agent_name, operator):
    """Format a single move line for GUI logs."""
    return f"[Round {round_num}] Agent {agent_index} ({agent_name}): {operator}"


def format_move_line_batch(round_num, agent_index, agent_name, operator):
    """Format a single move line for batch logs."""
    return f"  Round {round_num}, Agent {agent_index} ({agent_name}): {operator}"


# ── Parsing helpers ──────────────────────────────────────────────────

_VERSION_RE = re.compile(r'^LOG_VERSION:\s+(.+)', re.MULTILINE)


def detect_version(text):
    """Extract LOG_VERSION from log text.  Returns None for legacy logs."""
    m = _VERSION_RE.search(text)
    return m.group(1).strip() if m else None


# Anchored patterns for v1.0 (and legacy) log parsing.
# Every move pattern is anchored at start-of-line and uses match()
# to prevent false positives.

# GUI format patterns
GUI_SEED = re.compile(r'^Seed:\s+(\d+)', re.MULTILINE)
GUI_STEPS = re.compile(r'^Max Rounds:\s+(\d+)', re.MULTILINE)
GUI_AGENT0 = re.compile(r'^Agent 0 \(Blue\):\s+(.+)', re.MULTILINE)
GUI_AGENT1 = re.compile(r'^Agent 1 \(Red\):\s+(.+)', re.MULTILINE)
GUI_MOVE = re.compile(r'^\[Round \d+\] Agent (\d+) \(.+?\): (.+)')
GUI_ERROR = re.compile(r'^\[Round \d+\] Agent \d+ \(.+?\): ERROR')

# Batch format patterns
BATCH_SEED = re.compile(r'^Seed:\s+(\d+)', re.MULTILINE)
BATCH_STEPS = re.compile(r'^Config:.*count_steps=(\d+)', re.MULTILINE)
BATCH_AGENTS = re.compile(r'^Agents:\s+(.+?)\s+vs\s+(.+)', re.MULTILINE)
BATCH_MOVE = re.compile(r'^\s*Round \d+, Agent (\d+) \(.+?\): (.+)')


# ── JSONL sidecar I/O ───────────────────────────────────────────────

def jsonl_path_for(txt_path):
    """Derive the .jsonl sidecar path from a .txt log path."""
    base, _ = os.path.splitext(txt_path)
    return base + ".jsonl"


def write_jsonl_sidecar(filepath, header_dict, move_dicts, result_dict=None):
    """Write a complete JSONL sidecar file.

    Args:
        filepath: Path to the .jsonl file.
        header_dict: Dict with keys log_version, seed, count_steps,
                     agent_names, time_limit.
        move_dicts: List of dicts with keys round, agent, operator.
        result_dict: Optional dict with keys final_credits, winner, error.
    """
    with open(filepath, "w") as f:
        header = {"type": "header", "log_version": LOG_VERSION}
        header.update(header_dict)
        f.write(json.dumps(header, separators=(",", ":")) + "\n")
        for move in move_dicts:
            entry = {"type": "move"}
            entry.update(move)
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        if result_dict is not None:
            entry = {"type": "result"}
            entry.update(result_dict)
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def read_jsonl_sidecar(txt_filepath):
    """Parse the JSONL sidecar for a given .txt log path.

    Returns a tuple (header_dict, moves_list, result_dict_or_None) if
    the sidecar exists, or None if the sidecar file is not found.

    moves_list contains (agent_index, operator) tuples.
    """
    jsonl_path = jsonl_path_for(txt_filepath)
    if not os.path.isfile(jsonl_path):
        return None

    header = None
    moves = []
    result = None
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rtype = record.get("type")
            if rtype == "header":
                header = record
            elif rtype == "move":
                moves.append((record["agent"], record["operator"]))
            elif rtype == "result":
                result = record

    if header is None:
        return None

    return header, moves, result
