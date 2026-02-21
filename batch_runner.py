"""Batch game execution with statistics and log output.

Accepts ``BatchConfig`` typed config objects (from ``config.py``) for
all primary APIs.  Centralized defaults like ``DEFAULT_COUNT_STEPS``
are provided by the config dataclass itself.
"""

import os
import sys
import json
import csv
import time
import random
import platform
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional

from WarehouseEnv import WarehouseEnv
from agent_registry import VALID_AGENT_NAMES
from simulation import GameSimulator, GameResult, determine_winner
from logging_contract import (
    format_batch_header, format_move_line_batch,
    jsonl_path_for, write_jsonl_sidecar, LOG_VERSION,
)
from config import BatchConfig


def resolve_seeds(config):
    """Determine the list of seeds for the batch.

    Args:
        config: BatchConfig with seed_list_file, seed_start, num_games.
    """
    if config.seed_list_file:
        with open(config.seed_list_file) as f:
            seeds = [int(line.strip()) for line in f if line.strip()]
        if not seeds:
            raise ValueError(
                f"Seed list file '{config.seed_list_file}' is empty"
            )
        return seeds
    seed_start = config.seed_start
    if seed_start is None or seed_start == 0:
        seed_start = random.randint(0, 255)
    return [seed_start + i for i in range(config.num_games)]


def capture_initial_state(env, seed):
    """Capture the initial board state as a string for game logging."""
    lines = [f"Seed: {seed}"]
    for idx, robot in enumerate(env.robots):
        lines.append(
            f"  Robot {idx}: pos={robot.position} "
            f"battery={robot.battery} credit={robot.credit}"
        )
    for idx, pkg in enumerate(env.packages[:2]):
        lines.append(
            f"  Package {idx}: pos={pkg.position} "
            f"dest={pkg.destination} on_board={pkg.on_board}"
        )
    for idx, cs in enumerate(env.charge_stations):
        lines.append(f"  ChargeStation {idx}: pos={cs.position}")
    return '\n'.join(lines)


def save_game_log(entries, game_index, seed, output_dir,
                   jsonl_header=None, jsonl_moves=None, jsonl_result=None):
    """Write a sampled game log to disk with JSONL sidecar."""
    log_dir = os.path.join(output_dir, 'game_logs')
    os.makedirs(log_dir, exist_ok=True)
    filepath = os.path.join(
        log_dir, f'game_{game_index:04d}_seed_{seed}.txt',
    )
    with open(filepath, 'w') as f:
        f.write('\n'.join(entries) + '\n')
    if jsonl_header is not None and jsonl_moves is not None:
        jsonl_fp = jsonl_path_for(filepath)
        write_jsonl_sidecar(
            jsonl_fp, jsonl_header, jsonl_moves, jsonl_result,
        )


def run_single_game(agent0_name, agent1_name, seed, count_steps,
                    time_limit, game_index, log_this_game, output_dir):
    """Run a single game using GameSimulator and return a GameResult."""
    agent_names = [agent0_name, agent1_name]
    game_log_entries = [] if log_this_game else None
    jsonl_moves = [] if log_this_game else None

    if game_log_entries is not None:
        game_log_entries.extend(format_batch_header(
            game_index, agent0_name, agent1_name,
            time_limit, count_steps, seed,
        ))

    env = WarehouseEnv()
    env.generate(seed, 2 * count_steps)

    if game_log_entries is not None:
        game_log_entries.append("--- Initial State ---")
        game_log_entries.append(capture_initial_state(env, seed))
        game_log_entries.append("")
        game_log_entries.append("--- Moves ---")

    def on_turn(round_num, agent_index, agent_name, op, env):
        if game_log_entries is not None:
            game_log_entries.append(
                format_move_line_batch(
                    round_num, agent_index, agent_name, op,
                )
            )
        if jsonl_moves is not None:
            jsonl_moves.append({
                "round": round_num,
                "agent": agent_index,
                "operator": op,
            })

    sim = GameSimulator(
        agent_names=agent_names,
        seed=seed,
        count_steps=count_steps,
        time_limit=time_limit,
        env=env,
    )
    result = sim.run(turn_callback=on_turn)

    if game_log_entries is not None:
        game_log_entries.append("")
        game_log_entries.append("--- Result ---")
        game_log_entries.append(f"Final credits: {result.final_credits}")
        if result.error:
            game_log_entries.append(f"Error: {result.error}")
            game_log_entries.append(f"Error phase: {result.error_phase}")
            game_log_entries.append(f"Error type: {result.error_type}")
        if any(result.timeout_flags):
            game_log_entries.append(
                f"Timeout flags: {result.timeout_flags}"
            )
        if result.error:
            winner_str = "Error (no winner)"
        elif result.winner is not None:
            winner_str = f"Robot {result.winner} wins"
        else:
            winner_str = "Draw"
        game_log_entries.append(f"Outcome: {winner_str}")
        jsonl_header = {
            "seed": seed,
            "count_steps": count_steps,
            "agent_names": [agent0_name, agent1_name],
            "time_limit": time_limit,
        }
        jsonl_result = {
            "final_credits": list(result.final_credits),
            "winner": result.winner,
            "error": result.error,
        }
        save_game_log(
            game_log_entries, game_index, seed, output_dir,
            jsonl_header=jsonl_header, jsonl_moves=jsonl_moves,
            jsonl_result=jsonl_result,
        )

    return result


