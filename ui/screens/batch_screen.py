"""Batch run progress and results screen."""

import threading

import pygame

from ui import Screen, ScreenId
from ui.constants import (
    WINDOW_WIDTH, BLACK, GRAY, DARK_GRAY, LIGHT_GRAY,
    BLUE, RED, GREEN, ORANGE, WHITE,
    get_font,
)
from ui.widgets import Button
from batch_runner import run_batch


# ---------------------------------------------------------------------------
# Thread-safe progress tracking
# ---------------------------------------------------------------------------

class BatchProgress:
    """Thread-safe shared state between batch worker and BatchScreen."""

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
    """Background thread target — runs batch via run_batch()."""
    def on_game_complete(completed, total, results_so_far):
        progress.update_after_game(results_so_far[-1])

    try:
        summary, results, total_wall_time = run_batch(
            config, progress_callback=on_game_complete,
        )
        with progress.lock:
            progress.summary = summary
            progress.total_wall_time = total_wall_time
            progress.finished = True
    except Exception as e:
        with progress.lock:
            progress.error_message = str(e)
            progress.finished = True


# ---------------------------------------------------------------------------
# Batch screen
# ---------------------------------------------------------------------------

class BatchScreen(Screen):
    def __init__(self, config):
        self.config = config
        self.agent0_name = config.agent0
        self.agent1_name = config.agent1
        self.num_games = config.num_games

        # Shared progress state
        self.progress = BatchProgress(self.num_games)

        # Start worker thread
        self.thread = threading.Thread(
            target=_batch_worker,
            args=(config, self.progress),
            daemon=True,
        )
        self.thread.start()

        # Local snapshot for rendering
        self.snap = self.progress.snapshot()

        # UI elements
        self.new_game_btn = Button(
            260, 780, 200, 50, "New Game", color=RED,
            hover_color=(190, 50, 50), text_color=WHITE, font_size=20,
        )
        self.new_game_btn.enabled = False

    def handle_event(self, event):
        if self.new_game_btn.handle_event(event):
            return ScreenId.OPENING
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
            f"{self.agent0_name}  vs  {self.agent1_name}"
            f"  |  {self.num_games} games",
            True, DARK_GRAY,
        )
        surface.blit(
            matchup, matchup.get_rect(centerx=WINDOW_WIDTH // 2, y=70),
        )

    def _draw_progress_bar(self, surface):
        bar_x, bar_y = 60, 130
        bar_w, bar_h = 600, 40

        pygame.draw.rect(
            surface, LIGHT_GRAY, (bar_x, bar_y, bar_w, bar_h),
            border_radius=6,
        )
        pygame.draw.rect(
            surface, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h),
            width=2, border_radius=6,
        )

        completed = self.snap["completed"]
        total = self.snap["total"]
        if total > 0:
            fill_w = int(bar_w * completed / total)
            if fill_w > 0:
                fill_rect = pygame.Rect(bar_x, bar_y, fill_w, bar_h)
                pygame.draw.rect(
                    surface, GREEN, fill_rect, border_radius=6,
                )

        pct = (completed / total * 100) if total > 0 else 0
        font = get_font(20, bold=True)
        text = font.render(
            f"{completed} / {total}  ({pct:.0f}%)", True, BLACK,
        )
        surface.blit(
            text,
            text.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h // 2)),
        )

    def _draw_live_tallies(self, surface):
        font = get_font(22)
        bold_font = get_font(22, bold=True)
        y_start = 210
        spacing = 40

        lines = [
            (f"Robot 0 ({self.agent0_name}) wins:",
             str(self.snap["wins_0"]), BLUE),
            (f"Robot 1 ({self.agent1_name}) wins:",
             str(self.snap["wins_1"]), RED),
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
            err = font.render(
                f"Batch failed: {self.snap['error_message']}", True, RED,
            )
            surface.blit(
                err, err.get_rect(centerx=WINDOW_WIDTH // 2, y=420),
            )
            return

        pygame.draw.line(surface, GRAY, (60, 400), (660, 400), width=2)

        bold_font = get_font(20, bold=True)
        font = get_font(18)
        y = 420

        title = bold_font.render("Final Results", True, BLACK)
        surface.blit(title, title.get_rect(centerx=WINDOW_WIDTH // 2, y=y))
        y += 35

        lines = [
            f"Win rate R0: {summary['win_rate_0']:.1%}"
            f"    Win rate R1: {summary['win_rate_1']:.1%}"
            f"    Draw rate: {summary['draw_rate']:.1%}",
            f"Mean credits R0: {summary['mean_credits_0']}"
            f"  (p25={summary['p25_credits_0']},"
            f" p75={summary['p75_credits_0']})",
            f"Mean credits R1: {summary['mean_credits_1']}"
            f"  (p25={summary['p25_credits_1']},"
            f" p75={summary['p75_credits_1']})",
            f"Mean steps: {summary['mean_steps']}",
            f"Timeout rate R0: {summary['timeout_rate_0']:.1%}"
            f"    R1: {summary['timeout_rate_1']:.1%}",
            f"Error rate: {summary['error_rate']:.1%}",
        ]

        wall = self.snap.get("total_wall_time")
        if wall is not None:
            lines.append(f"Total wall time: {wall:.1f}s")

        lines.append(
            f"Output saved to: {self.config.output_dir}/"
        )

        for line in lines:
            text = font.render(line, True, BLACK)
            surface.blit(text, (80, y))
            y += 28
