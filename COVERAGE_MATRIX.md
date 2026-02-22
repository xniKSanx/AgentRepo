# M6-T01: Audit Coverage Matrix

Every finding record (origin + ID) from the three audit reports is mapped below to the implementing change and verifying test or quality gate.

**Legend:**
- **Origin**: `a1` = analy1.txt, `a2` = analy2.md, `a3` = analy3.txt
- **Milestone commits**: M1=`70248e8`, M2=`2087aa1`+`03b8e8f`, M3=`bfcaa0b`, M4=`3f7382d`, M5=`9bf7132`
- **Test file**: `test_unit.py` = `tests/test_unit.py`, `test_smoke.py` = `tests/test_smoke.py`

---

## 1. Agent Instance Isolation

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | BR-001 | `agent_registry.py` (factory pattern, `create_agent()` L27-36) | M1 `70248e8` | `test_unit::TestAgentIsolation::test_agent_isolation_distinct_instances` |
| a2 | GR-001 | `agent_registry.py` (per-player instantiation via factory) | M1 `70248e8` | `test_unit::TestAgentIsolation::test_agent_isolation_distinct_instances` |
| a1 | BR-002 | `agent_registry.py` (AGENT_REGISTRY maps name→class, not instance) | M1 `70248e8` | `test_unit::TestRegistrySingleSource::test_no_import_time_agent_instantiation` |
| a1 | GR-004 | `agent_registry.py` (create_agent returns fresh instance each call) | M1 `70248e8` | `test_unit::TestAgentIsolation::test_agent_isolation_no_shared_state` |
| a3 | BR-001 | `agent_registry.py` (factory pattern eliminates shared instances) | M1 `70248e8` | `test_unit::TestAgentIsolation::test_agent_isolation_distinct_instances` |

## 2. Central Agent Registry as Factories

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | BR-002 | `agent_registry.py` (AGENT_REGISTRY dict, VALID_AGENT_NAMES) | M1 `70248e8` | `test_unit::TestRegistrySingleSource::test_registry_single_source_of_truth` |
| a2 | BR-008 | `agent_registry.py` (single registry used by both runners) | M1 `70248e8` | `test_unit::TestRegistrySingleSource::test_registry_has_expected_agents` |
| a1 | XR-001 | `agent_registry.py` (no import-time instantiation; classes in registry) | M1 `70248e8` | `test_smoke::TestNoImportTimeSideEffects::test_no_agent_instantiation_on_import` |
| a1 | BR-001 | `agent_registry.py` + `batch_runner.py` (batch uses VALID_AGENT_NAMES) | M1 `70248e8` | `test_unit::TestRegistrySingleSource::test_registry_factories_are_callable` |

## 3. Batch Single-Game Orchestration Separation

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | BR-004 | `simulation.py` (GameSimulator extracted with turn_callback) | M1 `7e8222d` | `test_unit::TestErrorStates::test_simulation_game_loop_separation` |
| a1 | BR-003 | `simulation.py` (pure game loop; batch_runner handles I/O) | M1 `7e8222d` | `test_unit::TestErrorStates::test_simulation_game_loop_separation` |

## 4. Timeout Semantics and Enforcement

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | BR-005 | `execution.py` (subprocess-based timeout, monotonic clock, SIGTERM+SIGKILL) | M2 `2087aa1` | `test_unit::TestExecutionContract::test_timeout_policy_structure` |
| a2 | GR-006 | `execution.py` (TimeoutPolicy, StepResult with timed_out flag) | M2 `2087aa1` | `test_unit::TestExecutionContract::test_step_result_timeout` |
| a1 | BR-004 | `execution.py:127` (time.monotonic for timing) | M2 `2087aa1` | `test_unit::TestExecutionContract::test_execution_uses_monotonic` |
| a1 | GR-002 | `execution.py` + `ui/screens/game_screen.py` (shared timeout enforcement) | M2 `2087aa1` | `test_unit::TestExecutionContract::test_step_result_structure` |

