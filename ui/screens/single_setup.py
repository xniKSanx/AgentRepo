"""Single game setup screen."""

import random

import pygame

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, GRAY, DARK_GRAY, BLUE, RED, GREEN, ORANGE,
    HOVER_GRAY, WHITE,
    get_font,
)
from ui.widgets import Button, Dropdown, NumberInput, Checkbox
from agent_registry import VALID_AGENT_NAMES
from config import GameConfig


class SingleGameSetupScreen(Screen):
    def __init__(self):
        # Map mode toggle
        self.map_mode = "random"
        self.custom_map_data = None
        self.random_map_btn = Button(
            160, 110, 190, 38, "Random Map", color=GREEN,
            hover_color=(50, 160, 50), text_color=WHITE, font_size=18,
        )
        self.custom_map_btn = Button(
            370, 110, 190, 38, "Build Custom Map",
            hover_color=HOVER_GRAY, font_size=18,
        )

        self.dropdown0 = Dropdown(
            160, 210, 400, 40, VALID_AGENT_NAMES, default_index=0,
        )
        self.dropdown1 = Dropdown(
            160, 300, 400, 40, VALID_AGENT_NAMES, default_index=1,
        )

        self.time_input = NumberInput(
            160, 390, "Time Limit (s):", 1.0, 0.1, 30.0, step=0.5,
            is_float=True,
        )
        self.steps_input = NumberInput(
            160, 510, "Max Rounds:", 200, 10, 99999, step=10,
        )
        self.seed_input = NumberInput(
            160, 450, "Seed (0=random):", 0, 0, 9999, step=1,
        )

        self.log_checkbox = Checkbox(160, 580, "Enable Game Logging")

        self.back_btn = Button(160, 680, 140, 45, "Back", font_size=20)
        self.start_btn = Button(
            420, 680, 140, 45, "Start", color=GREEN,
            hover_color=(50, 160, 50), text_color=WHITE, font_size=22,
        )

    def _update_toggle_colors(self):
        if self.map_mode == "random":
            self.random_map_btn.color = GREEN
            self.random_map_btn.text_color = WHITE
            self.custom_map_btn.color = GRAY
            self.custom_map_btn.text_color = BLACK
        else:
            self.random_map_btn.color = GRAY
            self.random_map_btn.text_color = BLACK
            self.custom_map_btn.color = GREEN
            self.custom_map_btn.text_color = WHITE

    def handle_event(self, event):
        # Handle expanded dropdowns first
        if self.dropdown0.is_expanded():
            self.dropdown0.handle_event(event)
            return None
        if self.dropdown1.is_expanded():
            self.dropdown1.handle_event(event)
            return None

        # Map mode toggle
        if self.random_map_btn.handle_event(event):
            self.map_mode = "random"
            self._update_toggle_colors()
            return None
        if self.custom_map_btn.handle_event(event):
            self.map_mode = "custom"
            self._update_toggle_colors()
            return None

        self.dropdown0.handle_event(event)
        self.dropdown1.handle_event(event)

        self.time_input.handle_event(event)
        if self.map_mode == "random":
            self.seed_input.handle_event(event)
        self.steps_input.handle_event(event)
        self.log_checkbox.handle_event(event)

        if self.back_btn.handle_event(event):
            return ScreenId.OPENING
        if self.start_btn.handle_event(event):
            if self.map_mode == "custom" and self.custom_map_data is None:
                return ScreenId.MAP_BUILDER
            return (ScreenId.GAME, {"config": self.get_config()})
        return None

    def draw(self, surface):
        title_font = get_font(28, bold=True)
        title = title_font.render("Single Game Setup", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=30))

        # Map mode section
        map_label_font = get_font(18, bold=True)
        map_label = map_label_font.render("Map Mode:", True, DARK_GRAY)
        surface.blit(map_label, (160, 80))

        self._update_toggle_colors()
        self.random_map_btn.draw(surface)
        self.custom_map_btn.draw(surface)

        if self.map_mode == "custom":
            status_font = get_font(16)
            if self.custom_map_data is not None:
                status = status_font.render("Map Ready", True, GREEN)
            else:
                status = status_font.render(
                    "No map built yet - click Start to build", True, ORANGE,
                )
            surface.blit(status, (160, 152))

        pygame.draw.line(surface, GRAY, (140, 170), (580, 170), width=1)

        label_font = get_font(22, bold=True)
        lbl0 = label_font.render("Robot 0 (Blue):", True, BLUE)
        surface.blit(lbl0, (160, 180))
        lbl1 = label_font.render("Robot 1 (Red):", True, RED)
        surface.blit(lbl1, (160, 270))

        pygame.draw.line(surface, GRAY, (140, 360), (580, 360), width=1)

        self.time_input.draw(surface)
        if self.map_mode == "random":
            self.seed_input.draw(surface)
        self.steps_input.draw(surface)
        self.log_checkbox.draw(surface)

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
        seed_val = int(self.seed_input.get_value())
        return GameConfig(
            agent0=self.dropdown0.selected,
            agent1=self.dropdown1.selected,
            time_limit=self.time_input.get_value(),
            seed=seed_val if seed_val != 0 else random.randint(0, 255),
            count_steps=int(self.steps_input.get_value()),
            logging_enabled=self.log_checkbox.is_checked(),
            custom_map_data=(
                self.custom_map_data
                if self.map_mode == "custom" else None
            ),
        )
