# Model Support Status

This document tracks which forecast models work with AleutianFOSS + Sapheneia.

**Last Updated:** 2026-01-22

## Quick Reference

| Status | Count | Models |
|--------|-------|--------|
| **Working** | 5 | chronos-t5-tiny, chronos-t5-mini, chronos-t5-base, chronos-t5-large, timesfm-2-0 |
| **Untested** | 1 | chronos-t5-small |
| **Broken** | 3 | chronos-bolt-mini, chronos-bolt-small, chronos-bolt-base (incompatible model signature) |
| **Not Implemented** | 32 | All others (Moirai, Granite, Moment, Yinglong, etc.) |

---

## Working Models (Verified)

These models have been tested and confirmed working:

| Model | HuggingFace ID | Family | Port |
|-------|----------------|--------|------|
| `chronos-t5-tiny` | amazon/chronos-t5-tiny | chronos | 12710 |
| `chronos-t5-mini` | amazon/chronos-t5-mini | chronos | 12711 |
| `chronos-t5-base` | amazon/chronos-t5-base | chronos | 12713 |
| `chronos-t5-large` | amazon/chronos-t5-large | chronos | 12714 |
| `timesfm-2-0` | google/timesfm-2.0-500m-pytorch | timesfm | 12721 |

### Test Commands for Working Models

```bash
# Test chronos-t5-tiny
./scripts/model-manager.sh start chronos-t5-tiny
./scripts/model-manager.sh init chronos-t5-tiny
aleutian evaluate run --config simulations/strategies/SPY/spy_chronos_t5_tiny.yaml --api-version unified

# Test chronos-t5-base
./scripts/model-manager.sh start chronos-t5-base
./scripts/model-manager.sh init chronos-t5-base
aleutian evaluate run --config simulations/strategies/SPY/spy_chronos_t5_base.yaml --api-version unified

# Test timesfm-2-0 (requires uncommenting in docker-compose.yml)
./scripts/model-manager.sh start timesfm-2-0
./scripts/model-manager.sh init timesfm-2-0
aleutian evaluate run --config simulations/strategies/SPY/spy_timesfm_2_0.yaml --api-version unified
```

---

## Untested Models

These models have Sapheneia container definitions but haven't been verified:

| Model | HuggingFace ID | Notes |
|-------|----------------|-------|
| `chronos-t5-small` | amazon/chronos-t5-small | Should work (same family as working models) |

### Test Commands for Untested Models

```bash
# Test chronos-t5-small
./scripts/model-manager.sh start chronos-t5-small
./scripts/model-manager.sh init chronos-t5-small
curl http://localhost:12712/forecast/v1/chronos/status -H "Authorization: Bearer default_trading_api_key_please_change"
```

---

## Broken Models

These models have been tested and confirmed **not working** with the current Sapheneia implementation:

| Model | HuggingFace ID | Reason |
|-------|----------------|--------|
| `chronos-bolt-mini` | amazon/chronos-bolt-mini | Incompatible model signature - Bolt uses different parameters than T5 |
| `chronos-bolt-small` | amazon/chronos-bolt-small | Incompatible model signature - Bolt uses different parameters than T5 |
| `chronos-bolt-base` | amazon/chronos-bolt-base | Incompatible model signature - Bolt uses different parameters than T5 |

> **Note:** Chronos Bolt models use a different architecture than Chronos T5. The current `ChronosPipeline` implementation in Sapheneia does not support Bolt's parameter signature. Supporting Bolt would require a separate pipeline implementation.

---

## Not Implemented Models

These models have AleutianFOSS routing but **no Sapheneia implementation yet**.
Running backtests with these will fail with connection errors.

### Google TimesFM (Partial)
| Model | HuggingFace ID | Status |
|-------|----------------|--------|
| `timesfm-1-0` | google/timesfm-1.0-200m | No container |
| `timesfm-2-5` | google/timesfm-2.5 | No container |

