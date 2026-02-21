import pygame
import threading
import time
import random
import os
from enum import Enum
from datetime import datetime

from WarehouseEnv import WarehouseEnv, manhattan_distance, board_size
from agent_registry import create_agent, VALID_AGENT_NAMES
from batch_runner import run_batch
from simulation import determine_winner

# =============================================================================
#                               Constants
# =============================================================================

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 850


# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
LIGHT_GRAY = (230, 230, 230)
DARK_GRAY = (100, 100, 100)
BLUE = (70, 130, 230)
RED = (220, 70, 70)
GREEN = (70, 180, 70)
YELLOW = (220, 200, 60)
ORANGE = (230, 150, 50)
HOVER_GRAY = (180, 180, 180)
DISABLED_GRAY = (170, 170, 170)
PANEL_BG = (245, 245, 245)


def get_font(size, bold=False):
    return pygame.font.SysFont("arial", size, bold=bold)


# =============================================================================
#                              UI Primitives
# =============================================================================


class Button:
    def __init__(self, x, y, width, height, text, color=GRAY,
                 hover_color=HOVER_GRAY, text_color=BLACK, font_size=20):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.font_size = font_size
        self.hovered = False
        self.enabled = True

    def draw(self, surface):
        if not self.enabled:
            bg = DISABLED_GRAY
            fg = DARK_GRAY
        elif self.hovered:
            bg = self.hover_color
            fg = self.text_color
        else:
            bg = self.color
            fg = self.text_color

        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, BLACK, self.rect, width=2, border_radius=6)

        font = get_font(self.font_size)
        text_surf = font.render(self.text, True, fg)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.enabled and self.rect.collidepoint(event.pos):
                return True
        return False


class Dropdown:
    def __init__(self, x, y, width, height, options, default_index=0):
        self.rect = pygame.Rect(x, y, width, height)
        self.options = options
        self.selected_index = default_index
        self.expanded = False
        self.hovered_option = -1

    @property
    def selected(self):
        return self.options[self.selected_index]

    def draw(self, surface):
        # Main box
        bg = WHITE if not self.expanded else LIGHT_GRAY
        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        pygame.draw.rect(surface, BLACK, self.rect, width=2, border_radius=4)

        font = get_font(20)
        text_surf = font.render(self.selected, True, BLACK)
        surface.blit(text_surf, (self.rect.x + 10, self.rect.y + 8))

        # Arrow
        arrow_x = self.rect.right - 25
        arrow_y = self.rect.centery
        if self.expanded:
            pts = [(arrow_x - 6, arrow_y + 3), (arrow_x + 6, arrow_y + 3), (arrow_x, arrow_y - 5)]
        else:
            pts = [(arrow_x - 6, arrow_y - 3), (arrow_x + 6, arrow_y - 3), (arrow_x, arrow_y + 5)]
        pygame.draw.polygon(surface, BLACK, pts)

        # Expanded options
        if self.expanded:
            for i, option in enumerate(self.options):
                opt_rect = pygame.Rect(self.rect.x, self.rect.bottom + i * self.rect.height,
                                       self.rect.width, self.rect.height)
                if i == self.hovered_option:
                    pygame.draw.rect(surface, BLUE, opt_rect)
                    text_color = WHITE
                else:
                    pygame.draw.rect(surface, WHITE, opt_rect)
                    text_color = BLACK
                pygame.draw.rect(surface, BLACK, opt_rect, width=1)
                text_surf = font.render(option, True, text_color)
                surface.blit(text_surf, (opt_rect.x + 10, opt_rect.y + 8))

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION and self.expanded:
            for i in range(len(self.options)):
                opt_rect = pygame.Rect(self.rect.x, self.rect.bottom + i * self.rect.height,
                                       self.rect.width, self.rect.height)
                if opt_rect.collidepoint(event.pos):
                    self.hovered_option = i
                    break
            else:
                self.hovered_option = -1

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.expanded:
                for i in range(len(self.options)):
                    opt_rect = pygame.Rect(self.rect.x, self.rect.bottom + i * self.rect.height,
                                           self.rect.width, self.rect.height)
                    if opt_rect.collidepoint(event.pos):
                        self.selected_index = i
                        self.expanded = False
                        self.hovered_option = -1
                        return True
                # Clicked outside options
                self.expanded = False
                self.hovered_option = -1
                return False
            else:
                if self.rect.collidepoint(event.pos):
                    self.expanded = True
                    return False
        return False

    def is_expanded(self):
        return self.expanded


class NumberInput:
    def __init__(self, x, y, label, value, min_val, max_val, step=1, is_float=False):
        self.x = x
        self.y = y
        self.label = label
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.is_float = is_float
        self.minus_rect = pygame.Rect(x + 200, y, 36, 36)
        self.value_rect = pygame.Rect(x + 240, y, 100, 36)
        self.plus_rect = pygame.Rect(x + 344, y, 36, 36)

    def draw(self, surface):
        font = get_font(22)
        label_surf = font.render(self.label, True, BLACK)
        surface.blit(label_surf, (self.x, self.y + 6))

        # Minus button
        pygame.draw.rect(surface, GRAY, self.minus_rect, border_radius=4)
        pygame.draw.rect(surface, BLACK, self.minus_rect, width=2, border_radius=4)
        minus_text = get_font(24, bold=True).render("-", True, BLACK)
        surface.blit(minus_text, minus_text.get_rect(center=self.minus_rect.center))

        # Value display
        pygame.draw.rect(surface, WHITE, self.value_rect, border_radius=4)
        pygame.draw.rect(surface, BLACK, self.value_rect, width=2, border_radius=4)
        if self.is_float:
            val_str = f"{self.value:.1f}"
        else:
            val_str = str(int(self.value))
        val_surf = font.render(val_str, True, BLACK)
        surface.blit(val_surf, val_surf.get_rect(center=self.value_rect.center))

        # Plus button
        pygame.draw.rect(surface, GRAY, self.plus_rect, border_radius=4)
        pygame.draw.rect(surface, BLACK, self.plus_rect, width=2, border_radius=4)
        plus_text = get_font(24, bold=True).render("+", True, BLACK)
        surface.blit(plus_text, plus_text.get_rect(center=self.plus_rect.center))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.minus_rect.collidepoint(event.pos):
                self.value = max(self.min_val, self.value - self.step)
                if not self.is_float:
                    self.value = int(self.value)
                return True
            if self.plus_rect.collidepoint(event.pos):
                self.value = min(self.max_val, self.value + self.step)
                if not self.is_float:
                    self.value = int(self.value)
                return True
        return False

    def get_value(self):
        return self.value


