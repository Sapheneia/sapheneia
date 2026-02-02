# GAP-08: Make Inference Timeout Configurable

**Priority:** LOW
**Severity:** LOW
**Category:** Code Quality
**Effort:** 0.5 days

---

## Architecture Review

### Reliability
- **Flexible Timeouts:** Different models need different timeouts
- **Graceful Handling:** Timeout should log and fail clearly

### Optimization
- **Fast Models:** Tiny models could use shorter timeout
- **Large Models:** Large models may need > 5 minutes

---

## Summary

The inference timeout is hardcoded to 300 seconds in `orchestration/service.py`. Not configurable per-model.

## Current State

```python
# orchestration/service.py:76
self.timeout = 300.0  # 5 minutes for model operations
```

## Acceptance Criteria

- [ ] Timeout configurable via environment variable
- [ ] Optional per-request timeout override
- [ ] Update `.env.template` with documentation

## Implementation

```python
# orchestration/service.py

class InferenceService:
    def __init__(self, ...):
        import os
        self.default_timeout = float(os.getenv("INFERENCE_TIMEOUT", "300.0"))

    async def predict(
        self,
        request: InferenceRequest,
        timeout: Optional[float] = None,  # Per-request override
    ) -> InferenceResponse:
        effective_timeout = timeout or self.default_timeout
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            ...
```

### `.env.template` Update

```bash
# Inference timeout in seconds (default: 300)
# Increase for large models, decrease for tiny models
INFERENCE_TIMEOUT=300.0
```

## Related Files

- `orchestration/service.py`
- `.env.template`