### Salesforce Moirai
| Model | HuggingFace ID |
|-------|----------------|
| `moirai-1-0-small` | Salesforce/moirai-1.0-R-small |
| `moirai-1-1-small` | Salesforce/moirai-1.1-R-small |
| `moirai-1-1-base` | Salesforce/moirai-1.1-R-base |
| `moirai-1-1-large` | Salesforce/moirai-1.1-R-large |
| `moirai-2-0-small` | Salesforce/moirai-2.0-R-small |

### IBM Granite
| Model | HuggingFace ID |
|-------|----------------|
| `granite-ttm-r1` | ibm/granite-timeseries-ttm-r1 |
| `granite-ttm-r2` | ibm/granite-timeseries-ttm-r2 |
| `granite-flowstate` | ibm-granite/granite-timeseries-flowstate |
| `granite-patchtsmixer` | ibm-granite/granite-timeseries-patchtsmixer |
| `granite-patchtst` | ibm-granite/granite-timeseries-patchtst |

### AutonLab Moment
| Model | HuggingFace ID |
|-------|----------------|
| `moment-small` | AutonLab/MOMENT-1-small |
| `moment-base` | AutonLab/MOMENT-1-base |
| `moment-large` | AutonLab/MOMENT-1-large |

### Alibaba Yinglong
| Model | HuggingFace ID |
|-------|----------------|
| `yinglong-6m` | Alibaba/yinglong-6m |
| `yinglong-50m` | Alibaba/yinglong-50m |
| `yinglong-110m` | Alibaba/yinglong-110m |
| `yinglong-300m` | Alibaba/yinglong-300m |

### Other Models
| Model | HuggingFace ID |
|-------|----------------|
| `lag-llama` | time-series-foundation-models/Lag-Llama |
| `kairos-10m` | Salesforce/kairos-10m |
| `kairos-50m` | Salesforce/kairos-50m |
| `timemoe-200m` | Maple728/TimeMoE-200M |
| `timer` | thuml/Timer |
| `sundial` | Sundial/sundial |
| `toto` | Databricks/toto |
| `falcon-tst` | tii-falcon/falcon-tst |
| `tempopfn` | Salesforce/TempoPFN |
| `forecastpfn` | amazon/forecastpfn |
| `chattime` | amazon/chattime |
| `opencity` | OpenCity/opencity |
| `units` | mzchen/UniTS |

---

## Testing Framework

Use the test script to systematically verify models:

```bash
# List all models with status
./scripts/test-models.sh list

# Test all testable models
./scripts/test-models.sh test

# Test only known-working models (quick verification)
./scripts/test-models.sh quick

# Test a specific model
./scripts/test-models.sh model chronos-t5-tiny

# Test all models in a family
./scripts/test-models.sh family chronos

# Generate report
./scripts/test-models.sh report
```

---

## Adding Support for New Models

To add a new model family to Sapheneia:

1. **Create Python module:**
   ```
   forecast/models/<family>/
   ├── __init__.py
   ├── routes/endpoints.py
   ├── services/model.py
   └── schemas/schema.py
   ```

2. **Register in MODEL_REGISTRY:**
   Edit `forecast/models/__init__.py`

3. **Add to Dockerfile.forecast:**
   Add conditional dependency installation

4. **Add to docker-compose.yml:**
   Create service definition with port assignment

5. **Update test-models.sh:**
   Add model to MODELS array with status

6. **Test thoroughly:**
   ```bash
   ./scripts/test-models.sh model <new-model-slug>
   ```

---

## Port Assignments

| Range | Family |
|-------|--------|
| 12710-12714 | Chronos T5 |
| 12715-12717 | Chronos Bolt |
| 12720-12722 | TimesFM |
| 12730-12734 | Moirai |
| 12740-12744 | Granite |
| 12750-12752 | Moment |
| 12760-12763 | Yinglong |
| 12770-12782 | Others |
