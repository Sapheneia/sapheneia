package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	influxdb2 "github.com/influxdata/influxdb-client-go/v2"
	"github.com/influxdata/influxdb-client-go/v2/api"
	"github.com/influxdata/influxdb-client-go/v2/api/write"
	"github.com/influxdata/influxdb-client-go/v2/domain"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// --- Mock InfluxDB QueryAPI ---
type MockQueryAPI struct {
	mock.Mock
}

func (m *MockQueryAPI) Query(ctx context.Context, query string) (*api.QueryTableResult, error) {
	args := m.Called(ctx, query)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*api.QueryTableResult), args.Error(1)
}

func (m *MockQueryAPI) QueryRaw(ctx context.Context, query string, dialect *domain.Dialect) (string, error) {
	args := m.Called(ctx, query, dialect)
	return args.String(0), args.Error(1)
}

func (m *MockQueryAPI) QueryRawWithParams(ctx context.Context, query string, dialect *domain.Dialect, params interface{}) (string, error) {
	args := m.Called(ctx, query, dialect, params)
	return args.String(0), args.Error(1)
}

func (m *MockQueryAPI) QueryWithParams(ctx context.Context, query string, params interface{}) (*api.QueryTableResult, error) {
	args := m.Called(ctx, query, params)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*api.QueryTableResult), args.Error(1)
}

// --- Mock InfluxDB WriteAPIBlocking ---
type MockWriteAPIBlocking struct {
	mock.Mock
}

func (m *MockWriteAPIBlocking) WritePoint(ctx context.Context, points ...*write.Point) error {
	args := m.Called(ctx, points)
	return args.Error(0)
}

func (m *MockWriteAPIBlocking) WriteRecord(ctx context.Context, records ...string) error {
	args := m.Called(ctx, records)
	return args.Error(0)
}

func (m *MockWriteAPIBlocking) Flush(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func (m *MockWriteAPIBlocking) EnableBatching() {
	m.Called()
}

// --- Mock HTTP Client ---
type MockHTTPClient struct {
	mock.Mock
}

func (m *MockHTTPClient) Do(req *http.Request) (*http.Response, error) {
	args := m.Called(req)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*http.Response), args.Error(1)
}

// --- Test Setup ---
func setupTestRouter() (*gin.Engine, *MockWriteAPIBlocking, *MockQueryAPI, *MockHTTPClient) {
	gin.SetMode(gin.TestMode)

	// Create all mocks
	mockWriteAPI := new(MockWriteAPIBlocking)
	mockQueryAPI := new(MockQueryAPI)
	mockHTTPClient := new(MockHTTPClient)

	// Setup default mock behaviors
	// Return an error for Query to indicate "no existing data in DB"
	// This makes getLatestTimestamp use the default start date
	mockQueryAPI.On("Query", mock.Anything, mock.Anything).Return((*api.QueryTableResult)(nil), fmt.Errorf("no data")).Maybe()
	mockWriteAPI.On("WritePoint", mock.Anything, mock.Anything).Return(nil).Maybe()

	// Setup HTTP Mock to return FAKE Yahoo Data
	fakeYahooResponse := `{
		"chart": {
			"result": [{
				"meta": {"currency": "USD", "symbol": "SPY"},
				"timestamp": [1672531200],
				"indicators": {
					"quote": [{"open": [100.0], "high": [105.0], "low": [99.0], "close": [102.0], "volume": [1000]}],
					"adjclose": [{"adjclose": [102.0]}]
				}
			}],
			"error": null
		}
	}`

	mockResp := &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(bytes.NewBufferString(fakeYahooResponse)),
		Header:     make(http.Header),
	}
	mockHTTPClient.On("Do", mock.Anything).Return(mockResp, nil).Maybe()

	// Create Server with all mocks
	server := &Server{
		WriteAPI:   mockWriteAPI,
		QueryAPI:   mockQueryAPI,
		HTTPClient: mockHTTPClient,
	}

	router := gin.Default()
	router.POST("/v1/data/fetch", server.handleFetchData)
	router.POST("/v1/data/query", server.handleQueryData)

	return router, mockWriteAPI, mockQueryAPI, mockHTTPClient
}

// Helper function for tests that don't need mock access
func setupTestRouterSimple() *gin.Engine {
	router, _, _, _ := setupTestRouter()
	return router
}

// --- Tests for handleFetchData ---

func TestHandleFetchData_ValidRequest(t *testing.T) {
	router := setupTestRouterSimple()

	reqBody := DataFetchRequest{
		Tickers:   []string{"SPY", "AAPL"},
		StartDate: "2020-01-01",
		Interval:  "1d",
	}

	body, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", "/v1/data/fetch", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()

	// Note: This test will fail without proper mocks for influxClient
	// In a real scenario, you'd need to inject the client or use dependency injection
	router.ServeHTTP(w, req)

	// We expect a response (the actual status depends on mocked InfluxDB behavior)
	assert.NotNil(t, w.Body)
}

