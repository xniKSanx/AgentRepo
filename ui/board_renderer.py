"""Board rendering with dynamic layout derived from board_size.

All grid geometry is computed from ``BoardLayout`` so that no hardcoded
5x5 constants remain in the rendering code.
"""

import logging
from dataclasses import dataclass

import pygame

from WarehouseEnv import board_size
from ui.constants import (
    BLACK, BLUE, RED, GREEN, YELLOW, ORANGE,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    get_font,
)

_logger = logging.getLogger("board_renderer")


# ---------------------------------------------------------------------------
# Dynamic layout
# ---------------------------------------------------------------------------

@dataclass
class BoardLayout:
    """All rendering geometry derived from board_size."""

    board_size: int
    grid_x: int = 110
    grid_y: int = 190
    cell_size: int = 100

    @property
    def grid_width(self):
        return self.board_size * self.cell_size

    @property
    def grid_height(self):
        return self.board_size * self.cell_size

    def cell_origin(self, col, row):
        """Top-left pixel of a cell (2px inset from grid line)."""
        return (self.grid_x + col * self.cell_size + 2,
                self.grid_y + row * self.cell_size + 2)

    def icon_origin(self, col, row):
        """Top-left for icon rendering (10px inset from grid line)."""
        return (self.grid_x + col * self.cell_size + 10,
                self.grid_y + row * self.cell_size + 10)


# Module-level default layout
_default_layout = BoardLayout(board_size=board_size)


def validate_layout(layout):
    """Log a warning if the window is too small for the given layout."""
    needed_w = layout.grid_x + layout.grid_width + 10
    needed_h = layout.grid_y + layout.grid_height + 160
    if needed_w > WINDOW_WIDTH or needed_h > WINDOW_HEIGHT:
        _logger.warning(
            "Board size %d requires %dx%d but window is %dx%d",
            layout.board_size, needed_w, needed_h,
            WINDOW_WIDTH, WINDOW_HEIGHT,
        )


# Run sanity check on import
validate_layout(_default_layout)


# ---------------------------------------------------------------------------
# Icon loading
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Robot data panel
# ---------------------------------------------------------------------------

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
            surface.blit(
                pygame.transform.scale(icon, (95, 95)), (icon_x, icon_y)
            )
        else:
            _draw_fallback_icon(
                surface, icon_x, icon_y, 80, 80,
                fallback_color, fallback_label,
            )

        surface.blit(font.render(pos_txt, True, BLACK), (text_x, 95))
        surface.blit(font.render(bat_txt, True, BLACK), (text_x, 115))
        surface.blit(font.render(cred_txt, True, BLACK), (text_x, 135))

        if robot.package is not None:
            pkg_txt = (
                f"package: {robot.package.position} "
                f"-> {robot.package.destination}"
            )
            surface.blit(font.render(pkg_txt, True, BLACK), (text_x, 155))


# ---------------------------------------------------------------------------
# Board grid rendering (dynamic layout)
# ---------------------------------------------------------------------------

