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
import Agent
import submission


def build_agents():
    """Build and return the agent name-to-instance dictionary."""
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


@dataclass
class GameResult:
    game_index: int
    seed: int
    winner: Optional[int]           # 0, 1, or None for draw
    final_credits: List[int]        # [credit0, credit1]
    steps_taken: int
    timeout_flags: List[bool]       # [agent0_timed_out, agent1_timed_out]
    error: Optional[str]            # None if no error, else error message
    wall_time_seconds: float


def resolve_seeds(args):
    """Determine the list of seeds for the batch."""
    if args.seed_list_file:
        with open(args.seed_list_file) as f:
            seeds = [int(line.strip()) for line in f if line.strip()]
        if not seeds:
            raise ValueError(f"Seed list file '{args.seed_list_file}' is empty")
        return seeds
    seed_start = args.seed_start if args.seed_start is not None else random.randint(0, 255)
    return [seed_start + i for i in range(args.num_games)]


def capture_initial_state(env, seed):
    """Capture the initial board state as a string for game logging."""
    lines = [f"Seed: {seed}"]
    for idx, robot in enumerate(env.robots):
        lines.append(f"  Robot {idx}: pos={robot.position} battery={robot.battery} credit={robot.credit}")
    for idx, pkg in enumerate(env.packages[:2]):
        lines.append(f"  Package {idx}: pos={pkg.position} dest={pkg.destination} on_board={pkg.on_board}")
    for idx, cs in enumerate(env.charge_stations):
        lines.append(f"  ChargeStation {idx}: pos={cs.position}")
    return '\n'.join(lines)


def save_game_log(entries, game_index, seed, output_dir):
    """Write a sampled game log to disk."""
    log_dir = os.path.join(output_dir, 'game_logs')
    os.makedirs(log_dir, exist_ok=True)
    filepath = os.path.join(log_dir, f'game_{game_index:04d}_seed_{seed}.txt')
    with open(filepath, 'w') as f:
        f.write('\n'.join(entries) + '\n')


def run_single_game(agent0_name, agent1_name, seed, count_steps,
                    time_limit, game_index, log_this_game, output_dir):
    """Run a single game and return a GameResult.

    Agents are re-instantiated per game to avoid state leakage
    (e.g. AgentHardCoded.step).
    """
    agents = build_agents()
    agent_names = [agent0_name, agent1_name]
    env = WarehouseEnv()
    timeout_flags = [False, False]
    error_msg = None
    steps_taken = 0
    game_log_entries = [] if log_this_game else None

    wall_start = time.time()

    try:
        env.generate(seed, 2 * count_steps)

        if game_log_entries is not None:
            game_log_entries.append(f"=== Game {game_index} ===")
            game_log_entries.append(f"Agents: {agent0_name} vs {agent1_name}")
            game_log_entries.append(f"Config: time_limit={time_limit}, count_steps={count_steps}")
            game_log_entries.append("")
            game_log_entries.append("--- Initial State ---")
            game_log_entries.append(capture_initial_state(env, seed))
            game_log_entries.append("")
            game_log_entries.append("--- Moves ---")

        for step in range(count_steps):
            for i, agent_name in enumerate(agent_names):
                agent = agents[agent_name]
                start = time.time()
                try:
                    op = agent.run_step(env, i, time_limit)
                except Exception as agent_err:
                    raise RuntimeError(
                        f"Agent {i} ({agent_name}) crashed: {agent_err}"
                    ) from agent_err

                elapsed = time.time() - start
                if elapsed > time_limit:
                    timeout_flags[i] = True

                env.apply_operator(i, op)
                steps_taken += 1

                if game_log_entries is not None:
                    game_log_entries.append(
                        f"  Round {step}, Agent {i} ({agent_name}): {op}"
                    )

            if env.done():
                break

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"

    wall_time = time.time() - wall_start

    try:
        balances = env.get_balances()
    except Exception:
        balances = [0, 0]

    # Determine winner
    if error_msg is not None:
        winner = None
    elif balances[0] > balances[1]:
        winner = 0
    elif balances[1] > balances[0]:
        winner = 1
    else:
        winner = None  # draw

    # Finalize and save game log if sampled
    if game_log_entries is not None:
        game_log_entries.append("")
        game_log_entries.append("--- Result ---")
        game_log_entries.append(f"Final credits: {balances}")
        if error_msg:
            game_log_entries.append(f"Error: {error_msg}")
        if any(timeout_flags):
            game_log_entries.append(f"Timeout flags: {timeout_flags}")
        winner_str = f"Robot {winner} wins" if winner is not None else "Draw"
        if error_msg:
            winner_str = "Error (no winner)"
        game_log_entries.append(f"Outcome: {winner_str}")
        save_game_log(game_log_entries, game_index, seed, output_dir)

    return GameResult(
        game_index=game_index,
        seed=seed,
        winner=winner,
        final_credits=balances,
        steps_taken=steps_taken,
        timeout_flags=timeout_flags,
        error=error_msg,
        wall_time_seconds=round(wall_time, 4),
    )


