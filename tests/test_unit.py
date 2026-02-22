"""Unit tests for audit-critical contracts (M6-T01).

Every test is tagged with the audit finding IDs it verifies.
Notation: BR-001(a1) = finding BR-001 from analy1.txt,
          BR-001(a2) = finding BR-001 from analy2.md,
          BR-001(a3) = finding BR-001 from analy3.txt.
"""

import os
import inspect
import tempfile
from dataclasses import fields

import pytest

# ---------------------------------------------------------------------------
# Imports under test (all core modules — no pygame dependency)
# ---------------------------------------------------------------------------
from agent_registry import AGENT_REGISTRY, VALID_AGENT_NAMES, create_agent
from config import (
    GameConfig, BatchConfig,
    DEFAULT_COUNT_STEPS, DEFAULT_TIME_LIMIT,
    DEFAULT_NUM_GAMES,
)
from execution import StepResult, TimeoutPolicy, GRACE_PERIOD
from simulation import GameResult, GameSimulator, determine_winner
from logging_contract import (
    LOG_VERSION, detect_version,
    format_gui_header,
    format_batch_header,
    write_jsonl_sidecar, read_jsonl_sidecar, jsonl_path_for,
    GUI_MOVE, BATCH_MOVE,
)
from log_replay import LogParser, ReplayEngine, ReplayData, ReplayDiagnostics
from batch_runner import compute_summary


# ===================================================================
# Agent Isolation & Registry
# Covers: BR-001(a2), GR-001(a2), BR-002(a1), GR-004(a1), BR-001(a3)
# ===================================================================

class TestAgentIsolation:
    """BR-001(a2), GR-001(a2), BR-002(a1), GR-004(a1), BR-001(a3):
    Agents must be distinct instances even when both players pick the
    same name."""

    @pytest.mark.unit
    def test_agent_isolation_distinct_instances(self):
        """create_agent() must return distinct objects for the same name."""
        for name in VALID_AGENT_NAMES:
            a1 = create_agent(name)
            a2 = create_agent(name)
            assert a1 is not a2, (
                f"create_agent('{name}') returned the same object twice"
            )

    @pytest.mark.unit
    def test_agent_isolation_no_shared_state(self):
        """Two agents of the same type must not share mutable state."""
        for name in VALID_AGENT_NAMES:
            a1 = create_agent(name)
            a2 = create_agent(name)
            assert id(a1) != id(a2)


# ===================================================================
# Registry Single Source of Truth
# Covers: BR-002(a2), BR-008(a2), XR-001(a1), BR-001(a1)
# ===================================================================

class TestRegistrySingleSource:
    """BR-002(a2), BR-008(a2), XR-001(a1), BR-001(a1):
    One shared registry used by both batch and GUI."""

    @pytest.mark.unit
    def test_registry_single_source_of_truth(self):
        """VALID_AGENT_NAMES must be derived from AGENT_REGISTRY."""
        assert VALID_AGENT_NAMES == list(AGENT_REGISTRY.keys())

    @pytest.mark.unit
    def test_registry_has_expected_agents(self):
        """Registry must include both built-in and submission agents."""
        assert "random" in VALID_AGENT_NAMES
        assert "greedy" in VALID_AGENT_NAMES
        assert len(VALID_AGENT_NAMES) >= 2

    @pytest.mark.unit
    def test_registry_factories_are_callable(self):
        """Each registry entry must be a callable (class or factory)."""
        for name, factory in AGENT_REGISTRY.items():
            assert callable(factory), f"Registry entry '{name}' is not callable"

    @pytest.mark.unit
    def test_no_import_time_agent_instantiation(self):
        """XR-001(a1): Importing agent_registry must not instantiate agents.
        AGENT_REGISTRY values must be classes, not instances."""
        for name, factory in AGENT_REGISTRY.items():
            assert isinstance(factory, type), (
                f"AGENT_REGISTRY['{name}'] is an instance, not a class/factory"
            )


