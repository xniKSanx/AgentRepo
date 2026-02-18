import pygame
import threading
import time
import random
import os
from enum import Enum
from datetime import datetime

from WarehouseEnv import WarehouseEnv, manhattan_distance, board_size
import Agent
import submission

# =============================================================================
#                               Constants
# =============================================================================

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 850

AGENT_NAMES = [
    "random", "greedy", "greedyImproved", "minimax",
    "alphabeta", "expectimax", "hardcoded",
]

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
#                              Agent Helpers
# =============================================================================


def create_agents():
    return {
        "random": Agent.AgentRandom(),
        "greedy": Agent.AgentGreedy(),
        "greedyImproved": submission.AgentGreedyImproved(),
        "minimax": submission.AgentMinimax(),
        "alphabeta": submission.AgentAlphaBeta(),
        "expectimax": submission.AgentExpectimax(),
        "hardcoded": submission.AgentHardCoded(),
    }


# =============================================================================
#                              Screens
# =============================================================================


class SetupScreen:
    def __init__(self):
        self.dropdown0 = Dropdown(220, 250, 280, 40, AGENT_NAMES, default_index=0)
        self.dropdown1 = Dropdown(220, 370, 280, 40, AGENT_NAMES, default_index=1)
        self.start_btn = Button(260, 480, 200, 50, "Start Game", color=GREEN,
                                hover_color=(50, 160, 50), text_color=WHITE, font_size=22)

    def handle_event(self, event):
        # Handle dropdowns (expanded one first to capture clicks)
        if self.dropdown0.is_expanded():
            self.dropdown0.handle_event(event)
            return None
        if self.dropdown1.is_expanded():
            self.dropdown1.handle_event(event)
            return None

        self.dropdown0.handle_event(event)
        self.dropdown1.handle_event(event)

        if self.start_btn.handle_event(event):
            return "start"
        return None

    def draw(self, surface):
        # Title
        title_font = get_font(32, bold=True)
        title = title_font.render("AI Warehouse Game Runner", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=80))

        # Subtitle
        sub_font = get_font(18)
        subtitle = sub_font.render("Select the two agents to compete", True, DARK_GRAY)
        surface.blit(subtitle, subtitle.get_rect(centerx=WINDOW_WIDTH // 2, y=130))

        # Labels
        label_font = get_font(22, bold=True)
        lbl0 = label_font.render("Robot 0 (Blue):", True, BLUE)
        surface.blit(lbl0, (220, 218))
        lbl1 = label_font.render("Robot 1 (Red):", True, RED)
        surface.blit(lbl1, (220, 338))

        # Draw non-expanded dropdown first, expanded one last (on top)
        if self.dropdown1.is_expanded():
            self.dropdown0.draw(surface)
            self.start_btn.draw(surface)
            self.dropdown1.draw(surface)
        elif self.dropdown0.is_expanded():
            self.dropdown1.draw(surface)
            self.start_btn.draw(surface)
            self.dropdown0.draw(surface)
        else:
            self.dropdown0.draw(surface)
            self.dropdown1.draw(surface)
            self.start_btn.draw(surface)

    def get_agent0(self):
        return self.dropdown0.selected

    def get_agent1(self):
        return self.dropdown1.selected


class SettingsScreen:
    def __init__(self, agent0_name, agent1_name):
        self.agent0_name = agent0_name
        self.agent1_name = agent1_name

        self.time_input = NumberInput(160, 260, "Time Limit (s):", 1.0, 0.1, 30.0, step=0.5, is_float=True)
        self.seed_input = NumberInput(160, 330, "Seed (0=random):", 0, 0, 9999, step=1)
        self.steps_input = NumberInput(160, 400, "Max Rounds:", 4761, 10, 99999, step=100)

        self.log_checkbox = Checkbox(160, 450, "Enable Game Logging")

        self.back_btn = Button(160, 500, 140, 45, "Back", font_size=20)
        self.play_btn = Button(420, 500, 140, 45, "Play", color=GREEN,
                               hover_color=(50, 160, 50), text_color=WHITE, font_size=22)

    def handle_event(self, event):
        self.time_input.handle_event(event)
        self.seed_input.handle_event(event)
        self.steps_input.handle_event(event)
        self.log_checkbox.handle_event(event)

        if self.back_btn.handle_event(event):
            return "back"
        if self.play_btn.handle_event(event):
            return "play"
        return None

    def draw(self, surface):
        title_font = get_font(28, bold=True)
        title = title_font.render("Game Settings", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=80))

        matchup_font = get_font(20)
        matchup = matchup_font.render(
            f"{self.agent0_name} (Blue)  vs  {self.agent1_name} (Red)", True, DARK_GRAY)
        surface.blit(matchup, matchup.get_rect(centerx=WINDOW_WIDTH // 2, y=150))

        # Divider
        pygame.draw.line(surface, GRAY, (140, 200), (580, 200), width=1)

        self.time_input.draw(surface)
        self.seed_input.draw(surface)
        self.steps_input.draw(surface)
        self.log_checkbox.draw(surface)

        self.back_btn.draw(surface)
        self.play_btn.draw(surface)

    def get_config(self):
        seed_val = int(self.seed_input.get_value())
        if seed_val == 0:
            seed_val = random.randint(0, 255)
        return {
            "agent0": self.agent0_name,
            "agent1": self.agent1_name,
            "time_limit": self.time_input.get_value(),
            "seed": seed_val,
            "count_steps": int(self.steps_input.get_value()),
            "logging_enabled": self.log_checkbox.is_checked(),
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
        self.env.generate(self.seed, 2 * self.count_steps)

        # Initialize logger
        if self.logging_enabled:
            self.logger = GameLogger(config)
            self.logger.log_initial_state(self.env)

        # Initialize agents
        self.agents = create_agents()

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
        agent = self.agents[agent_name]
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
        if balances[0] == balances[1]:
            self.result_text = f"Draw!  ({balances[0]} vs {balances[1]})"
        elif balances[0] > balances[1]:
            self.result_text = (f"Robot 0 - {self.agent_names[0]} (Blue) wins!  "
                                f"({balances[0]} vs {balances[1]})")
        else:
            self.result_text = (f"Robot 1 - {self.agent_names[1]} (Red) wins!  "
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
#                            Game Runner (App Controller)
# =============================================================================


class GameRunner:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("AI Warehouse Game Runner")
        self.clock = pygame.time.Clock()
        self.running = True

        self.setup_screen = SetupScreen()
        self.settings_screen = None
        self.game_screen = None
        self.current_screen = "setup"

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
        if self.current_screen == "setup":
            result = self.setup_screen.handle_event(event)
            if result == "start":
                self.settings_screen = SettingsScreen(
                    self.setup_screen.get_agent0(),
                    self.setup_screen.get_agent1(),
                )
                self.current_screen = "settings"

        elif self.current_screen == "settings":
            result = self.settings_screen.handle_event(event)
            if result == "play":
                config = self.settings_screen.get_config()
                self.game_screen = GameScreen(config)
                self.current_screen = "game"
            elif result == "back":
                self.current_screen = "setup"

        elif self.current_screen == "game":
            result = self.game_screen.handle_event(event)
            if result == "new_game":
                self.setup_screen = SetupScreen()
                self.current_screen = "setup"
                self.game_screen = None

    def _update(self):
        if self.current_screen == "game" and self.game_screen:
            self.game_screen.update()

    def _draw(self):
        self.screen.fill(PANEL_BG)
        if self.current_screen == "setup":
            self.setup_screen.draw(self.screen)
        elif self.current_screen == "settings":
            self.settings_screen.draw(self.screen)
        elif self.current_screen == "game":
            self.game_screen.draw(self.screen)
        pygame.display.flip()


# =============================================================================
#                                  Main
# =============================================================================


def main():
    runner = GameRunner()
    runner.run()


if __name__ == "__main__":
    main()
