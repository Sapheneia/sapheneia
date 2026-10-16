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

> Universal `[ABS]` principles. These short rules are the **authoritative in-repo statement** — every subagent reads `CLAUDE.md` before any work. Longer-form discussion lives outside the repository under `.config/agentic-engineering/` (gitignored, per-developer); treat it as commentary, never as the source of truth, and never link to it as if it ships.

- **§3.5 Parameterization discipline.** Never hardcode values that vary across contexts (tickers, model IDs, paths, timeouts, URLs). Code is generic; varying inputs are parameters loaded from `pydantic-settings` or YAML. If a value appears as a literal in two places, extract it to a shared constant or config field.

  Model identity is the standing example. `shared/model_family.py` owns the family slugs and `shared/model_registry.py` owns the model -> container/port table; both the forecast service (`GET /models`) and the orchestrator (`model_id` -> base URL routing) read from them. Never re-derive a family from a substring check (`"chronos" in model_id`) and never add a second registry — an inline check silently routes unknown IDs to a default, and a second registry drifts out of sync with `docker-compose.yml` without anything failing.

- **§4.3 Dependency direction & enforcement.** The invariant is **table-scoped, not service-scoped**:

  - `forecast`, `trading`, `metrics` are pure compute. They must never import `asyncpg` or `shared.db`.
  - `data` owns the `prices` and `tickers` tables and *does* hold a pool — it is a leaf service by call graph, not by persistence.
  - The **orchestrator is the sole writer of run-state**: `runs`, `forecasts`, `trades`, `equity`, `metrics`. Nothing else writes those five tables.

  Enforced by code review only (no `pytest-archon`); preserve it manually in every PR.

- **§5.4 Symmetric fixes require symmetric tests.** When fixing a bug class that exists at multiple sites, fix every site AND add a test for every site. The reference case is auth-header propagation across the four orchestrator clients: one `BaseHttpClient` in `shared/http_client.py`, and a per-client test in `orchestrator/tests/test_clients_unit.py` covering URL, `Authorization`, `X-Request-ID`, and upstream 5xx. The production-key guard in `shared/service_config.py` is the same shape, applied to all four service configs.

- **§7.2 Specs must include explicit decisions.** Task specs must name reference implementations and explicit decisions, not just intent. "Add forecast caching" is incomplete. The shipped design is complete and is the model to imitate: forecast identity is the **6-column primary key** `(run_id, ticker, time, model_id, context_size, horizon_size)`, mirrored by the **5-column non-unique** `ix_forecasts_cache_lookup` `(model_id, ticker, time, context_size, horizon_size)` for cross-run reads, with `trading_horizon` deliberately excluded because a forecast does not depend on it. Keep the spec and `migrations/versions/001_initial_schema.py` in agreement — a key narrower than the identity makes `ON CONFLICT DO NOTHING` discard real rows in silence.

- **§7.3 Iterative refinement loop — write first, edit in file.** Drop the draft into `.local/01-phase/` early; iterate by editing the file in subsequent turns. Avoid long chat-only drafting sessions — get the structure on disk first so it's diff-able and reviewable.

- **§7.7 WARN/NIT capture.** Every review WARN/NIT that does not block merge must be written down before the session ends — the local ledger at `.config/agentic-engineering/code-review-followups.md` (gitignored) or a tracker issue. Anything that must outlive the working copy belongs in a tracker issue, not the local file. Never let WARN/NIT items vanish in chat.

- **§7.8 Cleanest-answer meta-rule.** When two solutions exist — one architecturally clean (often more work) and one expedient patch — default to the clean answer. Exemplars in this repo: no-look-ahead enforced in the SQL `WHERE` clause rather than filtered in application code; cascade deletes on every run-scoped hypertable; the double-index cache design; one canonical `ForecastEnvelope` returned by every model family instead of shape-sniffing at the call site. Patches are permitted only when explicitly traded off against schedule and logged as tech debt.

- **§9.3 Out-of-band success verification.** For long-running upstream calls (300s+ Chronos inference, multi-step forecasts), if a call errors, FIRST probe whether the work was actually completed (e.g., check whether a forecast row was already written for this run+date) BEFORE retrying. Retries that aren't idempotent will duplicate work on flaky timeouts. **Still NOT IMPLEMENTED** in the orchestrator clients — the clients have no retry logic at all today, so the gap is latent rather than active. Anything that adds a retry must add the probe in the same change.

## Gates required (autopilot trust requires these to pass)

| Gate | Tool | Config location |
|------|------|-----------------|
| Lint | `ruff check` | `[tool.ruff]` in `pyproject.toml` |
| Format | `ruff format --check` | same |
| Complexity | ruff `C901` (mccabe) | `[tool.ruff.lint.mccabe]` — `max-complexity = 25` (ratchet from current max 24; tighten to 15 then 10 over time) |
| Type-check | `mypy` | `[tool.mypy]` — lenient_ratchet with `disable_error_code` for the four no-type-annotation errors |
| Tests + coverage | `pytest --cov` | `[tool.coverage.report].fail_under = 35` |
| Architecture tests | local plugin runner (not in-repo; see §4.3 — enforced by review) | local `.config/agentic-engineering/architecture-rules.yaml` |
| Dead code | (skipped) | `tooling.dead_code_detector: none` |

CI (`.github/workflows/ci.yml`) runs lint/format, mypy, unit tests, and a
separate **integration** job against a real TimescaleDB service container — the
unit job runs `-m "not integration"`, so repository SQL is only covered by that
second job. The architecture-test and dead-code gates run from a developer's
local plugin install and are not reproduced in CI.

All run via `/home/marcelo/.services/jarvis/plugins/agentic-engineering/scripts/gates.sh`. Autopilot mode requires every detected gate to pass before commit.