def percentile(sorted_list, pct):
    """Compute percentile using linear interpolation. No numpy needed."""
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_list) - 1)
    return sorted_list[f] + (k - f) * (sorted_list[c] - sorted_list[f])


def compute_summary(args, results):
    """Compute aggregate statistics from game results."""
    completed = [r for r in results if r.error is None]
    n = len(completed) if completed else 1  # avoid division by zero
    total = len(results) if results else 1

    credits_0 = sorted([r.final_credits[0] for r in completed])
    credits_1 = sorted([r.final_credits[1] for r in completed])
    all_steps = [r.steps_taken for r in completed]

    return {
        "agent0": args.agent0,
        "agent1": args.agent1,
        "num_games": len(results),
        "num_completed": len(completed),
        "num_errors": len(results) - len(completed),
        "robot0_wins": sum(1 for r in completed if r.winner == 0),
        "robot1_wins": sum(1 for r in completed if r.winner == 1),
        "draws": sum(1 for r in completed if r.winner is None),
        "win_rate_0": round(sum(1 for r in completed if r.winner == 0) / n, 4),
        "win_rate_1": round(sum(1 for r in completed if r.winner == 1) / n, 4),
        "draw_rate": round(sum(1 for r in completed if r.winner is None) / n, 4),
        "mean_credits_0": round(sum(credits_0) / n, 2),
        "mean_credits_1": round(sum(credits_1) / n, 2),
        "p25_credits_0": round(percentile(credits_0, 25), 2),
        "p75_credits_0": round(percentile(credits_0, 75), 2),
        "p25_credits_1": round(percentile(credits_1, 25), 2),
        "p75_credits_1": round(percentile(credits_1, 75), 2),
        "mean_steps": round(sum(all_steps) / n, 2),
        "timeout_rate_0": round(sum(1 for r in results if r.timeout_flags[0]) / total, 4),
        "timeout_rate_1": round(sum(1 for r in results if r.timeout_flags[1]) / total, 4),
        "error_rate": round((len(results) - len(completed)) / total, 4),
    }


def build_manifest(args, seeds):
    """Build a manifest dict capturing the full batch configuration."""
    return {
        "created_at": datetime.now().isoformat(),
        "command": " ".join(sys.argv),
        "configuration": {
            "agent0": args.agent0,
            "agent1": args.agent1,
            "num_games": len(seeds),
            "time_limit": args.time_limit,
            "count_steps": args.count_steps,
            "fail_fast": args.fail_fast,
            "log_sampling_rate": args.log_sampling_rate,
            "csv_output": args.csv,
        },
        "seed_sequence": seeds,
        "seed_source": (
            f"file:{args.seed_list_file}" if args.seed_list_file
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
    print(f"[Batch] Manifest written to {filepath}", file=sys.stderr)


def write_json_summary(summary, results, output_dir, total_wall_time):
    """Write the full JSON summary with metadata, aggregate, and per-game results."""
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "agent0": summary["agent0"],
            "agent1": summary["agent1"],
            "num_games_requested": summary["num_games"],
            "num_games_completed": summary["num_completed"],
            "total_wall_time_seconds": round(total_wall_time, 2),
        },
        "aggregate": {k: v for k, v in summary.items()
                      if k not in ("agent0", "agent1", "num_games", "num_completed", "num_errors")},
        "per_game": [asdict(r) for r in results],
    }
    filepath = os.path.join(output_dir, 'batch_summary.json')
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"[Batch] Summary written to {filepath}", file=sys.stderr)