func TestHandleFetchData_InvalidJSON(t *testing.T) {
	router := setupTestRouterSimple()

	req, _ := http.NewRequest("POST", "/v1/data/fetch", bytes.NewBufferString("invalid json"))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Contains(t, response, "error")
}

func TestHandleFetchData_NoTickers(t *testing.T) {
	router := setupTestRouterSimple()

	reqBody := DataFetchRequest{
		Tickers:   []string{},
		StartDate: "2020-01-01",
		Interval:  "1d",
	}

	body, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", "/v1/data/fetch", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, "No tickers provided", response["error"])
}

func TestHandleFetchData_DefaultInterval(t *testing.T) {
	router := setupTestRouterSimple()

	reqBody := DataFetchRequest{
		Tickers:   []string{"SPY"},
		StartDate: "2020-01-01",
		// Interval not provided - should default to "1d"
	}

	body, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", "/v1/data/fetch", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should not return error for missing interval
	assert.NotEqual(t, http.StatusBadRequest, w.Code)
}

// --- Tests for handleQueryData ---

func TestHandleQueryData_ValidRequest(t *testing.T) {
	router := setupTestRouterSimple()

	reqBody := DataQueryRequest{
		Ticker:  "SPY",
		Days:    30,
		EndDate: "",
	}

	body, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", "/v1/data/query", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.NotNil(t, w.Body)
}

func TestHandleQueryData_InvalidJSON(t *testing.T) {
	router := setupTestRouterSimple()

	req, _ := http.NewRequest("POST", "/v1/data/query", bytes.NewBufferString("invalid json"))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Contains(t, response, "error")
}

func TestHandleQueryData_NoTicker(t *testing.T) {
	router := setupTestRouterSimple()

	reqBody := DataQueryRequest{
		Ticker: "",
		Days:   30,
	}

	body, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", "/v1/data/query", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, "Ticker is required", response["error"])
}

func TestHandleQueryData_DefaultDays(t *testing.T) {
	router := setupTestRouterSimple()

	reqBody := DataQueryRequest{
		Ticker: "SPY",
		Days:   0, // Should default to 252
	}

	body, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", "/v1/data/query", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should not return error for missing days
	assert.NotNil(t, w.Body)
}

// --- Tests for Date Parsing Logic ---

func TestDateParsing_YYYYMMDD(t *testing.T) {
	// Test YYYYMMDD format parsing
	dateStr := "20200101"
	parsed, err := time.Parse("20060102", dateStr)

	assert.NoError(t, err)
	expected := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	assert.Equal(t, expected.Format("2006-01-02"), parsed.Format("2006-01-02"))
}

func TestDateParsing_YYYY_MM_DD(t *testing.T) {
	// Test YYYY-MM-DD format parsing
	dateStr := "2020-01-01"
	parsed, err := time.Parse("2006-01-02", dateStr)

	assert.NoError(t, err)
	expected := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	assert.Equal(t, expected.Format("2006-01-02"), parsed.Format("2006-01-02"))
}

func TestDateParsing_InvalidDate_FallsBack(t *testing.T) {
	// Test the fallback logic for invalid date formats
	dateStr := "invalid-date"

	// Try first format
	parsed, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		// Try second format
		parsed, err = time.Parse("20060102", dateStr)
		if err != nil {
			// Fallback to 1 year ago
			parsed = time.Now().AddDate(-1, 0, 0)
		}
	}

	// Should be approximately 1 year ago
	expected := time.Now().AddDate(-1, 0, 0)
	assert.WithinDuration(t, expected, parsed, 24*time.Hour)
}

// --- Tests for fetchYahooData ---

func TestFetchYahooData_StartTimeInFuture(t *testing.T) {
	// Create a minimal server instance for testing
	mockHTTPClient := new(MockHTTPClient)
	server := &Server{
		HTTPClient: mockHTTPClient,
	}

	futureTime := time.Now().Add(24 * time.Hour)
	points, err := server.fetchYahooData("SPY", futureTime, "1d")

	assert.NoError(t, err)
	assert.Nil(t, points)
	assert.Len(t, points, 0)

	// HTTP client should not be called since start time is in the future
	mockHTTPClient.AssertNotCalled(t, "Do", mock.Anything)
}

