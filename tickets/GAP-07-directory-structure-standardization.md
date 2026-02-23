# GAP-07: Standardize Directory Structure

**Priority:** LOW
**Severity:** LOW
**Category:** Storage
**Effort:** 1 day

---

## Architecture Review

### Integrity
- **Documentation Accuracy:** Actual structure should match documented design
- **Developer Experience:** Clear structure reduces confusion

### Separation
- **Organized by Purpose:** Each directory has clear responsibility
- **Easy Navigation:** Predictable file locations

---

## Summary

The actual `simulations/` directory structure differs from what's documented in the design docs. While functional, it creates confusion.

## Current vs Documented Structure

**Documented (design docs):**
```
simulations/
├── forecasts/
├── backtests/
├── strategies/
├── models/
└── index/
```

**Actual:**
```
simulations/
└── strategies/
    ├── BND/
    ├── SPY/
    └── results/
```

## Recommendation

**Option A (Recommended):** Document the actual structure - it's simpler and works.

## Acceptance Criteria

- [ ] Create `simulations/README.md` explaining actual structure
- [ ] Update any design docs referencing the old structure
- [ ] Add `.gitkeep` to preserve empty directories

## Implementation

### File: `simulations/README.md`

```markdown
# Simulations Directory

Storage for strategy configurations and backtest results.

## Structure

```
simulations/
└── strategies/
    ├── {TICKER}/                    # Per-ticker strategy configs
    │   └── {ticker}_{model}.yaml    # Strategy YAML files
    ├── results/                     # Backtest results
    │   └── {timestamp}/             # Results by run time
    │       └── *.csv
    └── run_all_backtests.sh         # Batch runner script
```

## Strategy Config Format

See any YAML file for structure. Required fields:
- `metadata.id` - Unique strategy identifier
- `evaluation.ticker` - Stock symbol
- `evaluation.start_date` / `end_date` - Backtest period
- `forecast.model` - Model to use
- `trading.strategy_type` - Trading strategy

## Running Backtests

```bash
# Single strategy
sapheneia evaluate --config strategies/SPY/spy_chronos_t5_tiny.yaml

# All strategies
./strategies/run_all_backtests.sh
```
```

## Related Files

- `simulations/strategies/`
- `docs/design/aleutian_integration_v2.md`