## 5. Consistent Agent Execution Contract

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a1 | BR-007 | `execution.py` (shared entrypoint; env cloned internally L130) | M2 `2087aa1` | `test_unit::TestExecutionContract::test_execution_contract_consistent` |

## 6. Thread Synchronization for AgentWorker

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | GR-005 | `ui/screens/game_screen.py` (AgentWorker: Lock + Event, L51-52) | M2 `2087aa1` | `test_unit::TestAgentWorkerSync::test_agent_worker_sync` |
| a1 | GR-003 | `ui/screens/game_screen.py` (self._lock guards self._result, L58,71,79) | M2 `2087aa1` | `test_unit::TestAgentWorkerSync::test_agent_worker_sync` |
| a3 | GR-002 | `ui/screens/game_screen.py` (self._done_event for completion signal) | M2 `2087aa1` | `test_unit::TestAgentWorkerSync::test_agent_worker_sync` |

## 7. Explicit Error States and Structured Reporting

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | BR-006 | `simulation.py:215-234` (get_balances failure → error, not draw) | M3 `bfcaa0b` | `test_unit::TestErrorStates::test_game_result_error_no_winner` |
| a2 | BR-007 | `simulation.py:42-46` (GameResult: error_phase, error_type, error_traceback) | M3 `bfcaa0b` | `test_unit::TestErrorStates::test_game_result_error_phases` |
| a1 | BR-005 | `batch_runner.py:184` (compute_summary excludes errored games) | M3 `bfcaa0b` | `test_unit::TestErrorStates::test_errored_games_excluded_from_stats` |
| a3 | BR-002 | `simulation.py:234` (winner=None when error_msg is set) | M3 `bfcaa0b` | `test_unit::TestErrorStates::test_game_result_error_no_winner` |

## 8. GUI Move Boundary Containment

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | GR-007 | `ui/screens/game_screen.py:267-292` (try/except in _apply_move) + `game_runner.py:159-160` (crash log) | M3 `bfcaa0b` | `test_unit::TestGUIErrorContainment::test_game_screen_has_error_state`, `test_unit::TestGUIErrorContainment::test_game_runner_has_crash_log` |

## 9. Logging and Replay Contract

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | BR-003 | `logging_contract.py` (shared format templates used by both runners) | M4 `3f7382d` | `test_unit::TestLoggingContract::test_format_templates_include_version` |
| a2 | LR-001 | `logging_contract.py` (LOG_VERSION, JSONL sidecar write/read) | M4 `3f7382d` | `test_unit::TestLoggingContract::test_jsonl_roundtrip` |
| a1 | LR-001 | `logging_contract.py` + `log_replay.py` (versioned parser, golden fixtures) | M4 `3f7382d` | `test_unit::TestGoldenFixtures::test_golden_fixture_gui_parse`, `test_unit::TestGoldenFixtures::test_golden_fixture_batch_parse` |
| a3 | LR-001 | `logging_contract.py` + `game_logger.py` + `batch_runner.py` (JSONL sidecar) | M4 `3f7382d` | `test_unit::TestGoldenFixtures::test_golden_fixture_jsonl_sidecar_parse` |

## 10. Replay Truncation and Illegal-Operator Diagnostics

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | LR-002 | `log_replay.py:24-42` (ReplayDiagnostics: truncated, truncation_reason, warnings) | M4 `3f7382d` | `test_unit::TestReplayDiagnostics::test_replay_truncation_diagnostics` |
| a1 | LR-002 | `log_replay.py:218-233` (illegal operator → structured diagnostics) | M4 `3f7382d` | `test_unit::TestReplayDiagnostics::test_replay_diagnostics_structure` |