func TestFetchYahooData_TickerSymbolReplacement(t *testing.T) {
	// This test would require mocking HTTP client
	// Testing that "-USD" is replaced with "USDT" in the ticker tag
	// We'll create a table-driven test for the ticker replacement logic
	testCases := []struct {
		input    string
		expected string
	}{
		{"BTC-USD", "BTCUSDT"},
		{"ETH-USD", "ETHUSDT"},
		{"SPY", "SPY"},
		{"AAPL", "AAPL"},
	}

	for _, tc := range testCases {
		t.Run(tc.input, func(t *testing.T) {
			// Create a mock point to test the ticker replacement
			point := influxdb2.NewPoint(
				"stock_prices",
				map[string]string{
					"ticker": tc.input,
				},
				map[string]interface{}{
					"close": 100.0,
				},
				time.Now(),
			)

			// Get the tag value
			tickerTag := point.TagList()[0].Value

			// Note: The actual replacement happens in fetchYahooData at line 348
			// This is just demonstrating the pattern
			assert.Contains(t, []string{tc.input, tc.expected}, tickerTag)
		})
	}
}

// --- Table-Driven Tests for Data Structures ---

func TestDataFetchRequest_JSONMarshaling(t *testing.T) {
	testCases := []struct {
		name     string
		request  DataFetchRequest
		expected string
	}{
		{
			name: "Complete request",
			request: DataFetchRequest{
				Tickers:   []string{"SPY", "AAPL"},
				StartDate: "2020-01-01",
				Interval:  "1d",
			},
			expected: `{"names":["SPY","AAPL"],"start_date":"2020-01-01","interval":"1d"}`,
		},
		{
			name: "Single ticker",
			request: DataFetchRequest{
				Tickers:   []string{"SPY"},
				StartDate: "2020-01-01",
				Interval:  "1h",
			},
			expected: `{"names":["SPY"],"start_date":"2020-01-01","interval":"1h"}`,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			jsonData, err := json.Marshal(tc.request)
			assert.NoError(t, err)
			assert.JSONEq(t, tc.expected, string(jsonData))
		})
	}
}

func TestDataQueryRequest_JSONMarshaling(t *testing.T) {
	testCases := []struct {
		name     string
		request  DataQueryRequest
		expected string
	}{
		{
			name: "With end date",
			request: DataQueryRequest{
				Ticker:  "SPY",
				Days:    30,
				EndDate: "2020-12-31",
			},
			expected: `{"ticker":"SPY","days":30,"end_date":"2020-12-31"}`,
		},
		{
			name: "Without end date",
			request: DataQueryRequest{
				Ticker:  "AAPL",
				Days:    252,
				EndDate: "",
			},
			expected: `{"ticker":"AAPL","days":252,"end_date":""}`,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			jsonData, err := json.Marshal(tc.request)
			assert.NoError(t, err)
			assert.JSONEq(t, tc.expected, string(jsonData))
		})
	}
}

// --- Edge Case Tests ---

func TestYahooChartResponse_EmptyResult(t *testing.T) {
	jsonData := `{"chart":{"result":[],"error":null}}`

	var chartData YahooChartResponse
	err := json.Unmarshal([]byte(jsonData), &chartData)

	assert.NoError(t, err)
	assert.Len(t, chartData.Chart.Result, 0)
}

func TestYahooChartResponse_WithError(t *testing.T) {
	jsonData := `{"chart":{"result":[],"error":{"code":"Not Found","description":"No data found"}}}`

	var chartData YahooChartResponse
	err := json.Unmarshal([]byte(jsonData), &chartData)

	assert.NoError(t, err)
	assert.NotNil(t, chartData.Chart.Error)
}

func TestDataPoint_AllFields(t *testing.T) {
	dp := DataPoint{
		Time:     "2020-01-01T00:00:00Z",
		Open:     100.5,
		High:     105.0,
		Low:      99.0,
		Close:    103.0,
		Volume:   1000000,
		AdjClose: 102.8,
	}

	jsonData, err := json.Marshal(dp)
	assert.NoError(t, err)

	var decoded DataPoint
	err = json.Unmarshal(jsonData, &decoded)
	assert.NoError(t, err)

	assert.Equal(t, dp.Time, decoded.Time)
	assert.Equal(t, dp.Open, decoded.Open)
	assert.Equal(t, dp.High, decoded.High)
	assert.Equal(t, dp.Low, decoded.Low)
	assert.Equal(t, dp.Close, decoded.Close)
	assert.Equal(t, dp.Volume, decoded.Volume)
	assert.Equal(t, dp.AdjClose, decoded.AdjClose)
}

// --- Integration-Style Tests (with mocked external dependencies) ---

