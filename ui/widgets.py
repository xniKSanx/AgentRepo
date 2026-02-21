"""Reusable UI primitive widgets for pygame screens."""

import pygame

from ui.constants import (
    WHITE, BLACK, GRAY, LIGHT_GRAY, DARK_GRAY,
    GREEN, BLUE, HOVER_GRAY, DISABLED_GRAY,
    get_font,
)


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
            pts = [(arrow_x - 6, arrow_y + 3), (arrow_x + 6, arrow_y + 3),
                   (arrow_x, arrow_y - 5)]
        else:
            pts = [(arrow_x - 6, arrow_y - 3), (arrow_x + 6, arrow_y - 3),
                   (arrow_x, arrow_y + 5)]
        pygame.draw.polygon(surface, BLACK, pts)

        if self.expanded:
            for i, option in enumerate(self.options):
                opt_rect = pygame.Rect(
                    self.rect.x,
                    self.rect.bottom + i * self.rect.height,
                    self.rect.width,
                    self.rect.height,
                )
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
                opt_rect = pygame.Rect(
                    self.rect.x,
                    self.rect.bottom + i * self.rect.height,
                    self.rect.width,
                    self.rect.height,
                )
                if opt_rect.collidepoint(event.pos):
                    self.hovered_option = i
                    break
            else:
                self.hovered_option = -1

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.expanded:
                for i in range(len(self.options)):
                    opt_rect = pygame.Rect(
                        self.rect.x,
                        self.rect.bottom + i * self.rect.height,
                        self.rect.width,
                        self.rect.height,
                    )
                    if opt_rect.collidepoint(event.pos):
                        self.selected_index = i
                        self.expanded = False
                        self.hovered_option = -1
                        return True
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
    def __init__(self, x, y, label, value, min_val, max_val, step=1,
                 is_float=False):
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
        pygame.draw.rect(surface, BLACK, self.minus_rect, width=2,
                         border_radius=4)
        minus_text = get_font(24, bold=True).render("-", True, BLACK)
        surface.blit(minus_text,
                     minus_text.get_rect(center=self.minus_rect.center))

        # Value display
        pygame.draw.rect(surface, WHITE, self.value_rect, border_radius=4)
        pygame.draw.rect(surface, BLACK, self.value_rect, width=2,
                         border_radius=4)
        if self.is_float:
            val_str = f"{self.value:.1f}"
        else:
            val_str = str(int(self.value))
        val_surf = font.render(val_str, True, BLACK)
        surface.blit(val_surf,
                     val_surf.get_rect(center=self.value_rect.center))

        # Plus button
        pygame.draw.rect(surface, GRAY, self.plus_rect, border_radius=4)
        pygame.draw.rect(surface, BLACK, self.plus_rect, width=2,
                         border_radius=4)
        plus_text = get_font(24, bold=True).render("+", True, BLACK)
        surface.blit(plus_text,
                     plus_text.get_rect(center=self.plus_rect.center))

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
        pygame.draw.rect(surface, BLACK, self.box_rect, width=2,
                         border_radius=4)

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