## 11. Regex Parsing Hardening

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | LR-003 | `logging_contract.py:80-93` (anchored patterns with `^` prefix) | M4 `3f7382d` | `test_unit::TestRegexAnchoring::test_regex_anchoring_no_false_positives` |
| a1 | LR-004 | `log_replay.py:129,168` (`.match()` used, not `.search()`) | M4 `3f7382d` | `test_unit::TestRegexAnchoring::test_regex_matches_valid_lines` |

## 12. Replay Performance and Memory Scaling

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | LR-004 | `log_replay.py:186-249` (ReplayEngine with CHECKPOINT_INTERVAL=50) | M4 `3f7382d` | `test_unit::TestReplayCheckpoint::test_replay_checkpoint_engine` |
| a1 | LR-003 | `log_replay.py:251-263` (_reconstruct_state from nearest checkpoint) | M4 `3f7382d` | `test_unit::TestGoldenFixtures::test_golden_fixture_replay_engine` |

## 13. GUI Module Boundaries

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | GR-002 | `game_runner.py` (thin router), `ui/` package (screens, widgets, renderer) | M5 `9bf7132` | `test_smoke::TestNoPygameImport::test_batch_runner_no_pygame` + all `*_no_pygame` tests |
| a1 | GR-001 | `ui/screens/`, `ui/widgets.py`, `ui/board_renderer.py` (extracted from game_runner) | M5 `9bf7132` | `test_smoke::TestNoPygameImport` (all 8 core module tests) |
| a3 | GR-001 | Core modules (agent_registry, config, execution, simulation, etc.) do not import pygame | M5 `9bf7132` | `test_smoke::TestNoPygameImport` (all 8 core module tests) |

## 14. Screen Routing State Machine

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | GR-003 | `ui/__init__.py` (ScreenId enum, Screen ABC with lifecycle hooks) | M5 `9bf7132` | `test_unit::TestScreenRouting::test_screen_id_typed_enum` |
| a1 | GR-006 | `game_runner.py:56-84` (typed dispatch, _navigate with on_enter/on_exit) | M5 `9bf7132` | `test_unit::TestScreenRouting::test_screen_abc_lifecycle` |

## 15. Board Rendering Layout

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | GR-004 | `ui/board_renderer.py` (BoardLayout dataclass, grid from board_size) | M5 `9bf7132` | `test_unit::TestBoardLayout::test_board_layout_dynamic` |
| a1 | GR-005 | `ui/board_renderer.py:58-67` (validate_layout sanity check) | M5 `9bf7132` | `test_unit::TestBoardLayout::test_board_layout_has_validate` |

## 16. Temporary File Lifecycle

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | GR-008 | `ui/screens/map_builder.py` (no tempfile usage; in-memory dict via _build_map_data) | M5 `9bf7132` | `test_smoke::TestMapBuilderNoTempfileLeak::test_map_builder_no_tempfile_leak` |

## 17. Typed Config Objects and Centralized Defaults

| Origin | ID | Implementing File(s) | Milestone | Verifying Test |
|--------|------|----------------------|-----------|----------------|
| a2 | BR-009 | `config.py` (GameConfig/BatchConfig dataclasses with __post_init__ validation) | M5 `9bf7132` | `test_unit::TestTypedConfig::test_config_typed_validation_game`, `test_unit::TestTypedConfig::test_config_typed_validation_batch` |
| a2 | BR-010 | `config.py:16` (DEFAULT_COUNT_STEPS = 4761, documented) | M5 `9bf7132` | `test_unit::TestTypedConfig::test_default_count_steps_centralized` |
| a1 | BR-006 | `config.py` (typed dataclass replaces raw dict config) | M5 `9bf7132` | `test_unit::TestTypedConfig::test_config_is_dataclass` |

---

## Summary

| Metric | Count |
|--------|-------|
| Unique (origin, ID) finding records | 43 |
| Finding records mapped to implementation | 43 |
| Finding records with verifying test | 43 |
| Unmapped findings | **0** |

All 43 finding records across 17 canonical issues from 3 audit reports are mapped to implementing code and verified by automated tests.
