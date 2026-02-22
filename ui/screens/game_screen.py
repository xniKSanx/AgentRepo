"""Main game play screen with agent execution and move animation."""

import logging
import threading
import traceback as tb_module
from enum import Enum

import pygame

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, DARK_GRAY, WHITE, GREEN, RED,
    get_font,
)
from ui.widgets import Button
from ui.board_renderer import load_icons, render_robot_data, render_board

from WarehouseEnv import WarehouseEnv
from execution import execute_agent_step
from simulation import determine_winner
from game_logger import GameLogger

gui_logger = logging.getLogger("game_runner")


# ---------------------------------------------------------------------------
# Game state enum
# ---------------------------------------------------------------------------

class GameState(Enum):
    READY = "ready"
    WAITING_FOR_INPUT = "waiting"
    COMPUTING = "computing"
    ANIMATING = "animating"
    FINISHED = "finished"
    FINISHED_ERROR = "finished_error"


# ---------------------------------------------------------------------------
# Agent worker (threading)
# ---------------------------------------------------------------------------

class AgentWorker:
    """Runs an agent step asynchronously for the GUI.

    Uses ``threading.Event`` for completion signaling and
    ``threading.Lock`` to guard all cross-thread shared state.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._result = None
        self._thread = None

    def start(self, agent_name, env, agent_id, time_limit):
        self._done_event.clear()
        with self._lock:
            self._result = None
        self._thread = threading.Thread(
            target=self._run,
            args=(agent_name, env, agent_id, time_limit),
            daemon=True,
        )
        self._thread.start()

    def _run(self, agent_name, env, agent_id, time_limit):
        step_result = execute_agent_step(
            agent_name, env, agent_id, time_limit,
        )
        with self._lock:
            self._result = step_result
        self._done_event.set()

    def is_done(self):
        return self._done_event.is_set()

    def get_result(self):
        with self._lock:
            return self._result


# ---------------------------------------------------------------------------
# Game screen
# ---------------------------------------------------------------------------

class GameScreen(Screen):
    def __init__(self, config):
        self.agent_names = [config.agent0, config.agent1]
        self.time_limit = config.time_limit
        self.seed = config.seed
        self.count_steps = config.count_steps
        self.logging_enabled = config.logging_enabled
        self.logger = None

        # Initialize environment
        self.env = WarehouseEnv()
        if config.custom_map_data:
            self.env.load_from_map_data(
                config.custom_map_data, 2 * self.count_steps,
            )
        else:
            self.env.generate(self.seed, 2 * self.count_steps)

        # Initialize logger
        if self.logging_enabled:
            self.logger = GameLogger(config)
            self.logger.log_initial_state(self.env)

        # Load icons
        self.icons = load_icons()

        # Game state
        self.game_state = GameState.READY
        self.current_agent_index = 0
        self.current_round = 1
        self.last_operator = None
        self.last_agent_index = None
        self.auto_run = False
        self.step_mode = None
        self.round_step_needs_second = False

        # Timeout tracking
        self.timeout_flags = [False, False]

        # Animation
        self.animation_start = 0

        # Worker
        self.worker = AgentWorker()

        # Status
        self.status_text = "Ready - choose a run mode below"
        self.result_text = None

        # Buttons
        btn_y = 728
        self.run_btn = Button(
            10, btn_y, 130, 40, "Run Complete", color=GREEN,
            hover_color=(50, 160, 50), text_color=WHITE, font_size=17,
        )
        self.step_move_btn = Button(
            150, btn_y, 120, 40, "Step Move", font_size=17,
        )
        self.step_round_btn = Button(
            280, btn_y, 120, 40, "Step Round", font_size=17,
        )
        self.pause_btn = Button(
            410, btn_y, 100, 40, "Pause", font_size=17,
        )
        self.new_game_btn = Button(
            610, btn_y, 100, 40, "New Game", color=RED,
            hover_color=(190, 50, 50), text_color=WHITE, font_size=16,
        )

        self._update_button_states()

    def _update_button_states(self):
        can_act = self.game_state in (
            GameState.READY, GameState.WAITING_FOR_INPUT,
        )
        self.run_btn.enabled = can_act
        self.step_move_btn.enabled = can_act
        self.step_round_btn.enabled = can_act
        self.pause_btn.enabled = (
            self.auto_run
            and self.game_state in (GameState.COMPUTING, GameState.ANIMATING)
        )
        self.new_game_btn.enabled = True

    def handle_event(self, event):
        if self.run_btn.handle_event(event):
            self.auto_run = True
            self.step_mode = None
            self.round_step_needs_second = False
            self._start_agent_computation()

        elif self.step_move_btn.handle_event(event):
            self.auto_run = False
            self.step_mode = "move"
            self.round_step_needs_second = False
            self._start_agent_computation()

        elif self.step_round_btn.handle_event(event):
            self.auto_run = False
            self.step_mode = "round"
            self.round_step_needs_second = False
            self._start_agent_computation()

        elif self.pause_btn.handle_event(event):
            if self.auto_run:
                self.auto_run = False
                self.status_text = "Paused"

        elif self.new_game_btn.handle_event(event):
            return ScreenId.OPENING

        return None

    def update(self):
        if self.game_state == GameState.COMPUTING:
            if self.worker.is_done():
                step_result = self.worker.get_result()
                if step_result.error:
                    agent_name = self.agent_names[self.current_agent_index]
                    gui_logger.error(
                        "Agent execution error: round=%d, agent=%d (%s): %s",
                        self.current_round, self.current_agent_index,
                        agent_name, step_result.error,
                    )
                    if self.logger:
                        self.logger.log_error(
                            self.current_round,
                            self.current_agent_index,
                            agent_name,
                            step_result.error,
                        )
                    self._finish_game_with_error(
                        f"Agent {self.current_agent_index} ({agent_name}) "
                        f"crashed: {step_result.error}"
                    )
                elif step_result.timed_out:
                    idx = self.current_agent_index
                    agent_name = self.agent_names[idx]
                    self.timeout_flags[idx] = True
                    self.status_text = (
                        f"Agent {idx} ({agent_name}) timed out "
                        f"({step_result.elapsed:.2f}s) - turn forfeited"
                    )
                    if self.logger:
                        self.logger.log_error(
                            self.current_round, idx, agent_name,
                            f"Timeout ({step_result.elapsed:.2f}s)",
                        )
                    self._advance_turn_after_timeout()
                else:
                    self._apply_move(step_result.operator)

        elif self.game_state == GameState.ANIMATING:
            elapsed = pygame.time.get_ticks() - self.animation_start
            anim_delay = 300 if not self.auto_run else 150
            if elapsed >= anim_delay:
                if self.env.done():
                    self._finish_game()
                elif self.auto_run:
                    self._start_agent_computation()
                elif (self.step_mode == "round"
                      and self.round_step_needs_second):
                    self.round_step_needs_second = False
                    self._start_agent_computation()
                else:
                    self.game_state = GameState.WAITING_FOR_INPUT
                    self.status_text = "Waiting for input..."

        self._update_button_states()

    def _start_agent_computation(self):
        agent_name = self.agent_names[self.current_agent_index]
        self.game_state = GameState.COMPUTING
        self.status_text = (
            f"Agent {self.current_agent_index} ({agent_name}) is thinking..."
        )
        self.worker.start(
            agent_name, self.env, self.current_agent_index, self.time_limit,
        )

    def _apply_move(self, operator):
        try:
            self.env.apply_operator(self.current_agent_index, operator)
        except Exception as exc:
            agent_name = self.agent_names[self.current_agent_index]
            error_tb = tb_module.format_exc()
            gui_logger.error(
                "apply_operator failed: round=%d, agent=%d (%s), "
                "operator='%s': %s\n%s",
                self.current_round, self.current_agent_index,
                agent_name, operator, exc, error_tb,
            )
            if self.logger:
                self.logger.log_error(
                    self.current_round,
                    self.current_agent_index,
                    agent_name,
                    f"apply_operator exception: {type(exc).__name__}: {exc}",
                )
            self._finish_game_with_error(
                f"Move error: {type(exc).__name__}: {exc}  "
                f"(round {self.current_round}, "
                f"agent {self.current_agent_index} "
                f"[{agent_name}], operator '{operator}')"
            )
            return

        if self.logger:
            self.logger.log_move(
                self.current_round,
                self.current_agent_index,
                self.agent_names[self.current_agent_index],
                operator,
                self.env,
            )
        self.last_operator = operator
        self.last_agent_index = self.current_agent_index

        # Advance turn
        prev_agent = self.current_agent_index
        self.current_agent_index = (self.current_agent_index + 1) % 2
        if self.current_agent_index == 0:
            self.current_round += 1

        self.status_text = (
            f"Agent {prev_agent} ({self.agent_names[prev_agent]}) "
            f"chose: {operator}"
        )

        if self.env.done():
            self.game_state = GameState.ANIMATING
            self.animation_start = pygame.time.get_ticks()
            return

        if self.step_mode == "round" and prev_agent == 0:
            self.round_step_needs_second = True

        self.game_state = GameState.ANIMATING
        self.animation_start = pygame.time.get_ticks()

    def _advance_turn_after_timeout(self):
        prev_agent = self.current_agent_index
        self.current_agent_index = (self.current_agent_index + 1) % 2
        if self.current_agent_index == 0:
            self.current_round += 1

        if self.step_mode == "round" and prev_agent == 0:
            self.round_step_needs_second = True

        self.game_state = GameState.ANIMATING
        self.animation_start = pygame.time.get_ticks()

    def _finish_game(self):
        self.game_state = GameState.FINISHED
        self.auto_run = False
        try:
            balances = self.env.get_balances()
        except Exception as exc:
            gui_logger.warning(
                "get_balances failed during finish (seed=%d): %s",
                self.seed, exc, exc_info=True,
            )
            self._finish_game_with_error(
                f"get_balances failed: {type(exc).__name__}: {exc}"
            )
            return
        winner = determine_winner(balances)
        if winner is None:
            self.result_text = f"Draw!  ({balances[0]} vs {balances[1]})"
        else:
            self.result_text = (
                f"Robot {winner} - {self.agent_names[winner]} "
                f"({'Blue' if winner == 0 else 'Red'}) wins!  "
                f"({balances[0]} vs {balances[1]})"
            )
        timeout_info = ""
        if any(self.timeout_flags):
            parts = []
            for i, flagged in enumerate(self.timeout_flags):
                if flagged:
                    parts.append(f"Agent {i} ({self.agent_names[i]})")
            timeout_info = f"  [Timeouts: {', '.join(parts)}]"
        self.status_text = "Game Over" + timeout_info
        if self.logger:
            self.logger.log_result(self.result_text, balances)
            try:
                saved_path = self.logger.save()
                self.status_text = (
                    f"Game Over - Log saved to {saved_path}"
                )
            except OSError as e:
                self.status_text = (
                    f"Game Over - Failed to save log: {e}"
                )

    def _finish_game_with_error(self, error_message):
        self.game_state = GameState.FINISHED_ERROR
        self.auto_run = False
        self.result_text = f"ERROR: {error_message}"
        self.status_text = "Game ended due to error"
        if self.logger:
            self.logger.log_result(f"ERROR: {error_message}", [0, 0])
            try:
                saved_path = self.logger.save()
                self.status_text = (
                    f"Game ended due to error - Log saved to {saved_path}"
                )
            except OSError as e:
                self.status_text = (
                    f"Game ended due to error - Failed to save log: {e}"
                )

    def draw(self, surface):
        # Title
        title_font = get_font(26, bold=True)
        title = title_font.render("AI Warehouse", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=10))

        # Subtitle (matchup)
        sub_font = get_font(16)
        sub = sub_font.render(
            f"{self.agent_names[0]} (Blue)  vs  {self.agent_names[1]} (Red)",
            True, DARK_GRAY,
        )
        surface.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, y=42))

        # Robot data
        render_robot_data(surface, self.env, self.icons)

        # Board
        render_board(surface, self.env, self.icons)

        # Turn info line
        self._draw_turn_info(surface)

        # Control buttons
        self.run_btn.draw(surface)
        self.step_move_btn.draw(surface)
        self.step_round_btn.draw(surface)
        self.pause_btn.draw(surface)
        self.new_game_btn.draw(surface)

        # Status / result
        self._draw_status(surface)

    def _draw_turn_info(self, surface):
        font = get_font(16)
        info_parts = [f"Round: {self.current_round}/{self.count_steps}"]
        if self.last_operator is not None:
            info_parts.append(
                f"Agent {self.last_agent_index} "
                f"({self.agent_names[self.last_agent_index]}) "
                f"chose: {self.last_operator}"
            )
        info_text = "  |  ".join(info_parts)
        text_surf = font.render(info_text, True, BLACK)
        surface.blit(text_surf, (15, 698))

    def _draw_status(self, surface):
        if self.game_state == GameState.FINISHED and self.result_text:
            banner_rect = pygame.Rect(10, 778, WINDOW_WIDTH - 20, 60)
            pygame.draw.rect(
                surface, (40, 40, 40), banner_rect, border_radius=8,
            )
            font = get_font(22, bold=True)
            text = font.render(self.result_text, True, WHITE)
            surface.blit(text, text.get_rect(center=banner_rect.center))
        elif (self.game_state == GameState.FINISHED_ERROR
              and self.result_text):
            banner_rect = pygame.Rect(10, 778, WINDOW_WIDTH - 20, 60)
            pygame.draw.rect(
                surface, (160, 30, 30), banner_rect, border_radius=8,
            )
            font = get_font(18, bold=True)
            display_text = self.result_text
            if len(display_text) > 80:
                display_text = display_text[:77] + "..."
            text = font.render(display_text, True, WHITE)
            surface.blit(text, text.get_rect(center=banner_rect.center))
        else:
            font = get_font(16)
            text = font.render(self.status_text, True, DARK_GRAY)
            surface.blit(text, (15, 790))
