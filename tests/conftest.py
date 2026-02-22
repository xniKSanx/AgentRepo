"""Shared test configuration and fixtures for the AI Warehouse test suite."""

import os
import sys

import pytest

# Ensure project root is importable
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def gui_fixture_txt():
    return os.path.join(FIXTURES_DIR, "gui_game.txt")


@pytest.fixture
def gui_fixture_jsonl():
    return os.path.join(FIXTURES_DIR, "gui_game.jsonl")


@pytest.fixture
def batch_fixture_txt():
    return os.path.join(FIXTURES_DIR, "batch_game.txt")


@pytest.fixture
def batch_fixture_jsonl():
    return os.path.join(FIXTURES_DIR, "batch_game.jsonl")


@pytest.fixture
def custom_map_fixture_txt():
    return os.path.join(FIXTURES_DIR, "custom_map_game.txt")