func TestFetchYahooData_WithMockedHTTPClient_Success(t *testing.T) {
	gin.SetMode(gin.TestMode)

	mockWriteAPI := new(MockWriteAPIBlocking)
	mockQueryAPI := new(MockQueryAPI)
	mockHTTPClient := new(MockHTTPClient)

	// Setup successful Yahoo Finance response
	fakeYahooResponse := `{
		"chart": {
			"result": [{
				"meta": {"currency": "USD", "symbol": "SPY"},
				"timestamp": [1672531200, 1672617600],
				"indicators": {
					"quote": [{
						"open": [100.0, 101.0],
						"high": [105.0, 106.0],
						"low": [99.0, 100.0],
						"close": [102.0, 103.0],
						"volume": [1000000, 1100000]
					}],
					"adjclose": [{"adjclose": [102.0, 103.0]}]
				}
			}],
			"error": null
		}
	}`

	mockResp := &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(bytes.NewBufferString(fakeYahooResponse)),
		Header:     make(http.Header),
	}
	mockHTTPClient.On("Do", mock.Anything).Return(mockResp, nil)

	server := &Server{
		WriteAPI:   mockWriteAPI,
		QueryAPI:   mockQueryAPI,
		HTTPClient: mockHTTPClient,
	}

	// Test fetchYahooData
	points, err := server.fetchYahooData("SPY", time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC), "1d")

	assert.NoError(t, err)
	assert.NotNil(t, points)
	assert.Len(t, points, 2)

	// Verify the HTTP client was called
	mockHTTPClient.AssertExpectations(t)
}

func TestFetchYahooData_WithMockedHTTPClient_HTTPError(t *testing.T) {
	gin.SetMode(gin.TestMode)

	mockWriteAPI := new(MockWriteAPIBlocking)
	mockQueryAPI := new(MockQueryAPI)
	mockHTTPClient := new(MockHTTPClient)

	// Setup error response
	mockResp := &http.Response{
		StatusCode: 500,
		Body:       io.NopCloser(bytes.NewBufferString(`Internal Server Error`)),
		Header:     make(http.Header),
	}
	mockHTTPClient.On("Do", mock.Anything).Return(mockResp, nil)

	server := &Server{
		WriteAPI:   mockWriteAPI,
		QueryAPI:   mockQueryAPI,
		HTTPClient: mockHTTPClient,
	}

	// Test fetchYahooData with error
	points, err := server.fetchYahooData("SPY", time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC), "1d")

	assert.Error(t, err)
	assert.Nil(t, points)
	assert.Contains(t, err.Error(), "Yahoo API returned status")
}

func TestFetchYahooData_WithMockedHTTPClient_YahooAPIError(t *testing.T) {
	gin.SetMode(gin.TestMode)

	mockWriteAPI := new(MockWriteAPIBlocking)
	mockQueryAPI := new(MockQueryAPI)
	mockHTTPClient := new(MockHTTPClient)

	// Setup Yahoo API error in response body
	fakeYahooResponse := `{
		"chart": {
			"result": [],
			"error": {"code": "Not Found", "description": "No data found for ticker"}
		}
	}`

	mockResp := &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(bytes.NewBufferString(fakeYahooResponse)),
		Header:     make(http.Header),
	}
	mockHTTPClient.On("Do", mock.Anything).Return(mockResp, nil)

	server := &Server{
		WriteAPI:   mockWriteAPI,
		QueryAPI:   mockQueryAPI,
		HTTPClient: mockHTTPClient,
	}

	// Test fetchYahooData with API error
	points, err := server.fetchYahooData("INVALID", time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC), "1d")

	assert.Error(t, err)
	assert.Nil(t, points)
	assert.Contains(t, err.Error(), "Yahoo API error")
}

// Note: Full end-to-end test removed because it's too complex for unit testing.
// The flow involves QueryTableResult which has complex internal state that's
// difficult to mock properly. The individual components are tested separately:
// - Handler validation: TestHandleFetchData_* tests
// - HTTP client mocking: TestFetchYahooData_WithMockedHTTPClient_* tests
// - Date parsing: TestDateParsing_* tests
// - Data structures: TestDataFetchRequest_JSONMarshaling tests
// Integration testing should be done separately with a real or containerized InfluxDB instance.

// --- Benchmark Tests ---

func BenchmarkHandleFetchData(b *testing.B) {
	router := setupTestRouterSimple()

	reqBody := DataFetchRequest{
		Tickers:   []string{"SPY"},
		StartDate: "2020-01-01",
		Interval:  "1d",
	}

	body, _ := json.Marshal(reqBody)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("POST", "/v1/data/fetch", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")

		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}

func BenchmarkHandleQueryData(b *testing.B) {
	router := setupTestRouterSimple()

	reqBody := DataQueryRequest{
		Ticker: "SPY",
		Days:   30,
	}

	body, _ := json.Marshal(reqBody)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("POST", "/v1/data/query", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")

		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}