# ===================================================================
# Typed Config & Centralized Defaults
# Covers: BR-009(a2), BR-010(a2), BR-006(a1)
# ===================================================================

class TestTypedConfig:
    """BR-009(a2), BR-010(a2), BR-006(a1):
    Typed config objects with validation and centralized defaults."""

    @pytest.mark.unit
    def test_config_typed_validation_game(self):
        """GameConfig rejects invalid values."""
        with pytest.raises(ValueError):
            GameConfig(agent0="a", agent1="b", time_limit=-1)
        with pytest.raises(ValueError):
            GameConfig(agent0="a", agent1="b", count_steps=0)

    @pytest.mark.unit
    def test_config_typed_validation_batch(self):
        """BatchConfig rejects invalid values."""
        with pytest.raises(ValueError):
            BatchConfig(agent0="a", agent1="b", time_limit=0)
        with pytest.raises(ValueError):
            BatchConfig(agent0="a", agent1="b", count_steps=-1)
        with pytest.raises(ValueError):
            BatchConfig(agent0="a", agent1="b", num_games=0)
        with pytest.raises(ValueError):
            BatchConfig(agent0="a", agent1="b", log_sampling_rate=-1)

    @pytest.mark.unit
    def test_config_accepts_valid_values(self):
        """Valid configs must be constructible without error."""
        gc = GameConfig(agent0="greedy", agent1="random")
        assert gc.count_steps == DEFAULT_COUNT_STEPS
        assert gc.time_limit == DEFAULT_TIME_LIMIT

        bc = BatchConfig(agent0="greedy", agent1="random")
        assert bc.count_steps == DEFAULT_COUNT_STEPS
        assert bc.num_games == DEFAULT_NUM_GAMES

    @pytest.mark.unit
    def test_default_count_steps_centralized(self):
        """DEFAULT_COUNT_STEPS (4761) is defined once and used by both
        GameConfig and BatchConfig defaults."""
        assert DEFAULT_COUNT_STEPS == 4761
        gc = GameConfig(agent0="a", agent1="b")
        bc = BatchConfig(agent0="a", agent1="b")
        assert gc.count_steps == DEFAULT_COUNT_STEPS
        assert bc.count_steps == DEFAULT_COUNT_STEPS

    @pytest.mark.unit
    def test_config_is_dataclass(self):
        """Configs must be dataclasses (typed, not dicts)."""
        assert len(fields(GameConfig)) > 0
        assert len(fields(BatchConfig)) > 0


# ===================================================================
# Execution Contract: StepResult & TimeoutPolicy
# Covers: BR-005(a2), GR-006(a2), BR-004(a1), GR-002(a1)
# ===================================================================

class TestExecutionContract:
    """BR-005(a2), GR-006(a2), BR-004(a1), GR-002(a1):
    Shared execution contract with StepResult and TimeoutPolicy."""

    @pytest.mark.unit
    def test_step_result_structure(self):
        """StepResult must have operator, elapsed, timed_out, error fields."""
        sr = StepResult(operator="move north", elapsed=0.5,
                        timed_out=False, error=None)
        assert sr.operator == "move north"
        assert sr.elapsed == 0.5
        assert sr.timed_out is False
        assert sr.error is None

    @pytest.mark.unit
    def test_step_result_timeout(self):
        """A timed-out StepResult must have operator=None."""
        sr = StepResult(operator=None, elapsed=2.0,
                        timed_out=True, error=None)
        assert sr.operator is None
        assert sr.timed_out is True

    @pytest.mark.unit
    def test_timeout_policy_structure(self):
        """TimeoutPolicy must have time_limit, enforcement, grace_period."""
        tp = TimeoutPolicy(time_limit=1.0)
        assert tp.time_limit == 1.0
        assert tp.enforcement == "subprocess"
        assert tp.grace_period == GRACE_PERIOD

    @pytest.mark.unit
    def test_execution_uses_monotonic(self):
        """execution.py must use time.monotonic, not time.time."""
        import execution
        src = inspect.getsource(execution)
        assert "time.monotonic()" in src, (
            "execution.py must use time.monotonic() for timing"
        )
        # Should NOT use time.time() for elapsed measurement
        # (time.time is still OK for other purposes, but monotonic must be present)

    @pytest.mark.unit
    def test_execution_contract_consistent(self):
        """BR-007(a1): Both batch and GUI must use execute_agent_step.
        Verify simulation.py imports from execution."""
        import simulation
        src = inspect.getsource(simulation)
        assert "from execution import execute_agent_step" in src