def render_board(surface, env, icons, layout=None):
    if layout is None:
        layout = _default_layout

    # Sanity check
    if layout.board_size != board_size:
        _logger.error(
            "BoardLayout.board_size (%d) != WarehouseEnv.board_size (%d)",
            layout.board_size, board_size,
        )

    # Grid lines — derived from layout
    for i in range(layout.board_size + 1):
        y = layout.grid_y + i * layout.cell_size
        x = layout.grid_x + i * layout.cell_size
        pygame.draw.line(
            surface, BLACK,
            (layout.grid_x, y),
            (layout.grid_x + layout.grid_width, y),
            width=3,
        )
        pygame.draw.line(
            surface, BLACK,
            (x, layout.grid_y),
            (x, layout.grid_y + layout.grid_height),
            width=3,
        )

    # Icon dimensions derived from cell_size
    cell_icon_size = layout.cell_size - 5   # main entity (robot)
    small_icon_size = layout.cell_size - 20  # packages, stations, etc.

    # Board entities
    for row in range(layout.board_size):
        for col in range(layout.board_size):
            p = (col, row)
            robot = env.get_robot_in(p)
            package = env.get_package_in(p)
            charge_station = env.get_charge_station_in(p)
            package_destination = [
                pkg for pkg in env.packages
                if pkg.destination == p and pkg.on_board
            ]
            robot_package_destination = [
                i for i, r in enumerate(env.robots)
                if r.package is not None and r.package.destination == p
            ]

            cell_x, cell_y = layout.cell_origin(col, row)
            icon_x, icon_y = layout.icon_origin(col, row)

            if robot:
                ridx = env.robots.index(robot)
                if ridx == 0:
                    if robot.package is not None:
                        icon = icons.get("blue_robot_package")
                    else:
                        icon = icons.get("blue_robot")
                    if icon:
                        surface.blit(
                            pygame.transform.scale(
                                icon, (cell_icon_size, cell_icon_size)
                            ),
                            (cell_x, cell_y),
                        )
                    else:
                        label = "R0+" if robot.package else "R0"
                        _draw_fallback_icon(
                            surface, cell_x, cell_y,
                            cell_icon_size - 5, cell_icon_size - 5,
                            BLUE, label,
                        )
                else:
                    if robot.package is not None:
                        icon = icons.get("red_robot_package")
                    else:
                        icon = icons.get("red_robot")
                    if icon:
                        surface.blit(
                            pygame.transform.scale(
                                icon, (cell_icon_size, cell_icon_size)
                            ),
                            (cell_x, cell_y),
                        )
                    else:
                        label = "R1+" if robot.package else "R1"
                        _draw_fallback_icon(
                            surface, cell_x, cell_y,
                            cell_icon_size - 5, cell_icon_size - 5,
                            RED, label,
                        )

            elif charge_station:
                icon = icons.get("charge_station")
                if icon:
                    surface.blit(
                        pygame.transform.scale(
                            icon, (small_icon_size, small_icon_size)
                        ),
                        (icon_x, icon_y),
                    )
                else:
                    _draw_fallback_icon(
                        surface, icon_x, icon_y,
                        small_icon_size, small_icon_size,
                        GREEN, "CS",
                    )

            elif package and package.on_board:
                pidx = (
                    env.packages[0:2].index(package)
                    if package in env.packages[0:2]
                    else 0
                )
                icon_key = "package_1" if pidx == 0 else "package_2"
                icon = icons.get(icon_key)
                if icon:
                    surface.blit(
                        pygame.transform.scale(
                            icon, (small_icon_size, small_icon_size)
                        ),
                        (icon_x, icon_y),
                    )
                else:
                    _draw_fallback_icon(
                        surface, icon_x, icon_y,
                        small_icon_size, small_icon_size,
                        YELLOW, f"P{pidx}",
                    )

            elif len(package_destination) > 0:
                pkg = package_destination[0]
                pidx = (
                    env.packages.index(pkg) if pkg in env.packages else 0
                )
                icon_key = "dest_1" if pidx == 0 else "dest_2"
                icon = icons.get(icon_key)
                if icon:
                    surface.blit(
                        pygame.transform.scale(
                            icon, (small_icon_size, small_icon_size)
                        ),
                        (icon_x, icon_y),
                    )
                else:
                    _draw_fallback_icon(
                        surface, icon_x, icon_y,
                        small_icon_size, small_icon_size,
                        ORANGE, f"D{pidx}",
                    )

            elif len(robot_package_destination) > 0:
                ridx = robot_package_destination[0]
                icon_key = "dest_blue" if ridx == 0 else "dest_red"
                icon = icons.get(icon_key)
                if icon:
                    surface.blit(
                        pygame.transform.scale(
                            icon, (small_icon_size, small_icon_size)
                        ),
                        (icon_x, icon_y),
                    )
                else:
                    color = BLUE if ridx == 0 else RED
                    _draw_fallback_icon(
                        surface, icon_x, icon_y,
                        small_icon_size, small_icon_size,
                        color, f"X{ridx}",
                    )
