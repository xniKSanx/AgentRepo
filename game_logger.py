"""Game logger for the GUI single-game mode.

This module does NOT import pygame — it is a core module that records
game events and writes log files with JSONL sidecars.
"""

import os
from datetime import datetime

from logging_contract import (
    format_gui_header, format_move_line_gui, jsonl_path_for,
    write_jsonl_sidecar,
)


class GameLogger:
    """Records game events and saves human-readable logs + JSONL sidecars."""

    def __init__(self, config):
        self.entries = []
        self.config = config
        self._jsonl_moves = []
        self._jsonl_result = None
        self._log_header()

    def _log_header(self):
        # config may be a GameConfig dataclass or a dict — handle both
        cfg = self.config
        if hasattr(cfg, "agent0"):
            header_dict = {
                "agent0": cfg.agent0,
                "agent1": cfg.agent1,
                "time_limit": cfg.time_limit,
                "seed": cfg.seed,
                "count_steps": cfg.count_steps,
            }
        else:
            header_dict = cfg
        self.entries.extend(format_gui_header(header_dict))

    def log_initial_state(self, env):
        self.entries.append("--- INITIAL STATE ---")
        for i, robot in enumerate(env.robots):
            self.entries.append(
                f"  Robot {i}: position={robot.position}, "
                f"battery={robot.battery}, credit={robot.credit}"
            )
        for i, pkg in enumerate(env.packages[:2]):
            self.entries.append(
                f"  Package {i}: position={pkg.position}, "
                f"destination={pkg.destination}, on_board={pkg.on_board}"
            )
        for i, cs in enumerate(env.charge_stations):
            self.entries.append(
                f"  Charge Station {i}: position={cs.position}"
            )
        self.entries.append("")

    def log_move(self, round_num, agent_index, agent_name, operator, env):
        self.entries.append(
            format_move_line_gui(round_num, agent_index, agent_name, operator)
        )
        for i, robot in enumerate(env.robots):
            pkg_info = ""
            if robot.package is not None:
                pkg_info = (
                    f", carrying=({robot.package.position}"
                    f"->{robot.package.destination})"
                )
            self.entries.append(
                f"  Robot {i}: pos={robot.position}, "
                f"bat={robot.battery}, cred={robot.credit}{pkg_info}"
            )
        self._jsonl_moves.append({
            "round": round_num,
            "agent": agent_index,
            "operator": operator,
        })

    def log_error(self, round_num, agent_index, agent_name, error):
        self.entries.append(
            f"[Round {round_num}] Agent {agent_index} ({agent_name}): "
            f"ERROR - {error}"
        )

    def log_result(self, result_text, balances):
        self.entries.append("")
        self.entries.append("=" * 60)
        self.entries.append("GAME RESULT")
        self.entries.append("=" * 60)
        self.entries.append(
            f"Final Balances: Agent 0 = {balances[0]}, Agent 1 = {balances[1]}"
        )
        self.entries.append(f"Result: {result_text}")
        self.entries.append("=" * 60)
        winner = None
        if balances[0] > balances[1]:
            winner = 0
        elif balances[1] > balances[0]:
            winner = 1
        is_error = result_text.startswith("ERROR")
        self._jsonl_result = {
            "final_credits": list(balances),
            "winner": winner,
            "error": result_text if is_error else None,
        }

    def save(self, directory="game_logs"):
        os.makedirs(directory, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cfg = self.config
        if hasattr(cfg, "agent0"):
            agent0 = cfg.agent0
            agent1 = cfg.agent1
            seed = cfg.seed
        else:
            agent0 = cfg["agent0"]
            agent1 = cfg["agent1"]
            seed = cfg["seed"]
        filename = f"game_{agent0}_vs_{agent1}_seed{seed}_{timestamp}.txt"
        filepath = os.path.join(directory, filename)
        with open(filepath, "w") as f:
            f.write("\n".join(self.entries) + "\n")
        jsonl_fp = jsonl_path_for(filepath)
        if hasattr(cfg, "count_steps"):
            header = {
                "seed": cfg.seed,
                "count_steps": cfg.count_steps,
                "agent_names": [cfg.agent0, cfg.agent1],
                "time_limit": cfg.time_limit,
            }
        else:
            header = {
                "seed": cfg["seed"],
                "count_steps": cfg["count_steps"],
                "agent_names": [cfg["agent0"], cfg["agent1"]],
                "time_limit": cfg["time_limit"],
            }
        write_jsonl_sidecar(
            jsonl_fp, header, self._jsonl_moves, self._jsonl_result
        )
        return filepath
