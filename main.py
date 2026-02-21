import random
import sys

from WarehouseEnv import WarehouseEnv
import argparse

from simulation import GameSimulator


def build_parser():
    parser = argparse.ArgumentParser(
        description='AI Warehouse: test agents against each other.'
    )
    subparsers = parser.add_subparsers(dest='command')

    # ---- "run" subcommand (existing single-game / tournament behavior) ----
    run_parser = subparsers.add_parser('run', help='Run a single game or tournament')
    run_parser.add_argument('agent0', type=str, help='First agent')
    run_parser.add_argument('agent1', type=str, help='Second agent')
    run_parser.add_argument('-t', '--time_limit', type=float, nargs='?',
                            help='Time limit for each turn in seconds', default=1)
    run_parser.add_argument('-s', '--seed', nargs='?', type=int,
                            help='Seed to be used for generating the game', default=None)
    run_parser.add_argument('-c', '--count_steps', nargs='?', type=int,
                            help='Number of steps each robot gets before game is over',
                            default=4761)
    run_parser.add_argument('--console_print', action='store_true')
    run_parser.add_argument('--tournament', action='store_true')

    # ---- "batch" subcommand (new) ----
    batch_parser = subparsers.add_parser('batch', help='Run a batch of games with stats output')
    batch_parser.add_argument('agent0', type=str, help='First agent')
    batch_parser.add_argument('agent1', type=str, help='Second agent')
    batch_parser.add_argument('-n', '--num_games', type=int, default=100,
                              help='Number of games to run (default: 100)')
    batch_parser.add_argument('-s', '--seed_start', type=int, default=None,
                              help='Starting seed; games use seed_start, seed_start+1, ...')
    batch_parser.add_argument('--seed_list_file', type=str, default=None,
                              help='Path to text file with one seed per line (overrides --seed_start)')
    batch_parser.add_argument('-t', '--time_limit', type=float, default=1.0,
                              help='Time limit for each turn in seconds (default: 1.0)')
    batch_parser.add_argument('-c', '--count_steps', type=int, default=4761,
                              help='Number of steps each robot gets before game is over (default: 4761)')
    batch_parser.add_argument('-o', '--output_dir', type=str, default='batch_results',
                              help='Directory for output files (default: batch_results)')
    batch_parser.add_argument('--log_sampling_rate', type=int, default=0,
                              help='Save full game log for 1 out of every N games (0=off, default: 0)')
    batch_parser.add_argument('--fail_fast', action='store_true', default=False,
                              help='Abort entire batch on first game error')
    batch_parser.add_argument('--csv', action='store_true', default=False,
                              help='Also produce per-game CSV output')

    return parser


def detect_and_normalize_argv():
    """If user invokes old-style 'python main.py alphabeta greedy ...',
    detect absence of subcommand and prepend 'run'."""
    known_subcommands = {'run', 'batch'}
    args = sys.argv[1:]
    if not args:
        return args
    if args[0] not in known_subcommands and not args[0].startswith('-'):
        return ['run'] + args
    return args


def run_single_or_tournament(args):
    if args.seed is None:
        args.seed = random.randint(0, 255)

    agent_names = [args.agent0, args.agent1]
    env = WarehouseEnv()

    if not args.tournament:
        # --- Single game using GameSimulator ---
        def on_turn(round_num, agent_index, agent_name, op, env):
            if args.console_print:
                print('robot ' + str(agent_index) + ' chose ' + op)
                env.print()

        env.generate(args.seed, 2 * args.count_steps)

        if args.console_print:
            print('initial board:')
            env.print()

        sim = GameSimulator(
            agent_names=agent_names,
            seed=args.seed,
            count_steps=args.count_steps,
            time_limit=args.time_limit,
            env=env,
        )
        result = sim.run(turn_callback=on_turn)

        print(result.final_credits)
        if result.winner is None:
            print('draw')
        else:
            print('robot', result.winner, 'wins!')
    else:
        # --- Tournament mode ---
        robot0_wins = 0
        robot1_wins = 0
        draws = 0
        num_of_games = 100

        for i in range(num_of_games):
            game_seed = args.seed + i

            def on_turn(round_num, agent_index, agent_name, op, env):
                if args.console_print:
                    print('robot ' + str(agent_index) + ' chose ' + op)
                    env.print()

            game_env = WarehouseEnv()
            game_env.generate(game_seed, 2 * args.count_steps)

            if args.console_print:
                print('initial board:')
                game_env.print()

            sim = GameSimulator(
                agent_names=agent_names,
                seed=game_seed,
                count_steps=args.count_steps,
                time_limit=args.time_limit,
                env=game_env,
            )
            result = sim.run(turn_callback=on_turn)

            if result.winner is None:
                draws += 1
            elif result.winner == 0:
                robot0_wins += 1
            else:
                robot1_wins += 1

        print("Robot 0 wins: ", robot0_wins)
        print("Robot 1 wins: ", robot1_wins)
        print("Draws: ", draws)


def run_agents():
    parser = build_parser()
    args = parser.parse_args(detect_and_normalize_argv())

    if args.command == 'batch':
        from batch_runner import run_batch, print_final_summary
        config = vars(args)
        config["command"] = " ".join(sys.argv)
        summary, results, wall_time = run_batch(config)
        print_final_summary(summary)
        print(f"\n[Batch] Complete. Output in {config.get('output_dir', 'batch_results')}/",
              file=sys.stderr)
    elif args.command == 'run':
        run_single_or_tournament(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    run_agents()
