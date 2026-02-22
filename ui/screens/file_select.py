"""File selection screen for replay log browsing."""

import os

import pygame

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, GRAY, DARK_GRAY, WHITE, RED, GREEN,
    get_font,
)
from ui.widgets import Button


class FileSelectScreen(Screen):
    """Screen for browsing and selecting log files to replay."""

    MAX_VISIBLE = 14
    LIST_X = 60
    LIST_Y = 100
    LIST_W = 600
    ROW_H = 34

    def __init__(self):
        self.files = []
        self.selected_index = -1
        self.scroll_offset = 0
        self.error_msg = ""

        self.load_btn = Button(
            480, 600, 120, 45, "Load", color=GREEN,
            hover_color=(50, 160, 50), text_color=WHITE, font_size=20,
        )
        self.back_btn = Button(
            60, 600, 120, 45, "Back", color=RED,
            hover_color=(190, 50, 50), text_color=WHITE, font_size=20,
        )
        self._scan_directory()

    def _scan_directory(self):
        self.files = []
        self.selected_index = -1
        self.scroll_offset = 0

        search_dirs = ["game_logs"]
        if os.path.isdir("batch_results"):
            for entry in os.listdir("batch_results"):
                sub_logs = os.path.join("batch_results", entry, "game_logs")
                if os.path.isdir(sub_logs):
                    search_dirs.append(sub_logs)
            direct = os.path.join("batch_results", "game_logs")
            if os.path.isdir(direct):
                search_dirs.append(direct)

        for dir_path in search_dirs:
            if not os.path.isdir(dir_path):
                continue
            for fname in os.listdir(dir_path):
                if fname.endswith(".txt"):
                    full_path = os.path.join(dir_path, fname)
                    try:
                        mtime = os.path.getmtime(full_path)
                        from datetime import datetime as dt
                        mod_str = dt.fromtimestamp(mtime).strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    except OSError:
                        mod_str = ""
                        mtime = 0
                    self.files.append((fname, full_path, mod_str, mtime))

        self.files.sort(key=lambda x: x[3], reverse=True)

    def show_error(self, msg):
        self.error_msg = msg

    def handle_event(self, event):
        self.error_msg = ""

        if self.back_btn.handle_event(event):
            return ScreenId.OPENING

        if self.selected_index >= 0 and self.load_btn.handle_event(event):
            filepath = self.files[self.selected_index][1]
            return (ScreenId.REPLAY, {"filepath": filepath})

        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset = max(0, min(
                self.scroll_offset - event.y,
                max(0, len(self.files) - self.MAX_VISIBLE),
            ))

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.LIST_X <= mx <= self.LIST_X + self.LIST_W:
                rel_y = my - self.LIST_Y
                if 0 <= rel_y < self.MAX_VISIBLE * self.ROW_H:
                    row = rel_y // self.ROW_H + self.scroll_offset
                    if 0 <= row < len(self.files):
                        self.selected_index = row

        return None

    def draw(self, surface):
        title_font = get_font(28, bold=True)
        title = title_font.render("Select Replay Log", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=30))

        sub_font = get_font(15)
        count_text = f"{len(self.files)} log file(s) found"
        sub = sub_font.render(count_text, True, DARK_GRAY)
        surface.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, y=70))

        font = get_font(15)
        date_font = get_font(13)

        if not self.files:
            msg_font = get_font(18)
            msg = msg_font.render(
                "No log files found in game_logs/", True, DARK_GRAY,
            )
            surface.blit(
                msg, msg.get_rect(centerx=WINDOW_WIDTH // 2, y=250),
            )
        else:
            visible_end = min(
                self.scroll_offset + self.MAX_VISIBLE, len(self.files),
            )
            for i in range(self.scroll_offset, visible_end):
                row_idx = i - self.scroll_offset
                y = self.LIST_Y + row_idx * self.ROW_H
                row_rect = pygame.Rect(
                    self.LIST_X, y, self.LIST_W, self.ROW_H - 2,
                )

                if i == self.selected_index:
                    pygame.draw.rect(
                        surface, (180, 210, 255), row_rect, border_radius=4,
                    )
                else:
                    pygame.draw.rect(
                        surface, WHITE, row_rect, border_radius=4,
                    )
                pygame.draw.rect(
                    surface, GRAY, row_rect, width=1, border_radius=4,
                )

                fname = self.files[i][0]
                if len(fname) > 55:
                    fname = fname[:52] + "..."
                text = font.render(fname, True, BLACK)
                surface.blit(text, (self.LIST_X + 8, y + 4))

                date_text = date_font.render(self.files[i][2], True, DARK_GRAY)
                surface.blit(
                    date_text,
                    (self.LIST_X + self.LIST_W - 120, y + 7),
                )

            if self.scroll_offset > 0:
                indicator = font.render("^ more above ^", True, DARK_GRAY)
                surface.blit(indicator, indicator.get_rect(
                    centerx=WINDOW_WIDTH // 2, y=self.LIST_Y - 18,
                ))
            if visible_end < len(self.files):
                indicator = font.render("v more below v", True, DARK_GRAY)
                surface.blit(indicator, indicator.get_rect(
                    centerx=WINDOW_WIDTH // 2,
                    y=self.LIST_Y + self.MAX_VISIBLE * self.ROW_H + 2,
                ))

        self.back_btn.draw(surface)
        if self.selected_index >= 0:
            self.load_btn.draw(surface)

        if self.error_msg:
            err_font = get_font(15)
            err = err_font.render(f"Error: {self.error_msg}", True, RED)
            surface.blit(err, err.get_rect(centerx=WINDOW_WIDTH // 2, y=660))
