# Project: Sapheneia Foundation Models Time Series Forecast

@CLAUDE.local.md

## Project Overview

**Goal**:
- The goal of this project is to produce an agentic orchestration system to run time-series forecasting on various Foundation models.

**Background**:
- Sapheneia is a research and experimentation project focused on financial forecasting and time series analisys.
- The project uses various foundation models for making predictions with exogenous variables and includes comprehensive utilities for financial data analysis.

**Structure**:
- The project contains the following sub-applications or modules: `forecast`, `metrics`, `trading` and `orchestration`.
- These modules `forecast`, `metrics` and `trading` operate independently through FastAPI.
- The module `orchestration` orchestrates and manages the execution of the experiments.

## What Claude Gets Wrong

- Never chain commands with `&&`. Use separate sequential tool calls instead. Run clean and sequential `bash` commands so that the settings in `.claude/settings.local.json` are in effect.
- Never prefix commands with `cd path &&`. Use absolute paths directly or rely on the working directory. Run clean and sequential `bash` commands so that the settings in `.claude/settings.local.json` are in effect.

## Commands

- Follow the settings in `.claude/settings.local.json`, especially the `bash` commands as I do not wish you to constantly ask for permissions.
- For all deep research tasks you MUST use the skill `deep-research-plus`.

## Agent Routing Rules

- Spawn parallel subagents when ALL of these are true:
	- Tasks touch different files/modules (no overlap).
	- Tasks have no dependency on each other's output.
	- 2+ independent domains are involved simultaneously.
- Spawn sequential subagents when ANY of these is true:
	- Task B needs output from Task A.
	- Both tasks modify shared files.
	- Scope is unclear and needs planning first.
- Background dispatch when:
	- Task is research/analysis only (no file writes).
	- Result is not blocking the next step.

## Architecture rules

> Universal `[ABS]` principles. The full discussion of each lives in [project-engineering.md](.config/agentic-engineering/project-engineering.md) under the named category. These short rules are duplicated here because every subagent reads `CLAUDE.md` before any work; only `architecture-reviewer` reads `project-engineering.md`.

- **§3.5 Parameterization discipline.** Never hardcode values that vary across contexts (tickers, model IDs, paths, timeouts, URLs). Code is generic; varying inputs are parameters loaded from `pydantic-settings` or YAML. If a value appears as a literal in two places, extract it to a shared constant or config field. The current known drift — model-family slugs `"chronos"` / `"timesfm20"` duplicated in `orchestrator/clients/forecast_client.py` and `orchestrator/services/runs_service.py` — is tracked as a NIT and should converge to a shared enum in `shared/`. See [project-engineering.md §3.5](.config/agentic-engineering/project-engineering.md).

- **§4.3 Dependency direction & enforcement.** Leaf services (`forecast`, `trading`, `metrics`) must never import from persistence layers (`asyncpg`, `shared.db`). The orchestrator is the sole writer of run-state. This invariant is currently enforced by code review only (no `pytest-archon`); preserve the invariant manually in every PR. See [project-engineering.md §4.3](.config/agentic-engineering/project-engineering.md).

- **§5.4 Symmetric fixes require symmetric tests.** When fixing a bug class that exists at multiple sites (e.g., the auth-header propagation pattern across all four orchestrator clients), fix every site AND add a test for every site. If a site's test is deferred, log it as a WARN in `code-review-followups.md`. See [project-engineering.md §5.4](.config/agentic-engineering/project-engineering.md).

- **§7.2 Specs must include explicit decisions.** Task specs (e.g., `.local/01-phase/*.md` design plans) must name reference implementations and explicit decisions, not just intent. "Add forecast caching" is incomplete; "Add forecast cache with 6-column unique index `(model_id, ticker, time, context_size, horizon_size, run_id)` excluding `trading_horizon`, mirrored by a 5-column non-unique lookup index" is complete. See [project-engineering.md §7.2](.config/agentic-engineering/project-engineering.md).

- **§7.3 Iterative refinement loop — write first, edit in file.** Drop the draft into `.local/01-phase/` early; iterate by editing the file in subsequent turns. Avoid long chat-only drafting sessions — get the structure on disk first so it's diff-able and reviewable. See [project-engineering.md §7.3](.config/agentic-engineering/project-engineering.md).

- **§7.7 WARN/NIT capture.** Every `code-reviewer` WARN/NIT that does not block merge must be appended to `.config/agentic-engineering/code-review-followups.md` (Open items section). Closing an item moves it to the Closed section with the resolution. Never let WARN/NIT items vanish in chat. See [project-engineering.md §7.7](.config/agentic-engineering/project-engineering.md).

- **§7.8 Cleanest-answer meta-rule.** When two solutions exist — one architecturally clean (often more work) and one expedient patch — default to the clean answer. The Phase 1d plan and Appendix entries (no-look-ahead at SQL layer, cascade deletes, heartbeat reconciler, double-index design) are exemplars. Patches are permitted only when explicitly traded off against schedule and logged as tech debt. See [project-engineering.md §7.8](.config/agentic-engineering/project-engineering.md).

- **§9.3 Out-of-band success verification.** For long-running upstream calls (300s+ Chronos inference, multi-step forecasts), if a call errors, FIRST probe whether the work was actually completed (e.g., check whether a forecast row was already written for this run+date) BEFORE retrying. Retries that aren't idempotent will duplicate work on flaky timeouts. This is currently NOT IMPLEMENTED in orchestrator clients — flagged as a future gap. See [project-engineering.md §9.3](.config/agentic-engineering/project-engineering.md).

## Gates required (autopilot trust requires these to pass)

| Gate | Tool | Config location |
|------|------|-----------------|
| Lint | `ruff check` | `[tool.ruff]` in `pyproject.toml` |
| Format | `ruff format --check` | same |
| Complexity | ruff `C901` (mccabe) | `[tool.ruff.lint.mccabe]` — `max-complexity = 25` (ratchet from current max 24; tighten to 15 then 10 over time) |
| Type-check | `mypy` | `[tool.mypy]` — lenient_ratchet with `disable_error_code` for the four no-type-annotation errors |
| Tests + coverage | `pytest --cov` | `[tool.coverage.report].fail_under = 35` |
| Architecture tests | plugin runner at `/home/marcelo/.services/jarvis/plugins/agentic-engineering/scripts/test_architecture.py` | rules in `.config/agentic-engineering/architecture-rules.yaml` |
| Dead code | (skipped) | `tooling.dead_code_detector: none` in `project-parameters.yaml` |

All run via `/home/marcelo/.services/jarvis/plugins/agentic-engineering/scripts/gates.sh`. Autopilot mode requires every detected gate to pass before commit.
