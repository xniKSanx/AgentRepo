"""Shared UI constants: window dimensions, colors, and font helper."""

import pygame


# Window
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
    """Return a pygame SysFont for *arial* at the given size."""
    return pygame.font.SysFont("arial", size, bold=bold)
