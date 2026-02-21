"""Custom map builder screen."""

import pygame

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, GRAY, DARK_GRAY, BLUE, RED, GREEN, YELLOW,
    ORANGE, LIGHT_GRAY, HOVER_GRAY, WHITE,
    get_font,
)
from ui.widgets import Button
from ui.board_renderer import load_icons, _draw_fallback_icon
from WarehouseEnv import board_size


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


class MapBuilderScreen(Screen):
    # Grid geometry — derived from board_size
    GRID_X = 110
    GRID_Y = 170
    CELL_SIZE = 100

    def __init__(self):
        self.icons = load_icons()
        self.selected_tool = None
        self.placements = {}
        self.hovered_cell = None
        self.error_msg = ""

        # Build palette buttons
        self.palette_buttons = {}
        bx = 10
        for tool_id, label, color, _ in MAP_TOOLS:
            btn_w = max(68, get_font(13).size(label)[0] + 14)
            btn = Button(bx, 75, btn_w, 30, label, color=GRAY,
                         hover_color=HOVER_GRAY, text_color=BLACK,
                         font_size=13)
            self.palette_buttons[tool_id] = btn
            bx += btn_w + 4

        # Action buttons
        self.clear_btn = Button(
            30, 780, 120, 42, "Clear All", color=RED,
            hover_color=(190, 50, 50), text_color=WHITE, font_size=18,
        )
        self.back_btn = Button(260, 780, 120, 42, "Back", font_size=18)
        self.save_btn = Button(
            490, 780, 120, 42, "Save", color=GREEN,
            hover_color=(50, 160, 50), text_color=WHITE, font_size=18,
        )

    def _cell_from_pos(self, pos):
        """Convert pixel position to grid (x,y) or None if outside grid."""
        px, py = pos
        gx = (px - self.GRID_X) // self.CELL_SIZE
        gy = (py - self.GRID_Y) // self.CELL_SIZE
        if 0 <= gx < board_size and 0 <= gy < board_size:
            if (self.GRID_X <= px < self.GRID_X + board_size * self.CELL_SIZE
                    and self.GRID_Y <= py < self.GRID_Y + board_size * self.CELL_SIZE):
                return (gx, gy)
        return None

    def _find_placement(self, tool_id):
        """Find the cell where a tool_id is currently placed, or None."""
        for pos, tid in self.placements.items():
            if tid == tool_id:
                return pos
        return None

    def _validate(self):
        """Check if all required items are placed."""
        required = [
            "robot_0", "robot_1", "package_1", "package_1_dest",
            "package_2", "package_2_dest", "charge_1", "charge_2",
        ]
        placed = set(self.placements.values())
        missing = [tid for tid in required if tid not in placed]
        if missing:
            labels = {tid: label for tid, label, _, _ in MAP_TOOLS}
            names = ", ".join(labels[m] for m in missing)
            return f"Missing: {names}"

        for pkg_id, dest_id in [("package_1", "package_1_dest"),
                                ("package_2", "package_2_dest")]:
            pkg_pos = self._find_placement(pkg_id)
            dest_pos = self._find_placement(dest_id)
            if pkg_pos and dest_pos and pkg_pos == dest_pos:
                return "Package and its destination cannot be on the same cell"

        return ""

    def _build_map_data(self):
        """Convert placements to the JSON-compatible map data dict."""
        data = {
            "board_size": board_size,
            "robots": [],
            "packages": [],
            "charge_stations": [],
        }

        for rid in ["robot_0", "robot_1"]:
            pos = self._find_placement(rid)
            data["robots"].append({
                "position": list(pos),
                "battery": 20,
                "credit": 0,
            })

        for pkg_id, dest_id in [("package_1", "package_1_dest"),
                                ("package_2", "package_2_dest")]:
            pkg_pos = self._find_placement(pkg_id)
            dest_pos = self._find_placement(dest_id)
            data["packages"].append({
                "position": list(pkg_pos),
                "destination": list(dest_pos),
                "on_board": True,
            })

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

        # Grid click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = self._cell_from_pos(event.pos)
            if cell is not None and self.selected_tool is not None:
                if self.selected_tool == "eraser":
                    self.placements.pop(cell, None)
                else:
                    old_pos = self._find_placement(self.selected_tool)
                    if old_pos is not None:
                        del self.placements[old_pos]
                    self.placements[cell] = self.selected_tool

        # Action buttons
        if self.clear_btn.handle_event(event):
            self.placements.clear()
            return None

        if self.back_btn.handle_event(event):
            return (ScreenId.SINGLE_SETUP, {})

        if self.save_btn.handle_event(event):
            err = self._validate()
            if err:
                self.error_msg = err
                return None
            map_data = self._build_map_data()
            return (ScreenId.SINGLE_SETUP, {"map_data": map_data})

        return None

    def draw(self, surface):
        # Title
        title_font = get_font(26, bold=True)
        title = title_font.render("Custom Map Builder", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=15))

        sub_font = get_font(14)
        sub = sub_font.render(
            "Select an item, then click a cell to place it", True, DARK_GRAY,
        )
        surface.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, y=50))

        # Palette buttons
        for tool_id, btn in self.palette_buttons.items():
            if tool_id == self.selected_tool:
                highlight_rect = btn.rect.inflate(4, 4)
                pygame.draw.rect(
                    surface, BLUE, highlight_rect, width=3, border_radius=8,
                )
            btn.draw(surface)

        # Grid lines — dynamic from board_size
        for i in range(board_size + 1):
            pygame.draw.line(
                surface, BLACK,
                (self.GRID_X,
                 i * self.CELL_SIZE + self.GRID_Y),
                (self.GRID_X + board_size * self.CELL_SIZE,
                 i * self.CELL_SIZE + self.GRID_Y),
                width=3,
            )
            pygame.draw.line(
                surface, BLACK,
                (i * self.CELL_SIZE + self.GRID_X,
                 self.GRID_Y),
                (i * self.CELL_SIZE + self.GRID_X,
                 self.GRID_Y + board_size * self.CELL_SIZE),
                width=3,
            )

        # Hover highlight
        if self.hovered_cell is not None:
            hx, hy = self.hovered_cell
            hover_rect = pygame.Rect(
                self.GRID_X + hx * self.CELL_SIZE + 2,
                self.GRID_Y + hy * self.CELL_SIZE + 2,
                self.CELL_SIZE - 4, self.CELL_SIZE - 4,
            )
            hover_surface = pygame.Surface(
                (hover_rect.width, hover_rect.height), pygame.SRCALPHA,
            )
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
                surface.blit(
                    pygame.transform.scale(icon, (icon_size, icon_size)),
                    (ix, iy),
                )
            else:
                _draw_fallback_icon(
                    surface, ix, iy, icon_size, icon_size,
                    fallback_color, fallback_label,
                )

        # Placement count / status
        status_font = get_font(16)
        placed_count = len(self.placements)
        status_text = f"Items placed: {placed_count}/8"
        if self.selected_tool:
            tool_label = next(
                label for tid, label, _, _ in MAP_TOOLS
                if tid == self.selected_tool
            )
            status_text += f"  |  Selected: {tool_label}"
        status = status_font.render(status_text, True, DARK_GRAY)
        surface.blit(
            status,
            (self.GRID_X,
             self.GRID_Y + board_size * self.CELL_SIZE + 10),
        )

        # Error message
        if self.error_msg:
            err_font = get_font(16, bold=True)
            err = err_font.render(self.error_msg, True, RED)
            surface.blit(err, err.get_rect(centerx=WINDOW_WIDTH // 2, y=740))

        # Action buttons
        self.clear_btn.draw(surface)
        self.back_btn.draw(surface)
        self.save_btn.draw(surface)