def percentile(sorted_list, pct):
    """Compute percentile using linear interpolation."""
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_list) - 1)
    return sorted_list[f] + (k - f) * (sorted_list[c] - sorted_list[f])


def compute_summary(config, results):
    """Compute aggregate statistics from game results.

    Args:
        config: BatchConfig with agent0, agent1.
    """
    completed = [r for r in results if r.error is None]
    n = len(completed) if completed else 1
    total = len(results) if results else 1

    credits_0 = sorted([r.final_credits[0] for r in completed])
    credits_1 = sorted([r.final_credits[1] for r in completed])
    all_steps = [r.steps_taken for r in completed]

    return {
        "agent0": config.agent0,
        "agent1": config.agent1,
        "num_games": len(results),
        "num_completed": len(completed),
        "num_errors": len(results) - len(completed),
        "robot0_wins": sum(1 for r in completed if r.winner == 0),
        "robot1_wins": sum(1 for r in completed if r.winner == 1),
        "draws": sum(1 for r in completed if r.winner is None),
        "win_rate_0": round(
            sum(1 for r in completed if r.winner == 0) / n, 4,
        ),
        "win_rate_1": round(
            sum(1 for r in completed if r.winner == 1) / n, 4,
        ),
        "draw_rate": round(
            sum(1 for r in completed if r.winner is None) / n, 4,
        ),
        "mean_credits_0": round(sum(credits_0) / n, 2),
        "mean_credits_1": round(sum(credits_1) / n, 2),
        "p25_credits_0": round(percentile(credits_0, 25), 2),
        "p75_credits_0": round(percentile(credits_0, 75), 2),
        "p25_credits_1": round(percentile(credits_1, 25), 2),
        "p75_credits_1": round(percentile(credits_1, 75), 2),
        "mean_steps": round(sum(all_steps) / n, 2),
        "timeout_rate_0": round(
            sum(1 for r in results if r.timeout_flags[0]) / total, 4,
        ),
        "timeout_rate_1": round(
            sum(1 for r in results if r.timeout_flags[1]) / total, 4,
        ),
        "error_rate": round(
            (len(results) - len(completed)) / total, 4,
        ),
    }


def build_manifest(config, seeds):
    """Build a manifest dict capturing the full batch configuration.

    Args:
        config: BatchConfig with all batch parameters.
    """
    return {
        "created_at": datetime.now().isoformat(),
        "command": config.command or "game_runner_gui",
        "configuration": {
            "agent0": config.agent0,
            "agent1": config.agent1,
            "num_games": len(seeds),
            "time_limit": config.time_limit,
            "count_steps": config.count_steps,
            "fail_fast": config.fail_fast,
            "log_sampling_rate": config.log_sampling_rate,
            "csv_output": config.csv,
        },
        "seed_sequence": seeds,
        "seed_source": (
            f"file:{config.seed_list_file}"
            if config.seed_list_file
            else f"sequential_from:{seeds[0]}"
        ),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    }


def write_manifest(manifest, output_dir):
    filepath = os.path.join(output_dir, 'batch_manifest.json')
    with open(filepath, 'w') as f:
        json.dump(manifest, f, indent=2)


