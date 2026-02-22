"""Opening / main menu screen."""

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, DARK_GRAY, GREEN, BLUE, HOVER_GRAY,
    get_font,
)
from ui.widgets import Button


class OpeningScreen(Screen):
    def __init__(self):
        self.single_btn = Button(
            210, 340, 300, 55, "Start Single Game", color=GREEN,
            hover_color=(50, 160, 50), text_color=(255, 255, 255),
            font_size=22,
        )
        self.batch_btn = Button(
            210, 420, 300, 55, "Start Batch Check", color=BLUE,
            hover_color=(50, 110, 210), text_color=(255, 255, 255),
            font_size=22,
        )
        self.replay_btn = Button(
            210, 500, 300, 55, "Replay Log",
            hover_color=HOVER_GRAY, font_size=22,
        )

    def handle_event(self, event):
        if self.single_btn.handle_event(event):
            return ScreenId.SINGLE_SETUP
        if self.batch_btn.handle_event(event):
            return ScreenId.BATCH_SETUP
        if self.replay_btn.handle_event(event):
            return ScreenId.FILE_SELECT
        return None

    def draw(self, surface):
        title_font = get_font(36, bold=True)
        title = title_font.render("AI Warehouse Game Runner", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=160))

        sub_font = get_font(18)
        subtitle = sub_font.render("Select a mode to begin", True, DARK_GRAY)
        surface.blit(
            subtitle, subtitle.get_rect(centerx=WINDOW_WIDTH // 2, y=230)
        )

        self.single_btn.draw(surface)
        self.batch_btn.draw(surface)
        self.replay_btn.draw(surface)
