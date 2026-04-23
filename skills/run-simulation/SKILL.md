---
name: run-simulation
description: Use when the user asks to run a Sapheneia simulation matrix from a combinations.yaml file. Expands the matrix into individual strategy YAMLs, dispatches parallel runs through the orchestrator MCP, polls until complete, and produces a comparison report saved under .local/experiments/{experiment_id}/. Don't use for single-strategy debug runs — use the `sapheneia simulate` CLI directly for those.
---

# run-simulation

You are running a Sapheneia matrix simulation on behalf of the user.

## Inputs

- A `combinations.yaml` file (path provided by the user, defaults to `./combinations.yaml`).
- The `sapheneia-mcp` MCP server is reachable. If not, surface the error and stop.

## Output

- `.local/experiments/{experiment_id}/report.md` — markdown comparison table.
- `.local/experiments/{experiment_id}/combinations.yaml` — copy of the input.
- `experiments/{TIMESTAMP}/strategy_*.yaml` — rendered per-run YAMLs (kept for reproducibility).

## The five phases

### Phase 1 — Validate

Call:
- `validate_combinations(yaml_text=<contents>)`

If `valid: false`, surface every error verbatim to the user and stop. Do not try to "fix" the YAML on the user's behalf — they should see exactly what failed.

### Phase 2 — Expand matrix

Call:
- `expand_matrix(yaml_text=<contents>)`

This returns a list of cohorts:
```json
[{"forecast_key": {"model": "...", "ticker": "...", "context_size": 252},
  "strategy_variants": [...]}, ...]
```

Count the total variants across all cohorts. If > 200, ask the user to confirm before dispatching. Otherwise proceed.

### Phase 3 — Render and dispatch

Read `parallelism.max_concurrent_runs` from the YAML (default 4).

For each cohort:
1. Call `render_strategies(combinations_yaml_text=<contents>, cohort=<cohort>)` — returns a list of YAML strings.
2. Call `run_simulation_batch(strategy_yamls=<list>)` — returns list of `{run_id, status}`.
3. Track all returned `run_id` values in a list.

Respect the parallelism cap: never have more than `max_concurrent_runs` runs in `pending`+`running` state at once. Use `get_run_status` to check before dispatching the next batch.

### Phase 4 — Poll for completion

Every 5 seconds, call:
- `get_run_status(run_ids=<all active run_ids>)`

A run is in a terminal state if its `status` is `completed`, `failed`, `cancelled`, or `not_found`.

When all runs reach terminal state, proceed to Phase 5.

If any individual run hits `failed`, log the error (the response includes `error` field) but do NOT abort the rest of the matrix. Failures will be surfaced in the report.

### Phase 5 — Build the report

Call:
- `query_results(experiment_id=<from yaml metadata>, limit=1000)`

For each run row, also call `get_run_status(run_ids=[run_id])` to retrieve the metrics block.

Build a markdown table with these columns:
- ticker
- model_id
- trading_horizon (parse from `config.trading.horizon`)
- context_size (parse from `config.forecast.context_size`)
- strategy_type
- sharpe
- max_drawdown
- total_return
- status

Sort by `sharpe` descending (treat null as -inf). Bold the top 3 rows.

Append a "Failures" section if any runs failed, listing run_id + error message.

Save to `.local/experiments/{experiment_id}/report.md`. Also copy the input YAML to the same directory.

Show the user:
1. Total runs / passed / failed counts.
2. Top 5 rows of the table inline.
3. Path to the full report.

## Cleanup phase (only if user requests)

If the user said "and clean up the cache" (or similar), call:
- `delete_cache(experiment_id=<id>)` — removes forecast cache rows for this experiment.

If they said "delete the runs", call `delete_run(run_id=<id>)` for each. This cascades to all child rows.

## Failure modes

| Symptom | Action |
|---------|--------|
| `validate_combinations` returns `valid: false` | Surface errors verbatim, stop. |
| MCP server unreachable | Report `MCP transport error`, stop. |
| Matrix > 200 cells | Ask user to confirm before dispatching. |
| `get_run_status` returns `not_found` | Log and continue; run was likely deleted externally. |
| All runs `failed` with same error | Likely service down; show the error + the suspect service from the run's `error` field. |
| Disk full when writing report | Skip the file write; print the table to stdout instead. |

## Tools used

- `validate_combinations`, `expand_matrix`, `render_strategies`
- `run_simulation_batch`, `get_run_status`, `query_results`
- `delete_run`, `delete_cache` (cleanup phase only)

## Output convention

```
.local/experiments/{experiment_id}/
├── combinations.yaml
└── report.md
experiments/{TIMESTAMP}/
└── strategy_*.yaml   (one per run, for reproducibility)
```

## Style

Brief progress updates between phases ("Validating...", "Dispatching 12 runs in 3 batches...", "23/48 completed..."). No verbose narration; the user can read the report.

When summarizing at the end: lead with the top performer's metrics. Note any anomalies (Sharpe > 5 or < -2, drawdown > 50%) — those are usually data or strategy bugs worth flagging.