def write_json_summary(summary, results, output_dir, total_wall_time):
    """Write the full JSON summary with metadata, aggregate, and per-game."""
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "agent0": summary["agent0"],
            "agent1": summary["agent1"],
            "num_games_requested": summary["num_games"],
            "num_games_completed": summary["num_completed"],
            "total_wall_time_seconds": round(total_wall_time, 2),
        },
        "aggregate": {
            k: v for k, v in summary.items()
            if k not in (
                "agent0", "agent1", "num_games",
                "num_completed", "num_errors",
            )
        },
        "per_game": [asdict(r) for r in results],
    }
    filepath = os.path.join(output_dir, 'batch_summary.json')
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)


def write_csv_output(results, output_dir):
    """Write per-game results as CSV."""
    filepath = os.path.join(output_dir, 'batch_per_game.csv')
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'game_index', 'seed', 'winner', 'credits_0', 'credits_1',
            'steps_taken', 'timeout_0', 'timeout_1', 'error',
            'error_phase', 'error_type', 'wall_time_seconds',
        ])
        for i, r in enumerate(results):
            writer.writerow([
                i,
                r.seed,
                r.winner if r.winner is not None else (
                    'error' if r.error else 'draw'
                ),
                r.final_credits[0],
                r.final_credits[1],
                r.steps_taken,
                r.timeout_flags[0],
                r.timeout_flags[1],
                r.error or '',
                r.error_phase or '',
                r.error_type or '',
                r.wall_time_seconds,
            ])


def print_final_summary(summary):
    """Print a human-readable summary to stdout."""
    print("")
    print("=" * 50)
    print(f"  Batch Results: {summary['agent0']} vs {summary['agent1']}")
    print("=" * 50)
    print(f"  Games played:    {summary['num_games']}")
    print(f"  Games completed: {summary['num_completed']}")
    print(f"  Errors:          {summary['num_errors']}")
    print("-" * 50)
    print(f"  Robot 0 wins:    {summary['robot0_wins']}"
          f"  ({summary['win_rate_0']:.1%})")
    print(f"  Robot 1 wins:    {summary['robot1_wins']}"
          f"  ({summary['win_rate_1']:.1%})")
    print(f"  Draws:           {summary['draws']}"
          f"  ({summary['draw_rate']:.1%})")
    print("-" * 50)
    print(f"  Mean credits 0:  {summary['mean_credits_0']}"
          f"  (p25={summary['p25_credits_0']},"
          f" p75={summary['p75_credits_0']})")
    print(f"  Mean credits 1:  {summary['mean_credits_1']}"
          f"  (p25={summary['p25_credits_1']},"
          f" p75={summary['p75_credits_1']})")
    print(f"  Mean steps:      {summary['mean_steps']}")
    print(f"  Timeout rate 0:  {summary['timeout_rate_0']:.1%}")
    print(f"  Timeout rate 1:  {summary['timeout_rate_1']:.1%}")
    print(f"  Error rate:      {summary['error_rate']:.1%}")
    print("=" * 50)


def run_batch(config, progress_callback=None):
    """Run a batch of games between two agents.

    Args:
        config: BatchConfig with all batch parameters.
        progress_callback: optional callable(completed, total, results_so_far)
                          called after each game completes.

    Returns:
        (summary_dict, results_list, total_wall_time_seconds)
    """
    # Validate agent names
    for name in (config.agent0, config.agent1):
        if name not in VALID_AGENT_NAMES:
            raise ValueError(
                f"Unknown agent '{name}'. Valid agents: {VALID_AGENT_NAMES}"
            )

    seeds = resolve_seeds(config)
    output_dir = config.output_dir

    os.makedirs(output_dir, exist_ok=True)

    manifest = build_manifest(config, seeds)
    write_manifest(manifest, output_dir)

    results = []
    batch_start = time.monotonic()
    log_sampling_rate = config.log_sampling_rate
    fail_fast = config.fail_fast

    for i, seed in enumerate(seeds):
        log_this_game = (
            log_sampling_rate > 0 and i % log_sampling_rate == 0
        )

        result = run_single_game(
            agent0_name=config.agent0,
            agent1_name=config.agent1,
            seed=seed,
            count_steps=config.count_steps,
            time_limit=config.time_limit,
            game_index=i,
            log_this_game=log_this_game,
            output_dir=output_dir,
        )
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, len(seeds), results)

        if fail_fast and result.error is not None:
            break

    total_wall_time = time.monotonic() - batch_start

    summary = compute_summary(config, results)

    write_json_summary(summary, results, output_dir, total_wall_time)

    if config.csv:
        write_csv_output(results, output_dir)

    return summary, results, total_wall_time
