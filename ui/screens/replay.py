"""Visual replay screen with VCR-style controls."""

import os

import pygame

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, DARK_GRAY, LIGHT_GRAY,
    BLUE, GREEN, RED, WHITE,
    get_font,
)
from ui.widgets import Button
from ui.board_renderer import load_icons, render_robot_data, render_board


class ReplayScreen(Screen):
    """Visual replay of a recorded game with VCR-style controls."""

    SPEED_OPTIONS = [1, 2, 4, 8]
    SPEED_DELAYS = {1: 500, 2: 250, 4: 125, 8: 60}

    def __init__(self, engine, filepath):
        self.engine = engine
        self.filepath = filepath
        self.icons = load_icons()

        # Auto-play state
        self.playing = False
        self.speed_index = 0
        self.last_step_time = 0

        # Control buttons
        btn_y = 728
        self.start_btn = Button(30, btn_y, 55, 40, "|<", font_size=18)
        self.back_step_btn = Button(90, btn_y, 55, 40, "<", font_size=20)
        self.fwd_step_btn = Button(150, btn_y, 55, 40, ">", font_size=20)
        self.end_btn = Button(210, btn_y, 55, 40, ">|", font_size=18)
        self.play_btn = Button(
            280, btn_y, 90, 40, "Play", color=GREEN,
            hover_color=(50, 160, 50), text_color=WHITE, font_size=18,
        )
        self.speed_btn = Button(380, btn_y, 70, 40, "1x", font_size=18)
        self.menu_btn = Button(
            580, btn_y, 110, 40, "Menu", color=RED,
            hover_color=(190, 50, 50), text_color=WHITE, font_size=18,
        )

        # Progress bar
        self.progress_rect = pygame.Rect(60, 785, 600, 20)

    def handle_event(self, event):
        if self.start_btn.handle_event(event):
            self.engine.go_to_start()
            self.playing = False
        elif self.back_step_btn.handle_event(event):
            self.engine.step_backward()
            self.playing = False
        elif self.fwd_step_btn.handle_event(event):
            self.engine.step_forward()
        elif self.end_btn.handle_event(event):
            self.engine.go_to_end()
            self.playing = False
        elif self.play_btn.handle_event(event):
            if self.engine.is_at_end():
                self.engine.go_to_start()
            self.playing = not self.playing
            self.last_step_time = pygame.time.get_ticks()
        elif self.speed_btn.handle_event(event):
            self.speed_index = (
                (self.speed_index + 1) % len(self.SPEED_OPTIONS)
            )
        elif self.menu_btn.handle_event(event):
            return ScreenId.OPENING

        # Progress bar click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.progress_rect.collidepoint(event.pos):
                total = self.engine.total_moves
                if total > 0:
                    fraction = (
                        (event.pos[0] - self.progress_rect.x)
                        / self.progress_rect.width
                    )
                    target = int(fraction * total)
                    self.engine.go_to_index(target)
                    self.playing = False

        return None

    def update(self):
        if self.playing:
            now = pygame.time.get_ticks()
            delay = self.SPEED_DELAYS[
                self.SPEED_OPTIONS[self.speed_index]
            ]
            if now - self.last_step_time >= delay:
                if not self.engine.step_forward():
                    self.playing = False
                self.last_step_time = now

    def draw(self, surface):
        # Title
        title_font = get_font(26, bold=True)
        title = title_font.render("AI Warehouse - Replay", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=10))

        # Subtitle with agent names
        sub_font = get_font(16)
        names = self.engine.data.agent_names
        sub = sub_font.render(
            f"{names[0]} (Blue) vs {names[1]} (Red)", True, DARK_GRAY,
        )
        surface.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, y=42))

        # Board rendering
        render_robot_data(surface, self.engine.current_env, self.icons)
        render_board(surface, self.engine.current_env, self.icons)

        # Turn info line
        self._draw_turn_info(surface)

        # Control buttons
        self._update_button_labels()
        for btn in [self.start_btn, self.back_step_btn, self.fwd_step_btn,
                     self.end_btn, self.play_btn, self.speed_btn,
                     self.menu_btn]:
            btn.draw(surface)

        # Progress bar
        self._draw_progress_bar(surface)

        # Status line
        self._draw_status(surface)

    def _update_button_labels(self):
        self.play_btn.text = "Pause" if self.playing else "Play"
        self.speed_btn.text = f"{self.SPEED_OPTIONS[self.speed_index]}x"

    def _draw_turn_info(self, surface):
        font = get_font(16)
        idx = self.engine.current_index
        total = self.engine.total_moves
        round_num = self.engine.current_round

        parts = [f"Move: {idx}/{total}", f"Round: {round_num}"]
        move_info = self.engine.current_move_info
        if move_info:
            agent_idx, op = move_info
            agent_name = self.engine.data.agent_names[agent_idx]
            parts.append(f"Agent {agent_idx} ({agent_name}): {op}")
        else:
            parts.append("Initial State")

        text = "  |  ".join(parts)
        surface.blit(font.render(text, True, BLACK), (15, 700))

    def _draw_progress_bar(self, surface):
        pygame.draw.rect(
            surface, LIGHT_GRAY, self.progress_rect, border_radius=4,
        )
        pygame.draw.rect(
            surface, DARK_GRAY, self.progress_rect, width=1,
            border_radius=4,
        )

        total = self.engine.total_moves
        if total > 0:
            fill_w = int(
                self.progress_rect.width
                * self.engine.current_index / total
            )
            if fill_w > 0:
                fill_rect = pygame.Rect(
                    self.progress_rect.x, self.progress_rect.y,
                    fill_w, self.progress_rect.height,
                )
                pygame.draw.rect(
                    surface, BLUE, fill_rect, border_radius=4,
                )

        font = get_font(13)
        label = font.render(
            f"{self.engine.current_index}/{total}", True, BLACK,
        )
        surface.blit(
            label, label.get_rect(center=self.progress_rect.center),
        )

    def _draw_status(self, surface):
        font = get_font(14)
        filename = os.path.basename(self.filepath)
        text = font.render(f"Replaying: {filename}", True, DARK_GRAY)
        surface.blit(text, (15, 815))
