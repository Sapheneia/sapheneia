# GAP-06: Add Explicit Backtest Mode Test in Go

**Priority:** MEDIUM
**Severity:** MEDIUM
**Category:** Testing
**Effort:** 0.5 days

---

## Architecture Review

### Reliability
- **Current Risk:** Critical temporal isolation feature is untested
- **Mitigation:** Add explicit test verifying stop time bound
- **Regression Prevention:** Test ensures future changes don't break backtest mode

### Integrity
- **Date Format Verification:** Test RFC3339 format with T23:59:59Z suffix
- **Query Structure:** Verify Flux query contains correct stop parameter
- **Mode Detection:** Verify logging indicates "backtest mode"

---

## Summary

The critical temporal isolation feature lacks direct test coverage. While there are tests for basic query handling and date parsing, there's no specific test verifying that the `end_date` parameter creates proper temporal bounds and prevents future data leakage.

## Current State

- `data/main_test.go` has 21 tests (good coverage overall)
- Tests exist for: valid requests, invalid JSON, no ticker, default days, date parsing
- **No test** specifically for backtest mode with `end_date` parameter
- The critical look-ahead bias prevention is untested

## Critical Code Under Test

```go
// data/main.go:421-447
func (s *Server) handleQueryData(c *gin.Context) {
    // ...
    if req.EndDate != "" {
        // BACKTEST MODE: Use end_date as stop parameter
        stopTime := fmt.Sprintf("%sT23:59:59Z", req.EndDate)
        query = fmt.Sprintf(`
            from(bucket: "%s")
              |> range(start: -%dd, stop: %s)  // <-- CRITICAL
              |> filter(fn: (r) => r._measurement == "stock_prices")
              |> filter(fn: (r) => r.ticker == "%s")
              ...
        `, influxBucket, req.Days+10, stopTime, req.Ticker)
    }
}
```

## Acceptance Criteria

- [ ] Add `TestHandleQueryData_BacktestMode` test
- [ ] Verify query contains correct stop time bound
- [ ] Add `TestHandleQueryData_LiveMode` test for comparison
- [ ] Verify backtest mode logging

## Implementation

### File: `data/main_test.go` (additions)

