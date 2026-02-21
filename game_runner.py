"""AI Warehouse Game Runner — thin application router.

All screen controllers, widgets, and rendering live in the ``ui``
package.  This module wires screens together via a typed ``ScreenId``
dispatch and delegates to core modules (no game logic here).
"""

import logging
import traceback as tb_module
from datetime import datetime

import pygame

from ui import ScreenId, Screen
from ui.constants import WINDOW_WIDTH, WINDOW_HEIGHT, PANEL_BG
from ui.screens.opening import OpeningScreen
from ui.screens.single_setup import SingleGameSetupScreen
from ui.screens.map_builder import MapBuilderScreen
from ui.screens.batch_setup import BatchSetupScreen
from ui.screens.game_screen import GameScreen
from ui.screens.batch_screen import BatchScreen
from ui.screens.file_select import FileSelectScreen
from ui.screens.replay import ReplayScreen

gui_logger = logging.getLogger("game_runner")


class GameRunner:
    """Top-level application router.

    Manages a single ``active_screen`` reference and a typed dispatch
    for transitions.  Each screen returns ``ScreenId`` or
    ``(ScreenId, dict)`` from its ``handle_event`` to request a
    navigation.
    """

    def __init__(self):
        pygame.init()
        self.screen_surface = pygame.display.set_mode(
            (WINDOW_WIDTH, WINDOW_HEIGHT),
        )
        pygame.display.set_caption("AI Warehouse Game Runner")
        self.clock = pygame.time.Clock()
        self.running = True

        self._active_id = None
        self._active_screen = None
        self._stashed_setup = None  # preserved across MAP_BUILDER detour

        self._navigate(ScreenId.OPENING)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, screen_id, **kwargs):
        """Transition to a new screen, calling lifecycle hooks."""
        if self._active_screen is not None:
            self._active_screen.on_exit()

        screen = self._create_screen(screen_id, **kwargs)
        self._active_id = screen_id
        self._active_screen = screen
        self._active_screen.on_enter(**kwargs)

    def _create_screen(self, screen_id, **kwargs):
        """Instantiate the screen for *screen_id*."""
        if screen_id == ScreenId.OPENING:
            return OpeningScreen()
        elif screen_id == ScreenId.SINGLE_SETUP:
            return SingleGameSetupScreen()
        elif screen_id == ScreenId.MAP_BUILDER:
            return MapBuilderScreen()
        elif screen_id == ScreenId.BATCH_SETUP:
            return BatchSetupScreen()
        elif screen_id == ScreenId.GAME:
            return GameScreen(kwargs["config"])
        elif screen_id == ScreenId.BATCH:
            return BatchScreen(kwargs["config"])
        elif screen_id == ScreenId.FILE_SELECT:
            return FileSelectScreen()
        elif screen_id == ScreenId.REPLAY:
            return ReplayScreen(kwargs["engine"], kwargs["filepath"])
        raise ValueError(f"Unknown screen: {screen_id}")

    def _process_transition(self, result):
        """Single dispatch point for all screen transitions."""
        if result is None:
            return

        if isinstance(result, tuple):
            target_id = result[0]
            kwargs = result[1] if len(result) > 1 else {}
        elif isinstance(result, ScreenId):
            target_id = result
            kwargs = {}
        else:
            return

        # --- Special: SINGLE_SETUP → MAP_BUILDER (stash setup screen) ---
        if (self._active_id == ScreenId.SINGLE_SETUP
                and target_id == ScreenId.MAP_BUILDER):
            self._stashed_setup = self._active_screen
            self._active_screen = MapBuilderScreen()
            self._active_id = ScreenId.MAP_BUILDER
            self._active_screen.on_enter()
            return

        # --- Special: MAP_BUILDER → SINGLE_SETUP (restore stashed) ---
        if (self._active_id == ScreenId.MAP_BUILDER
                and target_id == ScreenId.SINGLE_SETUP):
            self._active_screen.on_exit()
            if self._stashed_setup is not None:
                if "map_data" in kwargs:
                    self._stashed_setup.custom_map_data = kwargs["map_data"]
                self._active_screen = self._stashed_setup
                self._active_id = ScreenId.SINGLE_SETUP
                self._stashed_setup = None
                return
            # Fallback if no stashed screen
            self._navigate(ScreenId.SINGLE_SETUP)
            return

        # --- Special: FILE_SELECT → REPLAY (parse log file) ---
        if (self._active_id == ScreenId.FILE_SELECT
                and target_id == ScreenId.REPLAY):
            filepath = kwargs.get("filepath")
            try:
                from log_replay import LogParser, ReplayEngine
                replay_data = LogParser.parse(filepath)
                engine = ReplayEngine(replay_data)
                self._navigate(
                    ScreenId.REPLAY, engine=engine, filepath=filepath,
                )
            except Exception as e:
                self._active_screen.show_error(str(e))
            return

        # --- Default transition ---
        self._navigate(target_id, **kwargs)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        try:
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
        except Exception:
            self._write_crash_log()
            raise
        finally:
            pygame.quit()

    def _handle_event(self, event):
        result = self._active_screen.handle_event(event)
        if result is not None:
            self._process_transition(result)

    def _update(self):
        self._active_screen.update()

    def _draw(self):
        self.screen_surface.fill(PANEL_BG)
        self._active_screen.draw(self.screen_surface)
        pygame.display.flip()

    def _write_crash_log(self):
        """Write a crash log for unexpected top-level exceptions."""
        crash_tb = tb_module.format_exc()
        crash_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_filename = f"crash_log_{crash_time}.txt"
        try:
            lines = [
                "=" * 60,
                "AI WAREHOUSE GUI - CRASH LOG",
                "=" * 60,
                f"Timestamp: {datetime.now().isoformat()}",
                f"Screen: {self._active_id}",
                "",
                "--- Traceback ---",
                crash_tb,
                "=" * 60,
            ]
            with open(crash_filename, "w") as f:
                f.write("\n".join(lines) + "\n")
            gui_logger.critical(
                "GUI crashed — crash log written to %s", crash_filename,
            )
        except Exception as log_exc:
            import sys
            print(
                f"Failed to write crash log ({log_exc}). "
                f"Original traceback:\n{crash_tb}",
                file=sys.stderr,
            )


# =============================================================================
#                                  Main
# =============================================================================


def main():
    runner = GameRunner()
    runner.run()


if __name__ == "__main__":
    main()
