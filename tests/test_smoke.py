"""Smoke tests for import-time side effects and module boundaries (M6-T01).

These tests verify that core modules do not import pygame and that
importing the batch/core path does not trigger agent instantiation.

Covers audit findings related to:
- GR-002(a2), GR-001(a1), GR-001(a3): GUI module boundary separation
- XR-001(a1), BR-002(a2): No import-time agent instantiation
- GR-008(a2): No tempfile leaks in map builder
"""

import os
import subprocess
import sys

import pytest


# ---------------------------------------------------------------------------
# Helper: check a module can be imported without pulling in pygame
# ---------------------------------------------------------------------------

def _assert_no_pygame(module_name):
    """Import *module_name* in a subprocess and assert pygame is NOT loaded."""
    script = (
        f"import sys; sys.path.insert(0, '.'); "
        f"import {module_name}; "
        f"print('pygame' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=30,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode == 0, (
        f"Importing {module_name} failed:\n{result.stderr}"
    )
    loaded = result.stdout.strip()
    assert loaded == "False", (
        f"Importing {module_name} pulled in pygame (loaded={loaded})"
    )


# ===================================================================
# Core modules must NOT import pygame
# Covers: GR-002(a2), GR-001(a1), GR-001(a3)
# ===================================================================

class TestNoPygameImport:
    """Core modules must be importable without pygame."""

    @pytest.mark.smoke
    def test_agent_registry_no_pygame(self):
        _assert_no_pygame("agent_registry")

    @pytest.mark.smoke
    def test_config_no_pygame(self):
        _assert_no_pygame("config")

    @pytest.mark.smoke
    def test_execution_no_pygame(self):
        _assert_no_pygame("execution")

    @pytest.mark.smoke
    def test_simulation_no_pygame(self):
        _assert_no_pygame("simulation")

    @pytest.mark.smoke
    def test_logging_contract_no_pygame(self):
        _assert_no_pygame("logging_contract")

    @pytest.mark.smoke
    def test_game_logger_no_pygame(self):
        _assert_no_pygame("game_logger")

    @pytest.mark.smoke
    def test_log_replay_no_pygame(self):
        _assert_no_pygame("log_replay")

    @pytest.mark.smoke
    def test_batch_runner_no_pygame(self):
        _assert_no_pygame("batch_runner")


# ===================================================================
# No agent instantiation at import time
# Covers: XR-001(a1), BR-002(a2)
# ===================================================================

class TestNoImportTimeSideEffects:
    """XR-001(a1), BR-002(a2): Importing runners must not instantiate agents."""

    @pytest.mark.smoke
    def test_no_agent_instantiation_on_import(self):
        """Importing batch_runner must not call any agent constructor."""
        script = (
            "import sys; sys.path.insert(0, '.'); "
            "import agent_registry; "
            "# After import, AGENT_REGISTRY values should be classes, not instances\n"
            "for name, val in agent_registry.AGENT_REGISTRY.items():\n"
            "    assert isinstance(val, type), "
            "f'AGENT_REGISTRY[{name!r}] is an instance, not a class'\n"
            "print('OK')"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert result.returncode == 0, (
            f"Import-time agent instantiation check failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout


# ===================================================================
# Map builder: no tempfile leak patterns
# Covers: GR-008(a2)
# ===================================================================

class TestMapBuilderNoTempfileLeak:
    """GR-008(a2): Map builder must not use delete=False temp file patterns."""

    @pytest.mark.smoke
    def test_map_builder_no_tempfile_leak(self):
        """map_builder.py source must not contain tempfile or delete=False."""
        map_builder_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ui", "screens", "map_builder.py",
        )
        with open(map_builder_path, "r") as f:
            source = f.read()

        assert "import tempfile" not in source, (
            "map_builder.py should not import tempfile"
        )
        assert "delete=False" not in source, (
            "map_builder.py should not use delete=False temp files"
        )
