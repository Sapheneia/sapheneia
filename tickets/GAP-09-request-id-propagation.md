# GAP-09: Propagate Request IDs Across Services

**Priority:** LOW
**Severity:** LOW
**Category:** Observability
**Effort:** 1 day

---

## Architecture Review

### Reliability
- **Debugging:** Correlated logs across services
- **Tracing:** End-to-end request tracking

### Integrity
- **Audit Trail:** Complete request history
- **Troubleshooting:** Identify failures across service boundaries

---

## Summary

Each service generates its own `request_id`. The Go orchestrator's ID is not propagated through Python services, breaking cross-service tracing.

## Current State

```python
# orchestration/schema.py:240-242
request_id: str = Field(
    default_factory=lambda: str(uuid.uuid4()),  # Generated fresh
)
```

## Acceptance Criteria

- [ ] Accept `X-Request-ID` header in Python endpoints
- [ ] Propagate ID to downstream services
- [ ] Include ID in all log messages
- [ ] Include ID in response headers

## Implementation

### Router Update

```python
# orchestration/router.py

from fastapi import Header

@router.post("/v1/predict")
async def predict(
    request: InferenceRequest,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    # Use provided ID or keep generated one
    if x_request_id:
        request.request_id = x_request_id

    logger.info(f"[{request.request_id}] Processing request")
    response = await service.predict(request)

    return Response(
        content=response.model_dump_json(),
        headers={"X-Request-ID": request.request_id},
    )
```

### Service Update

```python
# orchestration/service.py

async def _call_model_service(self, url: str, payload: dict, request_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=payload,
            headers={"X-Request-ID": request_id},
        )
        return response.json()
```

## Related Files

- `orchestration/router.py`
- `orchestration/service.py`
- `forecast/main.py`