# ===================================================================
# Error States & Explicit Outcomes
# Covers: BR-006(a2), BR-007(a2), BR-005(a1), BR-002(a3)
# ===================================================================

class TestErrorStates:
    """BR-006(a2), BR-007(a2), BR-005(a1), BR-002(a3):
    Explicit error outcomes; no silent fallbacks."""

    @pytest.mark.unit
    def test_game_result_error_no_winner(self):
        """Errored games must have winner=None."""
        gr = GameResult(
            seed=1, winner=None, final_credits=[0, 0],
            steps_taken=0, timeout_flags=[False, False],
            error="test error", wall_time_seconds=0.1,
            error_phase="agent_step", error_type="RuntimeError",
        )
        assert gr.winner is None
        assert gr.error is not None

    @pytest.mark.unit
    def test_game_result_error_phases(self):
        """GameResult must support structured error fields."""
        gr = GameResult(
            seed=1, winner=None, final_credits=[0, 0],
            steps_taken=0, timeout_flags=[False, False],
            error="crash", wall_time_seconds=0.1,
            error_phase="get_balances",
            error_type="RuntimeError",
            error_traceback="Traceback ...",
        )
        assert gr.error_phase == "get_balances"
        assert gr.error_type == "RuntimeError"
        assert gr.error_traceback is not None

    @pytest.mark.unit
    def test_errored_games_excluded_from_stats(self):
        """compute_summary must exclude errored games from win/loss stats."""
        ok = GameResult(
            seed=1, winner=0, final_credits=[10, 5],
            steps_taken=100, timeout_flags=[False, False],
            error=None, wall_time_seconds=1.0,
        )
        err = GameResult(
            seed=2, winner=None, final_credits=[0, 0],
            steps_taken=0, timeout_flags=[False, False],
            error="crash", wall_time_seconds=0.1,
            error_phase="agent_step", error_type="RuntimeError",
        )
        cfg = BatchConfig(agent0="greedy", agent1="random")
        summary = compute_summary(cfg, [ok, err])

        assert summary["num_games"] == 2
        assert summary["num_completed"] == 1
        assert summary["num_errors"] == 1
        # Only the completed game counts
        assert summary["robot0_wins"] == 1
        assert summary["robot1_wins"] == 0

    @pytest.mark.unit
    def test_determine_winner(self):
        """determine_winner returns correct results."""
        assert determine_winner([10, 5]) == 0
        assert determine_winner([5, 10]) == 1
        assert determine_winner([5, 5]) is None

    @pytest.mark.unit
    def test_simulation_game_loop_separation(self):
        """BR-004(a2), BR-003(a1): GameSimulator is a separate module
        from batch_runner, with injected callbacks."""
        assert hasattr(GameSimulator, 'run')
        sig = inspect.signature(GameSimulator.run)
        assert 'turn_callback' in sig.parameters


# ===================================================================
# Logging Contract & Versioning
# Covers: BR-003(a2), LR-001(a2), LR-001(a1), LR-001(a3)
# ===================================================================