def write_csv_output(results, output_dir):
    """Write per-game results as CSV."""
    filepath = os.path.join(output_dir, 'batch_per_game.csv')
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'game_index', 'seed', 'winner', 'credits_0', 'credits_1',
            'steps_taken', 'timeout_0', 'timeout_1', 'error', 'wall_time_seconds'
        ])
        for r in results:
            writer.writerow([
                r.game_index,
                r.seed,
                r.winner if r.winner is not None else 'draw',
                r.final_credits[0],
                r.final_credits[1],
                r.steps_taken,
                r.timeout_flags[0],
                r.timeout_flags[1],
                r.error or '',
                r.wall_time_seconds,
            ])
    print(f"[Batch] CSV written to {filepath}", file=sys.stderr)


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
    print(f"  Robot 0 wins:    {summary['robot0_wins']}  ({summary['win_rate_0']:.1%})")
    print(f"  Robot 1 wins:    {summary['robot1_wins']}  ({summary['win_rate_1']:.1%})")
    print(f"  Draws:           {summary['draws']}  ({summary['draw_rate']:.1%})")
    print("-" * 50)
    print(f"  Mean credits 0:  {summary['mean_credits_0']}  (p25={summary['p25_credits_0']}, p75={summary['p75_credits_0']})")
    print(f"  Mean credits 1:  {summary['mean_credits_1']}  (p25={summary['p25_credits_1']}, p75={summary['p75_credits_1']})")
    print(f"  Mean steps:      {summary['mean_steps']}")
    print(f"  Timeout rate 0:  {summary['timeout_rate_0']:.1%}")
    print(f"  Timeout rate 1:  {summary['timeout_rate_1']:.1%}")
    print(f"  Error rate:      {summary['error_rate']:.1%}")
    print("=" * 50)


def run_batch(args):
    """Main entry point for the batch subcommand."""
    # Validate agent names
    for name_attr in ('agent0', 'agent1'):
        name = getattr(args, name_attr)
        if name not in VALID_AGENT_NAMES:
            print(f"Error: Unknown agent '{name}'. Valid agents: {VALID_AGENT_NAMES}",
                  file=sys.stderr)
            sys.exit(1)

    # Resolve seeds
    seeds = resolve_seeds(args)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Write manifest before running
    manifest = build_manifest(args, seeds)
    write_manifest(manifest, args.output_dir)

    # Run games
    results = []
    progress_interval = max(1, len(seeds) // 10)
    batch_start = time.time()

    print(f"[Batch] Starting {len(seeds)} games: {args.agent0} vs {args.agent1}",
          file=sys.stderr)

    for i, seed in enumerate(seeds):
        # Progress reporting
        if i > 0 and i % progress_interval == 0:
            pct = (i / len(seeds)) * 100
            wins_0 = sum(1 for r in results if r.winner == 0)
            wins_1 = sum(1 for r in results if r.winner == 1)
            errors = sum(1 for r in results if r.error is not None)
            print(f"[Progress] {pct:.0f}% ({i}/{len(seeds)}) | "
                  f"W0:{wins_0} W1:{wins_1} E:{errors}",
                  file=sys.stderr)

        # Determine if this game should be logged
        log_this_game = (args.log_sampling_rate > 0
                         and i % args.log_sampling_rate == 0)

        result = run_single_game(
            agent0_name=args.agent0,
            agent1_name=args.agent1,
            seed=seed,
            count_steps=args.count_steps,
            time_limit=args.time_limit,
            game_index=i,
            log_this_game=log_this_game,
            output_dir=args.output_dir,
        )
        results.append(result)

        # Fail-fast check
        if args.fail_fast and result.error is not None:
            print(f"[FAIL FAST] Aborting batch at game {i} due to error: "
                  f"{result.error}", file=sys.stderr)
            break

    total_wall_time = time.time() - batch_start

    # Compute aggregate statistics
    summary = compute_summary(args, results)

    # Write outputs
    write_json_summary(summary, results, args.output_dir, total_wall_time)

    if args.csv:
        write_csv_output(results, args.output_dir)

    # Print final summary to stdout
    print_final_summary(summary)

    print(f"\n[Batch] Complete. Output in {args.output_dir}/", file=sys.stderr)
