"""Batch run setup screen."""

import pygame

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, GRAY, BLUE, RED, GREEN, WHITE,
    get_font,
)
from ui.widgets import Button, Dropdown, NumberInput, Checkbox
from agent_registry import VALID_AGENT_NAMES
from config import BatchConfig


class BatchSetupScreen(Screen):
    def __init__(self):
        self.dropdown0 = Dropdown(
            160, 165, 400, 40, VALID_AGENT_NAMES, default_index=0,
        )
        self.dropdown1 = Dropdown(
            160, 255, 400, 40, VALID_AGENT_NAMES, default_index=1,
        )

        self.time_input = NumberInput(
            160, 340, "Time Limit (s):", 1.0, 0.1, 30.0, step=0.5,
            is_float=True,
        )
        self.steps_input = NumberInput(
            160, 400, "Max Rounds:", 200, 10, 99999, step=10,
        )

        self.num_games_input = NumberInput(
            160, 480, "Num Games:", 100, 1, 10000, step=10,
        )
        self.log_rate_input = NumberInput(
            160, 540, "Log Sample Rate:", 0, 0, 1000, step=1,
        )
        self.csv_checkbox = Checkbox(160, 600, "Save CSV Output")

        self.back_btn = Button(160, 670, 140, 45, "Back", font_size=20)
        self.start_btn = Button(
            420, 670, 140, 45, "Start", color=GREEN,
            hover_color=(50, 160, 50), text_color=WHITE, font_size=22,
        )

    def handle_event(self, event):
        # Handle expanded dropdowns first
        if self.dropdown0.is_expanded():
            self.dropdown0.handle_event(event)
            return None
        if self.dropdown1.is_expanded():
            self.dropdown1.handle_event(event)
            return None

        self.dropdown0.handle_event(event)
        self.dropdown1.handle_event(event)

        self.time_input.handle_event(event)
        self.steps_input.handle_event(event)
        self.num_games_input.handle_event(event)
        self.log_rate_input.handle_event(event)
        self.csv_checkbox.handle_event(event)

        if self.back_btn.handle_event(event):
            return ScreenId.OPENING
        if self.start_btn.handle_event(event):
            return (ScreenId.BATCH, {"config": self.get_config()})
        return None

    def draw(self, surface):
        title_font = get_font(28, bold=True)
        title = title_font.render("Batch Check Setup", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=60))

        pygame.draw.line(surface, GRAY, (140, 110), (580, 110), width=1)

        label_font = get_font(22, bold=True)
        lbl0 = label_font.render("Robot 0 (Blue):", True, BLUE)
        surface.blit(lbl0, (160, 135))
        lbl1 = label_font.render("Robot 1 (Red):", True, RED)
        surface.blit(lbl1, (160, 225))

        pygame.draw.line(surface, GRAY, (140, 310), (580, 310), width=1)

        self.time_input.draw(surface)
        self.steps_input.draw(surface)

        pygame.draw.line(surface, GRAY, (140, 455), (580, 455), width=1)

        self.num_games_input.draw(surface)
        self.log_rate_input.draw(surface)
        self.csv_checkbox.draw(surface)

        self.back_btn.draw(surface)
        self.start_btn.draw(surface)

        # Draw expanded dropdown last (on top)
        if self.dropdown1.is_expanded():
            self.dropdown0.draw(surface)
            self.dropdown1.draw(surface)
        elif self.dropdown0.is_expanded():
            self.dropdown1.draw(surface)
            self.dropdown0.draw(surface)
        else:
            self.dropdown0.draw(surface)
            self.dropdown1.draw(surface)

    def get_config(self):
        return BatchConfig(
            agent0=self.dropdown0.selected,
            agent1=self.dropdown1.selected,
            time_limit=self.time_input.get_value(),
            count_steps=int(self.steps_input.get_value()),
            num_games=int(self.num_games_input.get_value()),
            log_sampling_rate=int(self.log_rate_input.get_value()),
            csv=self.csv_checkbox.is_checked(),
        )
