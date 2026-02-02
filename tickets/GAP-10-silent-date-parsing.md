# GAP-10: Fix Silent Date Parsing Failures

**Priority:** LOW
**Severity:** LOW
**Category:** Code Quality
**Effort:** 0.5 days

---

## Architecture Review

### Reliability
- **No Silent Failures:** Errors should be logged
- **Graceful Degradation:** Continue with default if parsing fails

### Integrity
- **Data Quality:** Wrong dates lead to wrong results
- **User Feedback:** Users should know when input was invalid

---

## Summary

Date parsing errors in the legacy adapter are silently ignored, which can lead to unexpected behavior.

## Current State

```python
# orchestration/adapters.py:351-363
try:
    end_date = datetime.strptime(legacy_request.as_of_date, "%Y-%m-%d").date()
except ValueError:
    pass  # Silent failure - uses today's date instead
```

## Issues

1. Silent failure on date parse error (no logging)
2. Assumes daily data frequency (breaks for hourly/weekly)
3. User not informed when date format is wrong

## Acceptance Criteria

- [ ] Log warning on date parse failure
- [ ] Support multiple common date formats
- [ ] Add test for date parsing edge cases

## Implementation

```python
# orchestration/adapters.py

import logging
from typing import Optional
from datetime import date, datetime

logger = logging.getLogger(__name__)

DATE_FORMATS = [
    "%Y-%m-%d",    # 2023-01-15 (primary)
    "%Y/%m/%d",    # 2023/01/15
    "%Y%m%d",      # 20230115
]


def parse_date_flexible(date_str: str) -> Optional[date]:
    """
    Try multiple date formats, return None if all fail.

    Args:
        date_str: Date string to parse

    Returns:
        Parsed date or None
    """
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def legacy_to_inference(...):
    # ... existing code ...

    end_date = date.today()
    if legacy_request.as_of_date:
        parsed = parse_date_flexible(legacy_request.as_of_date)
        if parsed:
            end_date = parsed
        else:
            logger.warning(
                f"Failed to parse as_of_date '{legacy_request.as_of_date}', "
                f"using today. Supported formats: {DATE_FORMATS}"
            )

    # ... rest of function ...
```

### Test

```python
def test_parse_date_flexible_iso():
    assert parse_date_flexible("2023-01-15") == date(2023, 1, 15)

def test_parse_date_flexible_compact():
    assert parse_date_flexible("20230115") == date(2023, 1, 15)

def test_parse_date_flexible_invalid():
    assert parse_date_flexible("not-a-date") is None

def test_legacy_to_inference_logs_warning_on_bad_date(caplog):
    req = LegacyForecastRequest(as_of_date="invalid", ...)
    legacy_to_inference(req)
    assert "Failed to parse" in caplog.text
```

## Related Files

- `orchestration/adapters.py`
- `orchestration/tests/test_adapters.py`