class Checkbox:
    def __init__(self, x, y, label, checked=False):
        self.x = x
        self.y = y
        self.label = label
        self.checked = checked
        self.box_size = 24
        self.box_rect = pygame.Rect(x, y + 4, self.box_size, self.box_size)

    def draw(self, surface):
        pygame.draw.rect(surface, WHITE, self.box_rect, border_radius=4)
        pygame.draw.rect(surface, BLACK, self.box_rect, width=2, border_radius=4)

        if self.checked:
            bx, by = self.box_rect.x, self.box_rect.y
            bs = self.box_size
            pygame.draw.line(surface, GREEN, (bx + 4, by + bs // 2),
                             (bx + bs // 3, by + bs - 6), width=3)
            pygame.draw.line(surface, GREEN, (bx + bs // 3, by + bs - 6),
                             (bx + bs - 4, by + 4), width=3)

        font = get_font(22)
        label_surf = font.render(self.label, True, BLACK)
        surface.blit(label_surf, (self.x + self.box_size + 10, self.y + 4))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.box_rect.collidepoint(event.pos):
                self.checked = not self.checked
                return True
        return False

    def is_checked(self):
        return self.checked


# =============================================================================
#                           Board Rendering
# =============================================================================


def load_icons():
    icon_files = {
        "blue_robot": "icons/robot_b.jpeg",
        "red_robot": "icons/robot_r.jpeg",
        "blue_robot_package": "icons/robot_b_package.jpeg",
        "red_robot_package": "icons/robot_r_package.jpeg",
        "charge_station": "icons/charge_station.jpeg",
        "package_1": "icons/package_1.jpeg",
        "package_2": "icons/package_2.jpeg",
        "dest_1": "icons/dest_1.jpeg",
        "dest_2": "icons/dest_2.jpeg",
        "dest_red": "icons/dest_red.jpeg",
        "dest_blue": "icons/dest_blue.jpeg",
    }
    icons = {}
    for key, path in icon_files.items():
        try:
            icons[key] = pygame.image.load(path).convert()
        except (FileNotFoundError, pygame.error):
            icons[key] = None
    return icons


def _draw_fallback_icon(surface, x, y, w, h, color, label):
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, color, rect, border_radius=6)
    pygame.draw.rect(surface, BLACK, rect, width=1, border_radius=6)
    font = get_font(16, bold=True)
    text = font.render(label, True, BLACK)
    surface.blit(text, text.get_rect(center=rect.center))


def render_robot_data(surface, env, icons):
    font = get_font(16)

    for robot_index in range(len(env.robots)):
        robot = env.robots[robot_index]
        pos_txt = f"position: {robot.position}"
        bat_txt = f"battery: {robot.battery}"
        cred_txt = f"credit: {robot.credit}"

        if robot_index == 0:
            icon_key = "blue_robot"
            icon_x, icon_y = 95, 80
            text_x = 185
            fallback_color = BLUE
            fallback_label = "R0"
        else:
            icon_key = "red_robot"
            icon_x, icon_y = 355, 80
            text_x = 445
            fallback_color = RED
            fallback_label = "R1"

        icon = icons.get(icon_key)
        if icon:
            surface.blit(pygame.transform.scale(icon, (95, 95)), (icon_x, icon_y))
        else:
            _draw_fallback_icon(surface, icon_x, icon_y, 80, 80, fallback_color, fallback_label)

        surface.blit(font.render(pos_txt, True, BLACK), (text_x, 95))
        surface.blit(font.render(bat_txt, True, BLACK), (text_x, 115))
        surface.blit(font.render(cred_txt, True, BLACK), (text_x, 135))

        if robot.package is not None:
            pkg_txt = f"package: {robot.package.position} -> {robot.package.destination}"
            surface.blit(font.render(pkg_txt, True, BLACK), (text_x, 155))


def render_board(surface, env, icons):
    # Grid lines
    for x in range(6):
        pygame.draw.line(surface, BLACK, (110, x * 100 + 190), (610, x * 100 + 190), width=3)
        pygame.draw.line(surface, BLACK, (x * 100 + 110, 190), (x * 100 + 110, 690), width=3)

    # Board entities
    for y in range(board_size):
        for x in range(board_size):
            p = (x, y)
            robot = env.get_robot_in(p)
            package = env.get_package_in(p)
            charge_station = env.get_charge_station_in(p)
            package_destination = [pkg for pkg in env.packages if
                                   pkg.destination == p and pkg.on_board]
            robot_package_destination = [i for i, r in enumerate(env.robots) if
                                         r.package is not None and r.package.destination == p]

            cell_x = x * 100 + 112
            cell_y = y * 100 + 192
            icon_x = x * 100 + 120
            icon_y = y * 100 + 200

            if robot:
                ridx = env.robots.index(robot)
                if ridx == 0:
                    if robot.package is not None:
                        icon = icons.get("blue_robot_package")
                    else:
                        icon = icons.get("blue_robot")
                    if icon:
                        surface.blit(pygame.transform.scale(icon, (95, 95)), (cell_x, cell_y))
                    else:
                        label = "R0+" if robot.package else "R0"
                        _draw_fallback_icon(surface, cell_x, cell_y, 90, 90, BLUE, label)
                else:
                    if robot.package is not None:
                        icon = icons.get("red_robot_package")
                    else:
                        icon = icons.get("red_robot")
                    if icon:
                        surface.blit(pygame.transform.scale(icon, (95, 95)), (cell_x, cell_y))
                    else:
                        label = "R1+" if robot.package else "R1"
                        _draw_fallback_icon(surface, cell_x, cell_y, 90, 90, RED, label)

            elif charge_station:
                icon = icons.get("charge_station")
                if icon:
                    surface.blit(pygame.transform.scale(icon, (80, 80)), (icon_x, icon_y))
                else:
                    _draw_fallback_icon(surface, icon_x, icon_y, 80, 80, GREEN, "CS")

            elif package and package.on_board:
                pidx = env.packages[0:2].index(package) if package in env.packages[0:2] else 0
                icon_key = "package_1" if pidx == 0 else "package_2"
                icon = icons.get(icon_key)
                if icon:
                    surface.blit(pygame.transform.scale(icon, (80, 80)), (icon_x, icon_y))
                else:
                    _draw_fallback_icon(surface, icon_x, icon_y, 80, 80, YELLOW, f"P{pidx}")

            elif len(package_destination) > 0:
                pkg = package_destination[0]
                pidx = env.packages.index(pkg) if pkg in env.packages else 0
                icon_key = "dest_1" if pidx == 0 else "dest_2"
                icon = icons.get(icon_key)
                if icon:
                    surface.blit(pygame.transform.scale(icon, (80, 80)), (icon_x, icon_y))
                else:
                    _draw_fallback_icon(surface, icon_x, icon_y, 80, 80, ORANGE, f"D{pidx}")

            elif len(robot_package_destination) > 0:
                ridx = robot_package_destination[0]
                icon_key = "dest_blue" if ridx == 0 else "dest_red"
                icon = icons.get(icon_key)
                if icon:
                    surface.blit(pygame.transform.scale(icon, (80, 80)), (icon_x, icon_y))
                else:
                    color = BLUE if ridx == 0 else RED
                    _draw_fallback_icon(surface, icon_x, icon_y, 80, 80, color, f"X{ridx}")


# =============================================================================
#                           File Select Screen
# =============================================================================


class FileSelectScreen:
    """Screen for browsing and selecting log files to replay."""

    MAX_VISIBLE = 14
    LIST_X = 60
    LIST_Y = 100
    LIST_W = 600
    ROW_H = 34

    def __init__(self):
        self.files = []          # list of (filename, full_path, mod_time_str)
        self.selected_index = -1
        self.scroll_offset = 0
        self.error_msg = ""

        self.load_btn = Button(480, 600, 120, 45, "Load", color=GREEN,
                               hover_color=(50, 160, 50), text_color=WHITE, font_size=20)
        self.back_btn = Button(60, 600, 120, 45, "Back", color=RED,
                               hover_color=(190, 50, 50), text_color=WHITE, font_size=20)
        self._scan_directory()

    def _scan_directory(self):
        self.files = []
        self.selected_index = -1
        self.scroll_offset = 0

        search_dirs = ["game_logs"]
        # Also check for batch result directories
        if os.path.isdir("batch_results"):
            for entry in os.listdir("batch_results"):
                sub_logs = os.path.join("batch_results", entry, "game_logs")
                if os.path.isdir(sub_logs):
                    search_dirs.append(sub_logs)
            # batch_results might have game_logs directly
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
                        mod_str = dt.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    except OSError:
                        mod_str = ""
                        mtime = 0
                    self.files.append((fname, full_path, mod_str, mtime))

        # Sort newest first
        self.files.sort(key=lambda x: x[3], reverse=True)

    def show_error(self, msg):
        self.error_msg = msg

    def handle_event(self, event):
        self.error_msg = ""

        if self.back_btn.handle_event(event):
            return "back"

        if self.selected_index >= 0 and self.load_btn.handle_event(event):
            filepath = self.files[self.selected_index][1]
            return ("load", filepath)

        # Mouse wheel scrolling
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset = max(0, min(
                self.scroll_offset - event.y,
                max(0, len(self.files) - self.MAX_VISIBLE)
            ))

        # Click on file list
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
        # Title
        title_font = get_font(28, bold=True)
        title = title_font.render("Select Replay Log", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=30))

        # Subtitle
        sub_font = get_font(15)
        count_text = f"{len(self.files)} log file(s) found"
        sub = sub_font.render(count_text, True, DARK_GRAY)
        surface.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, y=70))

        # File list
        font = get_font(15)
        date_font = get_font(13)

        if not self.files:
            msg_font = get_font(18)
            msg = msg_font.render("No log files found in game_logs/", True, DARK_GRAY)
            surface.blit(msg, msg.get_rect(centerx=WINDOW_WIDTH // 2, y=250))
        else:
            visible_end = min(self.scroll_offset + self.MAX_VISIBLE, len(self.files))
            for i in range(self.scroll_offset, visible_end):
                row_idx = i - self.scroll_offset
                y = self.LIST_Y + row_idx * self.ROW_H
                row_rect = pygame.Rect(self.LIST_X, y, self.LIST_W, self.ROW_H - 2)

                # Background
                if i == self.selected_index:
                    pygame.draw.rect(surface, (180, 210, 255), row_rect, border_radius=4)
                else:
                    pygame.draw.rect(surface, WHITE, row_rect, border_radius=4)
                pygame.draw.rect(surface, GRAY, row_rect, width=1, border_radius=4)

                # Filename
                fname = self.files[i][0]
                if len(fname) > 55:
                    fname = fname[:52] + "..."
                text = font.render(fname, True, BLACK)
                surface.blit(text, (self.LIST_X + 8, y + 4))

                # Date
                date_text = date_font.render(self.files[i][2], True, DARK_GRAY)
                surface.blit(date_text, (self.LIST_X + self.LIST_W - 120, y + 7))

            # Scroll indicators
            if self.scroll_offset > 0:
                indicator = font.render("^ more above ^", True, DARK_GRAY)
                surface.blit(indicator, indicator.get_rect(
                    centerx=WINDOW_WIDTH // 2, y=self.LIST_Y - 18))
            if visible_end < len(self.files):
                indicator = font.render("v more below v", True, DARK_GRAY)
                surface.blit(indicator, indicator.get_rect(
                    centerx=WINDOW_WIDTH // 2,
                    y=self.LIST_Y + self.MAX_VISIBLE * self.ROW_H + 2))

        # Buttons
        self.back_btn.draw(surface)
        if self.selected_index >= 0:
            self.load_btn.draw(surface)

        # Error message
        if self.error_msg:
            err_font = get_font(15)
            err = err_font.render(f"Error: {self.error_msg}", True, RED)
            surface.blit(err, err.get_rect(centerx=WINDOW_WIDTH // 2, y=660))



# =============================================================================
#                              Screens
# =============================================================================


class OpeningScreen:
    def __init__(self):
        self.single_btn = Button(210, 340, 300, 55, "Start Single Game", color=GREEN,
                                 hover_color=(50, 160, 50), text_color=WHITE, font_size=22)
        self.batch_btn = Button(210, 420, 300, 55, "Start Batch Check", color=BLUE,
                                hover_color=(50, 110, 210), text_color=WHITE, font_size=22)
        self.replay_btn = Button(210, 500, 300, 55, "Replay Log",
                                 hover_color=HOVER_GRAY, font_size=22)

    def handle_event(self, event):
        if self.single_btn.handle_event(event):
            return "single"
        if self.batch_btn.handle_event(event):
            return "batch"
        if self.replay_btn.handle_event(event):
            return "replay"
        return None

    def draw(self, surface):
        title_font = get_font(36, bold=True)
        title = title_font.render("AI Warehouse Game Runner", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=160))

        sub_font = get_font(18)
        subtitle = sub_font.render("Select a mode to begin", True, DARK_GRAY)
        surface.blit(subtitle, subtitle.get_rect(centerx=WINDOW_WIDTH // 2, y=230))

        self.single_btn.draw(surface)
        self.batch_btn.draw(surface)
        self.replay_btn.draw(surface)


class SingleGameSetupScreen:
    def __init__(self):
        # Map mode toggle
        self.map_mode = "random"  # "random" or "custom"
        self.custom_map_data = None
        self.random_map_btn = Button(160, 110, 190, 38, "Random Map", color=GREEN,
                                     hover_color=(50, 160, 50), text_color=WHITE, font_size=18)
        self.custom_map_btn = Button(370, 110, 190, 38, "Build Custom Map",
                                     hover_color=HOVER_GRAY, font_size=18)

        self.dropdown0 = Dropdown(160, 210, 400, 40, VALID_AGENT_NAMES, default_index=0)
        self.dropdown1 = Dropdown(160, 300, 400, 40, VALID_AGENT_NAMES, default_index=1)

        self.time_input = NumberInput(160, 390, "Time Limit (s):", 1.0, 0.1, 30.0, step=0.5, is_float=True)
        self.seed_input = NumberInput(160, 450, "Seed (0=random):", 0, 0, 9999, step=1)
        self.steps_input = NumberInput(160, 510, "Max Rounds:", 4761, 10, 99999, step=100)

        self.log_checkbox = Checkbox(160, 580, "Enable Game Logging")

        self.back_btn = Button(160, 680, 140, 45, "Back", font_size=20)
        self.start_btn = Button(420, 680, 140, 45, "Start", color=GREEN,
                                hover_color=(50, 160, 50), text_color=WHITE, font_size=22)

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
        # Handle expanded dropdowns first to capture clicks
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
            return "back"
        if self.start_btn.handle_event(event):
            if self.map_mode == "custom" and self.custom_map_data is None:
                return "build_map"
            return "start"
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

        # Custom map status
        if self.map_mode == "custom":
            status_font = get_font(16)
            if self.custom_map_data is not None:
                status = status_font.render("Map Ready", True, GREEN)
            else:
                status = status_font.render("No map built yet - click Start to build", True, ORANGE)
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

        # Draw expanded dropdown last (on top of everything)
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
        config = {
            "agent0": self.dropdown0.selected,
            "agent1": self.dropdown1.selected,
            "time_limit": self.time_input.get_value(),
            "seed": seed_val if seed_val != 0 else random.randint(0, 255),
            "count_steps": int(self.steps_input.get_value()),
            "logging_enabled": self.log_checkbox.is_checked(),
        }
        if self.map_mode == "custom" and self.custom_map_data is not None:
            config["custom_map_data"] = self.custom_map_data
        return config


# =============================================================================
#                          Map Builder Screen
# =============================================================================

# Tool types for the palette
MAP_TOOLS = [
    ("robot_0", "R0 Blue", BLUE, "R0"),
    ("robot_1", "R1 Red", RED, "R1"),
    ("package_1", "Pkg1", YELLOW, "P1"),
    ("package_1_dest", "Dest1", ORANGE, "D1"),
    ("package_2", "Pkg2", YELLOW, "P2"),
    ("package_2_dest", "Dest2", ORANGE, "D2"),
    ("charge_1", "Chg1", GREEN, "C1"),
    ("charge_2", "Chg2", GREEN, "C2"),
    ("eraser", "Erase", LIGHT_GRAY, "X"),
]

# Map from tool id to icon key used by load_icons()
TOOL_ICON_MAP = {
    "robot_0": "blue_robot",
    "robot_1": "red_robot",
    "package_1": "package_1",
    "package_1_dest": "dest_1",
    "package_2": "package_2",
    "package_2_dest": "dest_2",
    "charge_1": "charge_station",
    "charge_2": "charge_station",
}


class MapBuilderScreen:
    # Grid geometry (matches game board)
    GRID_X = 110
    GRID_Y = 170
    CELL_SIZE = 100

    def __init__(self):
        self.icons = load_icons()
        self.selected_tool = None
        self.placements = {}  # (x,y) -> tool_id string
        self.hovered_cell = None
        self.error_msg = ""

        # Build palette buttons
        self.palette_buttons = {}
        bx = 10
        for tool_id, label, color, _ in MAP_TOOLS:
            btn_w = max(68, get_font(13).size(label)[0] + 14)
            btn = Button(bx, 75, btn_w, 30, label, color=GRAY,
                         hover_color=HOVER_GRAY, text_color=BLACK, font_size=13)
            self.palette_buttons[tool_id] = btn
            bx += btn_w + 4

        # Action buttons
        self.clear_btn = Button(30, 780, 120, 42, "Clear All", color=RED,
                                hover_color=(190, 50, 50), text_color=WHITE, font_size=18)
        self.back_btn = Button(260, 780, 120, 42, "Back", font_size=18)
        self.save_btn = Button(490, 780, 120, 42, "Save", color=GREEN,
                               hover_color=(50, 160, 50), text_color=WHITE, font_size=18)

    def _cell_from_pos(self, pos):
        """Convert pixel position to grid (x,y) or None if outside grid."""
        px, py = pos
        gx = (px - self.GRID_X) // self.CELL_SIZE
        gy = (py - self.GRID_Y) // self.CELL_SIZE
        if 0 <= gx < board_size and 0 <= gy < board_size:
            # Verify within grid bounds (not just in surrounding area)
            if (self.GRID_X <= px < self.GRID_X + board_size * self.CELL_SIZE and
                    self.GRID_Y <= py < self.GRID_Y + board_size * self.CELL_SIZE):
                return (gx, gy)
        return None

    def _find_placement(self, tool_id):
        """Find the cell where a tool_id is currently placed, or None."""
        for pos, tid in self.placements.items():
            if tid == tool_id:
                return pos
        return None

    def _validate(self):
        """Check if all required items are placed. Returns error message or empty string."""
        required = ["robot_0", "robot_1", "package_1", "package_1_dest",
                     "package_2", "package_2_dest", "charge_1", "charge_2"]
        placed = set(self.placements.values())
        missing = [tid for tid in required if tid not in placed]
        if missing:
            labels = {tid: label for tid, label, _, _ in MAP_TOOLS}
            names = ", ".join(labels[m] for m in missing)
            return f"Missing: {names}"

        # Check package != its own destination
        for pkg_id, dest_id in [("package_1", "package_1_dest"), ("package_2", "package_2_dest")]:
            pkg_pos = self._find_placement(pkg_id)
            dest_pos = self._find_placement(dest_id)
            if pkg_pos and dest_pos and pkg_pos == dest_pos:
                return f"Package and its destination cannot be on the same cell"

        return ""

    def _build_map_data(self):
        """Convert placements to the JSON-compatible map data dict."""
        data = {"board_size": board_size, "robots": [], "packages": [], "charge_stations": []}

        # Robots
        for rid in ["robot_0", "robot_1"]:
            pos = self._find_placement(rid)
            data["robots"].append({
                "position": list(pos),
                "battery": 20,
                "credit": 0
            })

        # Packages
        for pkg_id, dest_id in [("package_1", "package_1_dest"), ("package_2", "package_2_dest")]:
            pkg_pos = self._find_placement(pkg_id)
            dest_pos = self._find_placement(dest_id)
            data["packages"].append({
                "position": list(pkg_pos),
                "destination": list(dest_pos),
                "on_board": True
            })

        # Charge stations
        for cid in ["charge_1", "charge_2"]:
            pos = self._find_placement(cid)
            data["charge_stations"].append({"position": list(pos)})

        return data

    def handle_event(self, event):
        self.error_msg = ""

        # Palette selection
        for tool_id, btn in self.palette_buttons.items():
            if btn.handle_event(event):
                self.selected_tool = tool_id
                return None

        # Grid hover
        if event.type == pygame.MOUSEMOTION:
            self.hovered_cell = self._cell_from_pos(event.pos)

        # Grid click — place or erase
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = self._cell_from_pos(event.pos)
            if cell is not None and self.selected_tool is not None:
                if self.selected_tool == "eraser":
                    self.placements.pop(cell, None)
                else:
                    # Remove previous placement of this tool (each tool is unique)
                    old_pos = self._find_placement(self.selected_tool)
                    if old_pos is not None:
                        del self.placements[old_pos]
                    self.placements[cell] = self.selected_tool

        # Action buttons
        if self.clear_btn.handle_event(event):
            self.placements.clear()
            return None

        if self.back_btn.handle_event(event):
            return "back"

        if self.save_btn.handle_event(event):
            err = self._validate()
            if err:
                self.error_msg = err
                return None
            map_data = self._build_map_data()
            return ("save", map_data)

        return None

    def draw(self, surface):
        # Title
        title_font = get_font(26, bold=True)
        title = title_font.render("Custom Map Builder", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=15))

        # Subtitle
        sub_font = get_font(14)
        sub = sub_font.render("Select an item, then click a cell to place it", True, DARK_GRAY)
        surface.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, y=50))

        # Palette buttons
        for tool_id, btn in self.palette_buttons.items():
            # Highlight selected tool
            if tool_id == self.selected_tool:
                highlight_rect = btn.rect.inflate(4, 4)
                pygame.draw.rect(surface, BLUE, highlight_rect, width=3, border_radius=8)
            btn.draw(surface)

        # Grid lines
        for i in range(board_size + 1):
            pygame.draw.line(surface, BLACK,
                             (self.GRID_X, i * self.CELL_SIZE + self.GRID_Y),
                             (self.GRID_X + board_size * self.CELL_SIZE, i * self.CELL_SIZE + self.GRID_Y),
                             width=3)
            pygame.draw.line(surface, BLACK,
                             (i * self.CELL_SIZE + self.GRID_X, self.GRID_Y),
                             (i * self.CELL_SIZE + self.GRID_X, self.GRID_Y + board_size * self.CELL_SIZE),
                             width=3)

        # Hover highlight
        if self.hovered_cell is not None:
            hx, hy = self.hovered_cell
            hover_rect = pygame.Rect(
                self.GRID_X + hx * self.CELL_SIZE + 2,
                self.GRID_Y + hy * self.CELL_SIZE + 2,
                self.CELL_SIZE - 4, self.CELL_SIZE - 4
            )
            hover_surface = pygame.Surface((hover_rect.width, hover_rect.height), pygame.SRCALPHA)
            hover_surface.fill((100, 150, 255, 60))
            surface.blit(hover_surface, hover_rect.topleft)

        # Draw placed items
        for (cx, cy), tool_id in self.placements.items():
            icon_key = TOOL_ICON_MAP.get(tool_id)
            _, _, fallback_color, fallback_label = next(
                t for t in MAP_TOOLS if t[0] == tool_id
            )
            ix = self.GRID_X + cx * self.CELL_SIZE + 10
            iy = self.GRID_Y + cy * self.CELL_SIZE + 10
            icon_size = 80

            icon = self.icons.get(icon_key) if icon_key else None
            if icon:
                surface.blit(pygame.transform.scale(icon, (icon_size, icon_size)), (ix, iy))
            else:
                _draw_fallback_icon(surface, ix, iy, icon_size, icon_size,
                                    fallback_color, fallback_label)

        # Placement count / status
        status_font = get_font(16)
        placed_count = len(self.placements)
        status_text = f"Items placed: {placed_count}/8"
        if self.selected_tool:
            tool_label = next(label for tid, label, _, _ in MAP_TOOLS if tid == self.selected_tool)
            status_text += f"  |  Selected: {tool_label}"
        status = status_font.render(status_text, True, DARK_GRAY)
        surface.blit(status, (self.GRID_X, self.GRID_Y + board_size * self.CELL_SIZE + 10))

        # Error message
        if self.error_msg:
            err_font = get_font(16, bold=True)
            err = err_font.render(self.error_msg, True, RED)
            surface.blit(err, err.get_rect(centerx=WINDOW_WIDTH // 2, y=740))

        # Action buttons
        self.clear_btn.draw(surface)
        self.back_btn.draw(surface)
        self.save_btn.draw(surface)


class BatchSetupScreen:
    def __init__(self):
        self.dropdown0 = Dropdown(160, 165, 400, 40, VALID_AGENT_NAMES, default_index=0)
        self.dropdown1 = Dropdown(160, 255, 400, 40, VALID_AGENT_NAMES, default_index=1)

        self.time_input = NumberInput(160, 340, "Time Limit (s):", 1.0, 0.1, 30.0, step=0.5, is_float=True)
        self.steps_input = NumberInput(160, 400, "Max Rounds:", 4761, 10, 99999, step=100)

        self.num_games_input = NumberInput(160, 480, "Num Games:", 100, 1, 10000, step=10)
        self.log_rate_input = NumberInput(160, 540, "Log Sample Rate:", 0, 0, 1000, step=1)
        self.csv_checkbox = Checkbox(160, 600, "Save CSV Output")

        self.back_btn = Button(160, 670, 140, 45, "Back", font_size=20)
        self.start_btn = Button(420, 670, 140, 45, "Start", color=GREEN,
                                hover_color=(50, 160, 50), text_color=WHITE, font_size=22)

    def handle_event(self, event):
        # Handle expanded dropdowns first to capture clicks
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
            return "back"
        if self.start_btn.handle_event(event):
            return "start"
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

        # Draw expanded dropdown last (on top of everything)
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
        return {
            "agent0": self.dropdown0.selected,
            "agent1": self.dropdown1.selected,
            "time_limit": self.time_input.get_value(),
            "count_steps": int(self.steps_input.get_value()),
            "batch_mode": True,
            "seed_start": None,
            "num_games": int(self.num_games_input.get_value()),
            "log_sampling_rate": int(self.log_rate_input.get_value()),
            "csv": self.csv_checkbox.is_checked(),
            "output_dir": "batch_results",
            "fail_fast": False,
            "seed_list_file": None,
        }


# =============================================================================
#                           Agent Worker (Threading)
# =============================================================================


class AgentWorker:
    def __init__(self):
        self.thread = None
        self.result_op = None
        self.error = None
        self.done = False

    def start(self, agent, env, agent_id, time_limit):
        self.result_op = None
        self.error = None
        self.done = False
        env_clone = env.clone()
        self.thread = threading.Thread(
            target=self._run,
            args=(agent, env_clone, agent_id, time_limit),
            daemon=True,
        )
        self.thread.start()

    def _run(self, agent, env_clone, agent_id, time_limit):
        try:
            self.result_op = agent.run_step(env_clone, agent_id, time_limit)
        except Exception as e:
            self.error = e
        finally:
            self.done = True

    def is_done(self):
        return self.done

    def get_result(self):
        return self.result_op

    def get_error(self):
        return self.error


# =============================================================================
#                         Batch Progress (Threading)
# =============================================================================


class BatchProgress:
    """Thread-safe shared state between batch worker thread and BatchScreen."""

    def __init__(self, total):
        self.lock = threading.Lock()
        self.total = total
        self.completed = 0
        self.wins_0 = 0
        self.wins_1 = 0
        self.draws = 0
        self.errors = 0
        self.finished = False
        self.error_message = None
        self.summary = None
        self.total_wall_time = None

    def update_after_game(self, result):
        with self.lock:
            self.completed += 1
            if result.error is not None:
                self.errors += 1
            elif result.winner == 0:
                self.wins_0 += 1
            elif result.winner == 1:
                self.wins_1 += 1
            else:
                self.draws += 1

    def snapshot(self):
        with self.lock:
            return {
                "completed": self.completed,
                "total": self.total,
                "wins_0": self.wins_0,
                "wins_1": self.wins_1,
                "draws": self.draws,
                "errors": self.errors,
                "finished": self.finished,
                "error_message": self.error_message,
                "summary": self.summary,
                "total_wall_time": self.total_wall_time,
            }


def _batch_worker(config, progress):
    """Runs in a background thread. Calls run_batch with a progress callback."""
    def on_game_complete(completed, total, results_so_far):
        progress.update_after_game(results_so_far[-1])

    try:
        summary, results, total_wall_time = run_batch(
            config, progress_callback=on_game_complete
        )
        with progress.lock:
            progress.summary = summary
            progress.total_wall_time = total_wall_time
            progress.finished = True
    except Exception as e:
        with progress.lock:
            progress.error_message = str(e)
            progress.finished = True


# =============================================================================
#                               Game State
# =============================================================================


class GameState(Enum):
    READY = "ready"
    WAITING_FOR_INPUT = "waiting"
    COMPUTING = "computing"
    ANIMATING = "animating"
    FINISHED = "finished"


# =============================================================================
#                              Game Logger
# =============================================================================


class GameLogger:
    def __init__(self, config):
        self.entries = []
        self.config = config
        self._log_header()

    def _log_header(self):
        self.entries.append("=" * 60)
        self.entries.append("AI WAREHOUSE GAME LOG")
        self.entries.append("=" * 60)
        self.entries.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.entries.append(f"Agent 0 (Blue): {self.config['agent0']}")
        self.entries.append(f"Agent 1 (Red):  {self.config['agent1']}")
        self.entries.append(f"Time Limit:     {self.config['time_limit']}s")
        self.entries.append(f"Seed:           {self.config['seed']}")
        self.entries.append(f"Max Rounds:     {self.config['count_steps']}")
        self.entries.append("=" * 60)
        self.entries.append("")

    def log_initial_state(self, env):
        self.entries.append("--- INITIAL STATE ---")
        for i, robot in enumerate(env.robots):
            self.entries.append(f"  Robot {i}: position={robot.position}, "
                                f"battery={robot.battery}, credit={robot.credit}")
        for i, pkg in enumerate(env.packages[:2]):
            self.entries.append(f"  Package {i}: position={pkg.position}, "
                                f"destination={pkg.destination}, on_board={pkg.on_board}")
        for i, cs in enumerate(env.charge_stations):
            self.entries.append(f"  Charge Station {i}: position={cs.position}")
        self.entries.append("")

    def log_move(self, round_num, agent_index, agent_name, operator, env):
        self.entries.append(f"[Round {round_num}] Agent {agent_index} ({agent_name}): {operator}")
        for i, robot in enumerate(env.robots):
            pkg_info = ""
            if robot.package is not None:
                pkg_info = (f", carrying=({robot.package.position}"
                            f"->{robot.package.destination})")
            self.entries.append(f"  Robot {i}: pos={robot.position}, "
                                f"bat={robot.battery}, cred={robot.credit}{pkg_info}")

    def log_error(self, round_num, agent_index, agent_name, error):
        self.entries.append(f"[Round {round_num}] Agent {agent_index} ({agent_name}): "
                            f"ERROR - {error}")

    def log_result(self, result_text, balances):
        self.entries.append("")
        self.entries.append("=" * 60)
        self.entries.append("GAME RESULT")
        self.entries.append("=" * 60)
        self.entries.append(f"Final Balances: Agent 0 = {balances[0]}, Agent 1 = {balances[1]}")
        self.entries.append(f"Result: {result_text}")
        self.entries.append("=" * 60)

    def save(self, directory="game_logs"):
        os.makedirs(directory, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        agent0 = self.config["agent0"]
        agent1 = self.config["agent1"]
        seed = self.config["seed"]
        filename = f"game_{agent0}_vs_{agent1}_seed{seed}_{timestamp}.txt"
        filepath = os.path.join(directory, filename)
        with open(filepath, "w") as f:
            f.write("\n".join(self.entries) + "\n")
        return filepath


# =============================================================================
#                              Game Screen
# =============================================================================


class GameScreen:
    def __init__(self, config):
        self.agent_names = [config["agent0"], config["agent1"]]
        self.time_limit = config["time_limit"]
        self.seed = config["seed"]
        self.count_steps = config["count_steps"]
        self.logging_enabled = config.get("logging_enabled", False)
        self.logger = None

        # Initialize environment
        self.env = WarehouseEnv()
        if config.get("custom_map_data"):
            self.env.load_from_map_data(config["custom_map_data"], 2 * self.count_steps)
        else:
            self.env.generate(self.seed, 2 * self.count_steps)

        # Initialize logger
        if self.logging_enabled:
            self.logger = GameLogger(config)
            self.logger.log_initial_state(self.env)

        # Initialize agents
        self.agents = [create_agent(name) for name in self.agent_names]

        # Load icons
        self.icons = load_icons()

        # Game state
        self.game_state = GameState.READY
        self.current_agent_index = 0
        self.current_round = 1
        self.last_operator = None
        self.last_agent_index = None
        self.auto_run = False
        self.step_mode = None  # "move" or "round"
        self.round_step_needs_second = False  # for round stepping: agent 1 still needs to go

        # Animation
        self.animation_start = 0

        # Worker
        self.worker = AgentWorker()

        # Status
        self.status_text = "Ready - choose a run mode below"
        self.result_text = None

        # Buttons
        btn_y = 728
        self.run_btn = Button(10, btn_y, 130, 40, "Run Complete", color=GREEN,
                              hover_color=(50, 160, 50), text_color=WHITE, font_size=17)
        self.step_move_btn = Button(150, btn_y, 120, 40, "Step Move", font_size=17)
        self.step_round_btn = Button(280, btn_y, 120, 40, "Step Round", font_size=17)
        self.pause_btn = Button(410, btn_y, 100, 40, "Pause", font_size=17)
        self.new_game_btn = Button(610, btn_y, 100, 40, "New Game", color=RED,
                                   hover_color=(190, 50, 50), text_color=WHITE, font_size=16)

        self._update_button_states()

    def _update_button_states(self):
        can_act = self.game_state in (GameState.READY, GameState.WAITING_FOR_INPUT)
        self.run_btn.enabled = can_act
        self.step_move_btn.enabled = can_act
        self.step_round_btn.enabled = can_act
        self.pause_btn.enabled = self.auto_run and self.game_state in (
            GameState.COMPUTING, GameState.ANIMATING)
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
            return "new_game"

        return None

    def update(self):
        if self.game_state == GameState.COMPUTING:
            if self.worker.is_done():
                if self.worker.get_error():
                    self.status_text = f"Agent error: {self.worker.get_error()}"
                    if self.logger:
                        self.logger.log_error(
                            self.current_round,
                            self.current_agent_index,
                            self.agent_names[self.current_agent_index],
                            self.worker.get_error(),
                        )
                    self.game_state = GameState.WAITING_FOR_INPUT
                else:
                    op = self.worker.get_result()
                    self._apply_move(op)

        elif self.game_state == GameState.ANIMATING:
            elapsed = pygame.time.get_ticks() - self.animation_start
            anim_delay = 300 if not self.auto_run else 150
            if elapsed >= anim_delay:
                if self.env.done():
                    self._finish_game()
                elif self.auto_run:
                    self._start_agent_computation()
                elif self.step_mode == "round" and self.round_step_needs_second:
                    self.round_step_needs_second = False
                    self._start_agent_computation()
                else:
                    self.game_state = GameState.WAITING_FOR_INPUT
                    self.status_text = "Waiting for input..."

        self._update_button_states()

    def _start_agent_computation(self):
        agent_name = self.agent_names[self.current_agent_index]
        agent = self.agents[self.current_agent_index]
        self.game_state = GameState.COMPUTING
        self.status_text = f"Agent {self.current_agent_index} ({agent_name}) is thinking..."
        self.worker.start(agent, self.env, self.current_agent_index, self.time_limit)

    def _apply_move(self, operator):
        self.env.apply_operator(self.current_agent_index, operator)
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

        self.status_text = (f"Agent {prev_agent} ({self.agent_names[prev_agent]}) "
                            f"chose: {operator}")

        # Check game end
        if self.env.done():
            self.game_state = GameState.ANIMATING
            self.animation_start = pygame.time.get_ticks()
            return

        # For round stepping: if agent 0 just went, schedule agent 1
        if self.step_mode == "round" and prev_agent == 0:
            self.round_step_needs_second = True

        self.game_state = GameState.ANIMATING
        self.animation_start = pygame.time.get_ticks()

    def _finish_game(self):
        self.game_state = GameState.FINISHED
        self.auto_run = False
        balances = self.env.get_balances()
        winner = determine_winner(balances)
        if winner is None:
            self.result_text = f"Draw!  ({balances[0]} vs {balances[1]})"
        else:
            self.result_text = (f"Robot {winner} - {self.agent_names[winner]} "
                                f"({'Blue' if winner == 0 else 'Red'}) wins!  "
                                f"({balances[0]} vs {balances[1]})")
        self.status_text = "Game Over"
        if self.logger:
            self.logger.log_result(self.result_text, balances)
            try:
                saved_path = self.logger.save()
                self.status_text = f"Game Over - Log saved to {saved_path}"
            except OSError as e:
                self.status_text = f"Game Over - Failed to save log: {e}"

    def draw(self, surface):
        # Title
        title_font = get_font(26, bold=True)
        title = title_font.render("AI Warehouse", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=10))

        # Subtitle (matchup)
        sub_font = get_font(16)
        sub = sub_font.render(
            f"{self.agent_names[0]} (Blue)  vs  {self.agent_names[1]} (Red)", True, DARK_GRAY)
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
                f"Agent {self.last_agent_index} ({self.agent_names[self.last_agent_index]}) "
                f"chose: {self.last_operator}")
        info_text = "  |  ".join(info_parts)
        text_surf = font.render(info_text, True, BLACK)
        surface.blit(text_surf, (15, 698))

    def _draw_status(self, surface):
        if self.game_state == GameState.FINISHED and self.result_text:
            # Result banner
            banner_rect = pygame.Rect(10, 778, WINDOW_WIDTH - 20, 60)
            pygame.draw.rect(surface, (40, 40, 40), banner_rect, border_radius=8)
            font = get_font(22, bold=True)
            text = font.render(self.result_text, True, WHITE)
            surface.blit(text, text.get_rect(center=banner_rect.center))
        else:
            font = get_font(16)
            text = font.render(self.status_text, True, DARK_GRAY)
            surface.blit(text, (15, 790))


# =============================================================================
#                              Batch Screen
# =============================================================================


class BatchScreen:
    def __init__(self, config):
        self.config = config
        self.agent0_name = config["agent0"]
        self.agent1_name = config["agent1"]
        self.num_games = config["num_games"]

        # Shared progress state
        self.progress = BatchProgress(self.num_games)

        # Start worker thread
        self.thread = threading.Thread(
            target=_batch_worker,
            args=(config, self.progress),
            daemon=True,
        )
        self.thread.start()

        # Local snapshot for rendering (updated each frame)
        self.snap = self.progress.snapshot()

        # UI elements
        self.new_game_btn = Button(
            260, 780, 200, 50, "New Game", color=RED,
            hover_color=(190, 50, 50), text_color=WHITE, font_size=20
        )
        self.new_game_btn.enabled = False

    def handle_event(self, event):
        if self.new_game_btn.handle_event(event):
            return "new_game"
        return None

    def update(self):
        self.snap = self.progress.snapshot()
        self.new_game_btn.enabled = self.snap["finished"]

    def draw(self, surface):
        self._draw_header(surface)
        self._draw_progress_bar(surface)
        self._draw_live_tallies(surface)
        if self.snap["finished"]:
            self._draw_final_summary(surface)
        self.new_game_btn.draw(surface)

    def _draw_header(self, surface):
        title_font = get_font(28, bold=True)
        title = title_font.render("Batch Run", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=30))

        sub_font = get_font(20)
        matchup = sub_font.render(
            f"{self.agent0_name}  vs  {self.agent1_name}  |  {self.num_games} games",
            True, DARK_GRAY
        )
        surface.blit(matchup, matchup.get_rect(centerx=WINDOW_WIDTH // 2, y=70))

    def _draw_progress_bar(self, surface):
        bar_x, bar_y = 60, 130
        bar_w, bar_h = 600, 40

        # Background
        pygame.draw.rect(surface, LIGHT_GRAY, (bar_x, bar_y, bar_w, bar_h), border_radius=6)
        pygame.draw.rect(surface, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h), width=2, border_radius=6)

        # Filled portion
        completed = self.snap["completed"]
        total = self.snap["total"]
        if total > 0:
            fill_w = int(bar_w * completed / total)
            if fill_w > 0:
                fill_rect = pygame.Rect(bar_x, bar_y, fill_w, bar_h)
                pygame.draw.rect(surface, GREEN, fill_rect, border_radius=6)

        # Text overlay
        pct = (completed / total * 100) if total > 0 else 0
        font = get_font(20, bold=True)
        text = font.render(f"{completed} / {total}  ({pct:.0f}%)", True, BLACK)
        surface.blit(text, text.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h // 2)))

    def _draw_live_tallies(self, surface):
        font = get_font(22)
        bold_font = get_font(22, bold=True)
        y_start = 210
        spacing = 40

        lines = [
            (f"Robot 0 ({self.agent0_name}) wins:", str(self.snap["wins_0"]), BLUE),
            (f"Robot 1 ({self.agent1_name}) wins:", str(self.snap["wins_1"]), RED),
            ("Draws:", str(self.snap["draws"]), DARK_GRAY),
            ("Errors:", str(self.snap["errors"]), ORANGE),
        ]

        for i, (label, value, color) in enumerate(lines):
            y = y_start + i * spacing
            label_surf = font.render(label, True, BLACK)
            surface.blit(label_surf, (80, y))
            value_surf = bold_font.render(value, True, color)
            surface.blit(value_surf, (520, y))

    def _draw_final_summary(self, surface):
        summary = self.snap["summary"]
        if summary is None:
            font = get_font(20)
            err = font.render(f"Batch failed: {self.snap['error_message']}", True, RED)
            surface.blit(err, err.get_rect(centerx=WINDOW_WIDTH // 2, y=420))
            return

        # Divider
        pygame.draw.line(surface, GRAY, (60, 400), (660, 400), width=2)

        bold_font = get_font(20, bold=True)
        font = get_font(18)
        y = 420

        title = bold_font.render("Final Results", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=y))
        y += 35

        lines = [
            f"Win rate R0: {summary['win_rate_0']:.1%}    Win rate R1: {summary['win_rate_1']:.1%}    Draw rate: {summary['draw_rate']:.1%}",
            f"Mean credits R0: {summary['mean_credits_0']}  (p25={summary['p25_credits_0']}, p75={summary['p75_credits_0']})",
            f"Mean credits R1: {summary['mean_credits_1']}  (p25={summary['p25_credits_1']}, p75={summary['p75_credits_1']})",
            f"Mean steps: {summary['mean_steps']}",
            f"Timeout rate R0: {summary['timeout_rate_0']:.1%}    R1: {summary['timeout_rate_1']:.1%}",
            f"Error rate: {summary['error_rate']:.1%}",
        ]

        wall = self.snap.get("total_wall_time")
        if wall is not None:
            lines.append(f"Total wall time: {wall:.1f}s")

        lines.append(f"Output saved to: {self.config.get('output_dir', 'batch_results')}/")

        for line in lines:
            text = font.render(line, True, BLACK)
            surface.blit(text, (80, y))
            y += 28


# =============================================================================
#                              Replay Screen
# =============================================================================


class ReplayScreen:
    """Visual replay of a recorded game with VCR-style controls."""

    SPEED_OPTIONS = [1, 2, 4, 8]
    SPEED_DELAYS = {1: 500, 2: 250, 4: 125, 8: 60}  # ms per move

    def __init__(self, engine, filepath):
        from log_replay import ReplayEngine
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
        self.play_btn = Button(280, btn_y, 90, 40, "Play", color=GREEN,
                               hover_color=(50, 160, 50), text_color=WHITE, font_size=18)
        self.speed_btn = Button(380, btn_y, 70, 40, "1x", font_size=18)
        self.menu_btn = Button(580, btn_y, 110, 40, "Menu", color=RED,
                               hover_color=(190, 50, 50), text_color=WHITE, font_size=18)

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
            self.speed_index = (self.speed_index + 1) % len(self.SPEED_OPTIONS)
        elif self.menu_btn.handle_event(event):
            return "back_to_menu"

        # Progress bar click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.progress_rect.collidepoint(event.pos):
                total = self.engine.total_moves
                if total > 0:
                    fraction = (event.pos[0] - self.progress_rect.x) / self.progress_rect.width
                    target = int(fraction * total)
                    self.engine.go_to_index(target)
                    self.playing = False

        return None

    def update(self):
        if self.playing:
            now = pygame.time.get_ticks()
            delay = self.SPEED_DELAYS[self.SPEED_OPTIONS[self.speed_index]]
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
        sub = sub_font.render(f"{names[0]} (Blue) vs {names[1]} (Red)", True, DARK_GRAY)
        surface.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, y=42))

        # Reuse existing board and robot data rendering
        render_robot_data(surface, self.engine.current_env, self.icons)
        render_board(surface, self.engine.current_env, self.icons)

        # Turn info line
        self._draw_turn_info(surface)

        # Control buttons
        self._update_button_labels()
        for btn in [self.start_btn, self.back_step_btn, self.fwd_step_btn,
                     self.end_btn, self.play_btn, self.speed_btn, self.menu_btn]:
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
        # Background
        pygame.draw.rect(surface, LIGHT_GRAY, self.progress_rect, border_radius=4)
        pygame.draw.rect(surface, DARK_GRAY, self.progress_rect, width=1, border_radius=4)

        # Filled portion
        total = self.engine.total_moves
        if total > 0:
            fill_w = int(self.progress_rect.width * self.engine.current_index / total)
            if fill_w > 0:
                fill_rect = pygame.Rect(self.progress_rect.x, self.progress_rect.y,
                                        fill_w, self.progress_rect.height)
                pygame.draw.rect(surface, BLUE, fill_rect, border_radius=4)

        # Position text
        font = get_font(13)
        label = font.render(f"{self.engine.current_index}/{total}", True, BLACK)
        surface.blit(label, label.get_rect(center=self.progress_rect.center))

    def _draw_status(self, surface):
        font = get_font(14)
        filename = os.path.basename(self.filepath)
        text = font.render(f"Replaying: {filename}", True, DARK_GRAY)
        surface.blit(text, (15, 815))


# =============================================================================
#                            Game Runner (App Controller)
# =============================================================================


class GameRunner:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("AI Warehouse Game Runner")
        self.clock = pygame.time.Clock()
        self.running = True

        self.opening_screen = OpeningScreen()
        self.single_setup_screen = None
        self.batch_setup_screen = None
        self.map_builder_screen = None
        self.game_screen = None
        self.batch_screen = None
        self.file_select_screen = None
        self.replay_screen = None
        self.current_screen = "opening"

    def run(self):
        while self.running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                self._handle_event(event)

            self._update()
            self._draw()
            self.clock.tick(30)

        pygame.quit()

    def _handle_event(self, event):
        if self.current_screen == "opening":
            result = self.opening_screen.handle_event(event)
            if result == "single":
                self.single_setup_screen = SingleGameSetupScreen()
                self.current_screen = "single_setup"
            elif result == "batch":
                self.batch_setup_screen = BatchSetupScreen()
                self.current_screen = "batch_setup"
            elif result == "replay":
                self.file_select_screen = FileSelectScreen()
                self.current_screen = "file_select"

        elif self.current_screen == "single_setup":
            result = self.single_setup_screen.handle_event(event)
            if result == "start":
                config = self.single_setup_screen.get_config()
                self.game_screen = GameScreen(config)
                self.current_screen = "game"
                self.single_setup_screen = None
            elif result == "build_map":
                self.map_builder_screen = MapBuilderScreen()
                self.current_screen = "map_builder"
            elif result == "back":
                self.current_screen = "opening"
                self.single_setup_screen = None

        elif self.current_screen == "map_builder":
            result = self.map_builder_screen.handle_event(event)
            if isinstance(result, tuple) and result[0] == "save":
                self.single_setup_screen.custom_map_data = result[1]
                # Write temp JSON file
                import json
                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.json', prefix='custom_map_',
                    delete=False, dir='.'
                )
                json.dump(result[1], tmp, indent=2)
                tmp.close()
                self.current_screen = "single_setup"
                self.map_builder_screen = None
            elif result == "back":
                self.current_screen = "single_setup"
                self.map_builder_screen = None

        elif self.current_screen == "batch_setup":
            result = self.batch_setup_screen.handle_event(event)
            if result == "start":
                config = self.batch_setup_screen.get_config()
                self.batch_screen = BatchScreen(config)
                self.current_screen = "batch"
                self.batch_setup_screen = None
            elif result == "back":
                self.current_screen = "opening"
                self.batch_setup_screen = None

        elif self.current_screen == "game":
            result = self.game_screen.handle_event(event)
            if result == "new_game":
                self.opening_screen = OpeningScreen()
                self.current_screen = "opening"
                self.game_screen = None

        elif self.current_screen == "batch":
            result = self.batch_screen.handle_event(event)
            if result == "new_game":
                self.opening_screen = OpeningScreen()
                self.current_screen = "opening"
                self.batch_screen = None

        elif self.current_screen == "file_select":
            result = self.file_select_screen.handle_event(event)
            if result == "back":
                self.current_screen = "opening"
                self.file_select_screen = None
            elif isinstance(result, tuple) and result[0] == "load":
                filepath = result[1]
                try:
                    from log_replay import LogParser, ReplayEngine
                    replay_data = LogParser.parse(filepath)
                    engine = ReplayEngine(replay_data)
                    self.replay_screen = ReplayScreen(engine, filepath)
                    self.current_screen = "replay"
                    self.file_select_screen = None
                except Exception as e:
                    self.file_select_screen.show_error(str(e))

        elif self.current_screen == "replay":
            result = self.replay_screen.handle_event(event)
            if result == "back_to_menu":
                self.opening_screen = OpeningScreen()
                self.current_screen = "opening"
                self.replay_screen = None

    def _update(self):
        if self.current_screen == "game" and self.game_screen:
            self.game_screen.update()
        elif self.current_screen == "batch" and self.batch_screen:
            self.batch_screen.update()
        elif self.current_screen == "replay" and self.replay_screen:
            self.replay_screen.update()

    def _draw(self):
        self.screen.fill(PANEL_BG)
        if self.current_screen == "opening":
            self.opening_screen.draw(self.screen)
        elif self.current_screen == "single_setup":
            self.single_setup_screen.draw(self.screen)
        elif self.current_screen == "map_builder":
            self.map_builder_screen.draw(self.screen)
        elif self.current_screen == "batch_setup":
            self.batch_setup_screen.draw(self.screen)
        elif self.current_screen == "game":
            self.game_screen.draw(self.screen)
        elif self.current_screen == "batch":
            self.batch_screen.draw(self.screen)
        elif self.current_screen == "file_select":
            self.file_select_screen.draw(self.screen)
        elif self.current_screen == "replay":
            self.replay_screen.draw(self.screen)
        pygame.display.flip()


# =============================================================================
#                                  Main
# =============================================================================


def main():
    runner = GameRunner()
    runner.run()


if __name__ == "__main__":
    main()