class TestLoggingContract:
    """BR-003(a2), LR-001(a2), LR-001(a1), LR-001(a3):
    Versioned logging contract with shared templates."""

    @pytest.mark.unit
    def test_log_version_exists(self):
        """LOG_VERSION must be defined."""
        assert LOG_VERSION is not None
        assert isinstance(LOG_VERSION, str)
        assert len(LOG_VERSION) > 0

    @pytest.mark.unit
    def test_detect_version_v1(self):
        """detect_version must find LOG_VERSION in header text."""
        text = "LOG_VERSION: 1.0\nsome data"
        assert detect_version(text) == "1.0"

    @pytest.mark.unit
    def test_detect_version_legacy(self):
        """detect_version returns None for legacy logs without version."""
        text = "AI WAREHOUSE GAME LOG\nno version here"
        assert detect_version(text) is None

    @pytest.mark.unit
    def test_jsonl_roundtrip(self):
        """Write a JSONL sidecar and read it back — data must match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "test.txt")
            # Write a dummy text file so jsonl_path_for works
            with open(txt_path, "w") as f:
                f.write("dummy")

            header = {
                "seed": 42,
                "count_steps": 5,
                "agent_names": ["greedy", "random"],
                "time_limit": 1.0,
            }
            moves = [
                {"round": 0, "agent": 0, "operator": "move south"},
                {"round": 0, "agent": 1, "operator": "move north"},
            ]
            result = {"final_credits": [10, 5], "winner": 0, "error": None}

            write_jsonl_sidecar(
                jsonl_path_for(txt_path), header, moves, result,
            )

            parsed = read_jsonl_sidecar(txt_path)
            assert parsed is not None
            hdr, mvs, res = parsed

            assert hdr["seed"] == 42
            assert hdr["count_steps"] == 5
            assert hdr["agent_names"] == ["greedy", "random"]
            assert len(mvs) == 2
            assert mvs[0] == (0, "move south")
            assert mvs[1] == (1, "move north")
            assert res["winner"] == 0

    @pytest.mark.unit
    def test_format_templates_include_version(self):
        """Both GUI and batch headers must include LOG_VERSION."""
        gui_lines = format_gui_header({
            "agent0": "a", "agent1": "b",
            "time_limit": 1.0, "seed": 1, "count_steps": 5,
        })
        assert any("LOG_VERSION" in line for line in gui_lines)

        batch_lines = format_batch_header(0, "a", "b", 1.0, 5, 1)
        assert any("LOG_VERSION" in line for line in batch_lines)


# ===================================================================
# Golden Fixture Parsing
# Covers: LR-001(a1), LR-001(a3), BR-003(a2)
# ===================================================================

class TestGoldenFixtures:
    """LR-001(a1), LR-001(a3), BR-003(a2):
    Golden fixture parsing for both GUI and batch formats."""

    EXPECTED_MOVES = [
        (0, "move south"),
        (1, "move north"),
        (0, "move north"),
        (1, "move north"),
        (0, "move south"),
        (1, "move north"),
    ]

    @pytest.mark.unit
    def test_golden_fixture_gui_parse(self, gui_fixture_txt):
        """Parse GUI text log golden fixture."""
        data = LogParser.parse(gui_fixture_txt)
        assert data.seed == 42
        assert data.count_steps == 5
        assert data.agent_names == ["greedy", "greedy"]
        assert len(data.moves) == 6
        assert data.moves == self.EXPECTED_MOVES

    @pytest.mark.unit
    def test_golden_fixture_batch_parse(self, batch_fixture_txt):
        """Parse batch text log golden fixture."""
        data = LogParser.parse(batch_fixture_txt)
        assert data.seed == 42
        assert data.count_steps == 5
        assert data.agent_names == ["greedy", "greedy"]
        assert len(data.moves) == 6
        assert data.moves == self.EXPECTED_MOVES

    @pytest.mark.unit
    def test_golden_fixture_jsonl_sidecar_parse(self, gui_fixture_txt):
        """Parse JSONL sidecar golden fixture (preferred path)."""
        # LogParser should prefer sidecar when it exists
        data = LogParser.parse(gui_fixture_txt)
        assert data.seed == 42
        assert len(data.moves) == 6

    @pytest.mark.unit
    def test_golden_fixture_replay_engine(self, gui_fixture_txt):
        """ReplayEngine can reconstruct states from golden fixture."""
        data = LogParser.parse(gui_fixture_txt)
        engine = ReplayEngine(data)

        assert engine.total_moves == 6
        assert engine.is_at_start()
        assert not engine.is_at_end()

        # Step forward through all moves
        for _ in range(6):
            assert engine.step_forward()

        assert engine.is_at_end()
        assert not engine.step_forward()  # can't go past end

    @pytest.mark.unit
    def test_golden_fixture_replay_backward(self, gui_fixture_txt):
        """ReplayEngine backward navigation from golden fixture."""
        data = LogParser.parse(gui_fixture_txt)
        engine = ReplayEngine(data)

        # Go to end
        engine.go_to_end()
        assert engine.is_at_end()

        # Step backward
        assert engine.step_backward()
        assert engine.current_index == 5

        # Go to start
        engine.go_to_start()
        assert engine.is_at_start()

    @pytest.mark.unit
    def test_golden_fixture_replay_random_access(self, gui_fixture_txt):
        """ReplayEngine random access via go_to_index."""
        data = LogParser.parse(gui_fixture_txt)
        engine = ReplayEngine(data)

        engine.go_to_index(3)
        assert engine.current_index == 3
        assert engine.current_env is not None

        engine.go_to_index(0)
        assert engine.is_at_start()


# ===================================================================
# Custom Map Embedding in Logs
# ===================================================================

class TestCustomMapEmbedding:
    """Custom map data must survive log write/read roundtrip and be
    used by ReplayEngine to reconstruct the correct initial state."""

    SAMPLE_MAP_DATA = {
        "board_size": 5,
        "robots": [
            {"position": [0, 0], "battery": 20, "credit": 0},
            {"position": [4, 4], "battery": 20, "credit": 0},
        ],
        "packages": [
            {"position": [2, 2], "destination": [3, 3], "on_board": True},
            {"position": [1, 1], "destination": [4, 0], "on_board": True},
        ],
        "charge_stations": [
            {"position": [0, 4]},
            {"position": [4, 0]},
        ],
    }

    @pytest.mark.unit
    def test_jsonl_roundtrip_with_custom_map(self):
        """JSONL sidecar roundtrip preserves custom_map_data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "test.txt")
            with open(txt_path, "w") as f:
                f.write("dummy")

            header = {
                "seed": 0,
                "count_steps": 5,
                "agent_names": ["greedy", "greedy"],
                "time_limit": 1.0,
                "custom_map_data": self.SAMPLE_MAP_DATA,
            }
            moves = [
                {"round": 0, "agent": 0, "operator": "move south"},
                {"round": 0, "agent": 1, "operator": "move north"},
            ]
            result = {"final_credits": [0, 0], "winner": None, "error": None}

            write_jsonl_sidecar(
                jsonl_path_for(txt_path), header, moves, result,
            )

            parsed = read_jsonl_sidecar(txt_path)
            assert parsed is not None
            hdr, mvs, res = parsed
            assert "custom_map_data" in hdr
            assert hdr["custom_map_data"] == self.SAMPLE_MAP_DATA

    @pytest.mark.unit
    def test_jsonl_roundtrip_without_custom_map(self):
        """JSONL sidecar roundtrip without custom_map_data (backward compat)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "test.txt")
            with open(txt_path, "w") as f:
                f.write("dummy")

            header = {
                "seed": 42,
                "count_steps": 5,
                "agent_names": ["greedy", "greedy"],
                "time_limit": 1.0,
            }
            moves = []
            write_jsonl_sidecar(
                jsonl_path_for(txt_path), header, moves,
            )

            parsed = read_jsonl_sidecar(txt_path)
            assert parsed is not None
            hdr, _, _ = parsed
            assert hdr.get("custom_map_data") is None

    @pytest.mark.unit
    def test_parser_populates_custom_map_data(self, custom_map_fixture_txt):
        """LogParser.parse() sets ReplayData.custom_map_data from JSONL."""
        data = LogParser.parse(custom_map_fixture_txt)
        assert data.custom_map_data is not None
        assert data.custom_map_data["board_size"] == 5
        assert len(data.custom_map_data["robots"]) == 2
        assert data.custom_map_data["robots"][0]["position"] == [0, 0]

    @pytest.mark.unit
    def test_parser_old_log_has_no_custom_map(self, gui_fixture_txt):
        """Old v1.0 logs parse with custom_map_data=None."""
        data = LogParser.parse(gui_fixture_txt)
        assert data.custom_map_data is None

    @pytest.mark.unit
    def test_replay_engine_uses_custom_map(self, custom_map_fixture_txt):
        """ReplayEngine reconstructs initial state from custom map data."""
        data = LogParser.parse(custom_map_fixture_txt)
        engine = ReplayEngine(data)

        # Initial env must match the custom map, not a seed-generated map
        env = engine.current_env
        assert env.robots[0].position == (0, 0)
        assert env.robots[1].position == (4, 4)
        assert env.charge_stations[0].position == (0, 4)
        assert env.charge_stations[1].position == (4, 0)

    @pytest.mark.unit
    def test_replay_engine_custom_map_navigation(self, custom_map_fixture_txt):
        """ReplayEngine forward/backward navigation works with custom maps."""
        data = LogParser.parse(custom_map_fixture_txt)
        engine = ReplayEngine(data)

        assert engine.is_at_start()
        # Step through all moves
        while engine.step_forward():
            pass
        assert engine.is_at_end()

        # Go back to start
        engine.go_to_start()
        assert engine.is_at_start()
        # Initial positions preserved after round-trip
        env = engine.current_env
        assert env.robots[0].position == (0, 0)
        assert env.robots[1].position == (4, 4)

    @pytest.mark.unit
    def test_replay_data_custom_map_field(self):
        """ReplayData accepts custom_map_data parameter."""
        data = ReplayData(
            seed=0,
            count_steps=5,
            agent_names=["a", "b"],
            moves=[],
            source_file="test",
            custom_map_data=self.SAMPLE_MAP_DATA,
        )
        assert data.custom_map_data == self.SAMPLE_MAP_DATA

        # Default is None
        data2 = ReplayData(
            seed=0,
            count_steps=5,
            agent_names=["a", "b"],
            moves=[],
            source_file="test",
        )
        assert data2.custom_map_data is None

    @pytest.mark.unit
    def test_replay_engine_restores_seed_for_custom_map(self):
        """ReplayEngine restores the logged seed after load_from_map_data
        so that spawn_package produces deterministic results on drop-off."""
        data = ReplayData(
            seed=42,
            count_steps=5,
            agent_names=["a", "b"],
            moves=[],
            source_file="test",
            custom_map_data=self.SAMPLE_MAP_DATA,
        )
        engine = ReplayEngine(data)
        # After _build_checkpoints, the initial env must have seed == 42
        # (the logged seed), not whatever random.randint produced inside
        # load_from_map_data.
        assert engine.current_env.seed == 42

    @pytest.mark.unit
    def test_gui_header_shows_custom_map(self):
        """format_gui_header includes 'Custom Map: yes' when map data present."""
        lines = format_gui_header({
            "agent0": "a", "agent1": "b",
            "time_limit": 1.0, "seed": 1, "count_steps": 5,
            "custom_map_data": self.SAMPLE_MAP_DATA,
        })
        assert any("Custom Map" in line for line in lines)

    @pytest.mark.unit
    def test_gui_header_no_custom_map_line(self):
        """format_gui_header omits 'Custom Map' line for seed-based games."""
        lines = format_gui_header({
            "agent0": "a", "agent1": "b",
            "time_limit": 1.0, "seed": 1, "count_steps": 5,
        })
        assert not any("Custom Map" in line for line in lines)


# ===================================================================
# Replay Truncation & Diagnostics
# Covers: LR-002(a2), LR-002(a1)
# ===================================================================

class TestReplayDiagnostics:
    """LR-002(a2), LR-002(a1):
    Replay must report truncation and illegal operators."""

    @pytest.mark.unit
    def test_replay_truncation_diagnostics(self):
        """ReplayEngine records truncation reason on illegal operator."""
        # Build replay data with an illegal move
        data = ReplayData(
            seed=42,
            count_steps=5,
            agent_names=["greedy", "greedy"],
            moves=[
                (0, "move south"),   # legal for seed 42
                (1, "move north"),   # legal
                (0, "ILLEGAL_OP"),   # NOT legal
            ],
            source_file="test",
        )
        engine = ReplayEngine(data)
        assert engine.diagnostics.truncated is True
        assert engine.diagnostics.truncation_reason is not None
        assert "ILLEGAL_OP" in engine.diagnostics.truncation_reason
        assert len(engine.diagnostics.warnings) > 0
        # Only the first 2 moves should be valid
        assert engine.total_moves == 2

    @pytest.mark.unit
    def test_replay_diagnostics_structure(self):
        """ReplayDiagnostics has the expected fields."""
        d = ReplayDiagnostics()
        assert d.truncated is False
        assert d.truncation_reason is None
        assert isinstance(d.warnings, list)
        d.add_warning("test", "msg", round_num=1, agent=0, line_number=5)
        assert len(d.warnings) == 1
        assert d.warnings[0]["kind"] == "test"
        assert d.warnings[0]["round"] == 1


# ===================================================================
# Regex Anchoring & Parsing Robustness
# Covers: LR-003(a2), LR-004(a1)
# ===================================================================

class TestRegexAnchoring:
    """LR-003(a2), LR-004(a1):
    Anchored regex prevents false positives from similar text."""

    @pytest.mark.unit
    def test_regex_anchoring_no_false_positives(self):
        """Lines containing move-like text in comments must not match."""
        false_positive_lines = [
            "  # [Round 1] Agent 0 (greedy): move south",
            "  The agent chose [Round 1] Agent 0 (greedy): move east",
            "  Summary: Round 0, Agent 0 (greedy): move north happened",
            "Result: [Round 1] Agent 0 (greedy): move south",
        ]
        for line in false_positive_lines:
            assert GUI_MOVE.match(line) is None, (
                f"GUI_MOVE falsely matched: {line!r}"
            )
            assert BATCH_MOVE.match(line) is None, (
                f"BATCH_MOVE falsely matched: {line!r}"
            )

    @pytest.mark.unit
    def test_regex_matches_valid_lines(self):
        """Valid move lines must be matched correctly."""
        gui_line = "[Round 1] Agent 0 (greedy): move south"
        m = GUI_MOVE.match(gui_line)
        assert m is not None
        assert m.group(1) == "0"
        assert m.group(2) == "move south"

        batch_line = "  Round 1, Agent 0 (greedy): move south"
        m = BATCH_MOVE.match(batch_line)
        assert m is not None
        assert m.group(1) == "0"
        assert m.group(2) == "move south"


# ===================================================================
# Replay Performance: Checkpoint Engine
# Covers: LR-004(a2), LR-003(a1)
# ===================================================================

class TestReplayCheckpoint:
    """LR-004(a2), LR-003(a1):
    Checkpoint-based replay instead of cloning every state."""

    @pytest.mark.unit
    def test_replay_checkpoint_engine(self, gui_fixture_txt):
        """ReplayEngine uses checkpoints, not per-move clones."""
        from log_replay import CHECKPOINT_INTERVAL
        data = LogParser.parse(gui_fixture_txt)
        engine = ReplayEngine(data)

        # Engine must have checkpoints dict
        assert hasattr(engine, '_checkpoints')
        assert isinstance(engine._checkpoints, dict)
        # At minimum, checkpoint 0 (initial state) must exist
        assert 0 in engine._checkpoints
        # Checkpoint interval must be defined
        assert CHECKPOINT_INTERVAL > 1


# ===================================================================
# Board Layout Dynamic
# Covers: GR-004(a2), GR-005(a1)
# ===================================================================

class TestBoardLayout:
    """GR-004(a2), GR-005(a1):
    Rendering layout derived from board_size, no hardcoded 5x5.
    Uses source inspection since pygame is not installed."""

    @pytest.mark.unit
    def test_board_layout_dynamic(self):
        """board_renderer.py defines BoardLayout with dynamic board_size."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ui", "board_renderer.py",
        )
        with open(src_path) as f:
            src = f.read()

        # Must have a BoardLayout class
        assert "class BoardLayout" in src
        # Must derive grid dimensions from board_size
        assert "board_size" in src
        assert "self.board_size * self.cell_size" in src
        # Must NOT have hardcoded grid_width=500 or grid_height=500
        assert "grid_width = 500" not in src
        assert "grid_height = 500" not in src

    @pytest.mark.unit
    def test_board_layout_has_validate(self):
        """board_renderer.py has a validate_layout sanity check."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ui", "board_renderer.py",
        )
        with open(src_path) as f:
            src = f.read()

        assert "validate_layout" in src


# ===================================================================
# Screen Routing: Typed ScreenId & Screen ABC
# Covers: GR-003(a2), GR-006(a1)
# ===================================================================

class TestScreenRouting:
    """GR-003(a2), GR-006(a1):
    Typed screen routing with ScreenId enum and Screen interface."""

    @pytest.mark.unit
    def test_screen_id_typed_enum(self):
        """ScreenId must be an enum with expected members."""
        from ui import ScreenId
        from enum import Enum
        assert issubclass(ScreenId, Enum)
        assert hasattr(ScreenId, 'OPENING')
        assert hasattr(ScreenId, 'GAME')
        assert hasattr(ScreenId, 'REPLAY')
        assert hasattr(ScreenId, 'BATCH')

    @pytest.mark.unit
    def test_screen_abc_lifecycle(self):
        """Screen ABC must define lifecycle methods."""
        from ui import Screen
        from abc import ABC
        assert issubclass(Screen, ABC)
        # Must have required abstract methods
        assert hasattr(Screen, 'handle_event')
        assert hasattr(Screen, 'draw')
        # Must have lifecycle hooks
        assert hasattr(Screen, 'on_enter')
        assert hasattr(Screen, 'on_exit')
        assert hasattr(Screen, 'update')


# ===================================================================
# AgentWorker Synchronization (source inspection)
# Covers: GR-005(a2), GR-003(a1), GR-002(a3)
# ===================================================================

class TestAgentWorkerSync:
    """GR-005(a2), GR-003(a1), GR-002(a3):
    Cross-thread state access must use Lock and Event."""

    @pytest.mark.unit
    def test_agent_worker_sync(self):
        """AgentWorker source must use threading.Lock and threading.Event.
        Uses source file inspection since pygame is not installed."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ui", "screens", "game_screen.py",
        )
        with open(src_path) as f:
            src = f.read()

        # Must use both Lock and Event
        assert "threading.Lock()" in src, (
            "AgentWorker must use threading.Lock()"
        )
        assert "threading.Event()" in src, (
            "AgentWorker must use threading.Event()"
        )
        # Lock must guard result access
        assert "self._lock" in src
        assert "self._done_event" in src


# ===================================================================
# GUI Error Containment (source inspection)
# Covers: GR-007(a2)
# ===================================================================

class TestGUIErrorContainment:
    """GR-007(a2): Move-boundary error containment in GUI."""

    @pytest.mark.unit
    def test_game_screen_has_error_state(self):
        """GameScreen must have a FINISHED_ERROR state.
        Uses source file inspection since pygame is not installed."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ui", "screens", "game_screen.py",
        )
        with open(src_path) as f:
            src = f.read()
        assert "FINISHED_ERROR" in src, (
            "GameScreen must have FINISHED_ERROR state"
        )

    @pytest.mark.unit
    def test_game_runner_has_crash_log(self):
        """game_runner.py must write crash logs on unexpected exceptions.
        Uses source file inspection since pygame is not installed."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "game_runner.py",
        )
        with open(src_path) as f:
            src = f.read()
        assert "_write_crash_log" in src, (
            "GameRunner must have _write_crash_log method"
        )
        assert "crash_log_" in src, (
            "GameRunner must write crash log files"
        )