```go
// TestHandleQueryData_BacktestMode verifies that providing end_date
// creates proper temporal bounds to prevent look-ahead bias
func TestHandleQueryData_BacktestMode(t *testing.T) {
    // Setup
    mockQueryAPI := new(MockQueryAPI)
    server := &Server{
        QueryAPI: mockQueryAPI,
    }

    // Capture the query string for inspection
    var capturedQuery string
    mockQueryAPI.On("Query", mock.Anything, mock.AnythingOfType("string")).
        Run(func(args mock.Arguments) {
            capturedQuery = args.Get(1).(string)
        }).
        Return(createMockQueryResult([]float64{380.0, 381.0, 382.0}), nil)

    // Create request with end_date (backtest mode)
    reqBody := DataQueryRequest{
        Ticker:  "SPY",
        Days:    90,
        EndDate: "2023-01-15",  // Historical date
    }
    body, _ := json.Marshal(reqBody)

    // Setup Gin test context
    gin.SetMode(gin.TestMode)
    w := httptest.NewRecorder()
    c, _ := gin.CreateTestContext(w)
    c.Request = httptest.NewRequest("POST", "/v1/data/query", bytes.NewBuffer(body))
    c.Request.Header.Set("Content-Type", "application/json")

    // Execute
    server.handleQueryData(c)

    // Assert response
    assert.Equal(t, http.StatusOK, w.Code)

    // CRITICAL: Verify query contains stop time bound
    assert.Contains(t, capturedQuery, "stop:",
        "Backtest mode query MUST contain stop: parameter")

    assert.Contains(t, capturedQuery, "2023-01-15T23:59:59Z",
        "Stop time must be end_date with T23:59:59Z suffix")

    // Verify query structure is correct
    assert.Contains(t, capturedQuery, `range(start:`,
        "Query must use range function")
    assert.Contains(t, capturedQuery, `ticker == "SPY"`,
        "Query must filter by ticker")

    // Verify mock was called
    mockQueryAPI.AssertExpectations(t)
}

// TestHandleQueryData_LiveMode verifies that WITHOUT end_date,
// the query fetches up to current time (no stop bound)
func TestHandleQueryData_LiveMode(t *testing.T) {
    // Setup
    mockQueryAPI := new(MockQueryAPI)
    server := &Server{
        QueryAPI: mockQueryAPI,
    }

    var capturedQuery string
    mockQueryAPI.On("Query", mock.Anything, mock.AnythingOfType("string")).
        Run(func(args mock.Arguments) {
            capturedQuery = args.Get(1).(string)
        }).
        Return(createMockQueryResult([]float64{450.0, 451.0, 452.0}), nil)

    // Create request WITHOUT end_date (live mode)
    reqBody := DataQueryRequest{
        Ticker: "SPY",
        Days:   90,
        // EndDate not provided
    }
    body, _ := json.Marshal(reqBody)

    gin.SetMode(gin.TestMode)
    w := httptest.NewRecorder()
    c, _ := gin.CreateTestContext(w)
    c.Request = httptest.NewRequest("POST", "/v1/data/query", bytes.NewBuffer(body))
    c.Request.Header.Set("Content-Type", "application/json")

    // Execute
    server.handleQueryData(c)

    // Assert response
    assert.Equal(t, http.StatusOK, w.Code)

    // CRITICAL: Verify query does NOT contain stop: parameter
    // Live mode should query up to current time
    assert.NotContains(t, capturedQuery, "stop:",
        "Live mode query should NOT contain stop: parameter")

    // Verify basic query structure
    assert.Contains(t, capturedQuery, `range(start:`,
        "Query must use range function")

    mockQueryAPI.AssertExpectations(t)
}

// TestHandleQueryData_BacktestDateFormat tests various date formats
func TestHandleQueryData_BacktestDateFormats(t *testing.T) {
    testCases := []struct {
        name           string
        endDate        string
        expectedInStop string
        shouldWork     bool
    }{
        {
            name:           "YYYY-MM-DD format",
            endDate:        "2023-01-15",
            expectedInStop: "2023-01-15T23:59:59Z",
            shouldWork:     true,
        },
        {
            name:           "Start of year",
            endDate:        "2023-01-01",
            expectedInStop: "2023-01-01T23:59:59Z",
            shouldWork:     true,
        },
        {
            name:           "End of year",
            endDate:        "2023-12-31",
            expectedInStop: "2023-12-31T23:59:59Z",
            shouldWork:     true,
        },
        {
            name:           "Leap year date",
            endDate:        "2024-02-29",
            expectedInStop: "2024-02-29T23:59:59Z",
            shouldWork:     true,
        },
    }

    for _, tc := range testCases {
        t.Run(tc.name, func(t *testing.T) {
            mockQueryAPI := new(MockQueryAPI)
            server := &Server{QueryAPI: mockQueryAPI}

            var capturedQuery string
            mockQueryAPI.On("Query", mock.Anything, mock.AnythingOfType("string")).
                Run(func(args mock.Arguments) {
                    capturedQuery = args.Get(1).(string)
                }).
                Return(createMockQueryResult([]float64{100.0}), nil)

            reqBody := DataQueryRequest{
                Ticker:  "TEST",
                Days:    30,
                EndDate: tc.endDate,
            }
            body, _ := json.Marshal(reqBody)

            gin.SetMode(gin.TestMode)
            w := httptest.NewRecorder()
            c, _ := gin.CreateTestContext(w)
            c.Request = httptest.NewRequest("POST", "/v1/data/query", bytes.NewBuffer(body))
            c.Request.Header.Set("Content-Type", "application/json")

            server.handleQueryData(c)

            if tc.shouldWork {
                assert.Equal(t, http.StatusOK, w.Code)
                assert.Contains(t, capturedQuery, tc.expectedInStop,
                    "Stop time should match expected format")
            }
        })
    }
}

// Helper to create mock query result
func createMockQueryResult(values []float64) *api.QueryTableResult {
    // Implementation depends on your mock setup
    // Return a mock result that can be iterated
    // ...
}
```

## Running Tests

```bash
cd data

# Run specific backtest tests
go test -v -run TestHandleQueryData_BacktestMode
go test -v -run TestHandleQueryData_LiveMode
go test -v -run TestHandleQueryData_BacktestDateFormats

# Run all query tests
go test -v -run TestHandleQueryData

# Run with coverage
go test -v -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

## Dependencies

- None (can be developed independently)

## Related Files

- `data/main.go` (lines 421-447)
- `data/main_test.go`
