package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin" // <-- Import Gin
	influxdb2 "github.com/influxdata/influxdb-client-go/v2"
	"github.com/influxdata/influxdb-client-go/v2/api"
	"github.com/influxdata/influxdb-client-go/v2/api/write"
)

// Ticker definitions (REMOVED, will come from API request)

// --- Constants ---
const (
	NUM_WORKERS = 8 // Number of *parallel fetches* per API request
)

// --- HTTPClient Interface ---
// HTTPClient interface allows injecting mock HTTP clients for testing
type HTTPClient interface {
	Do(req *http.Request) (*http.Response, error)
}

// --- Server struct holds all dependencies ---
type Server struct {
	WriteAPI   api.WriteAPIBlocking
	QueryAPI   api.QueryAPI
	HTTPClient HTTPClient
}

// --- Yahoo Finance Structs (Unchanged) ---
type YahooChartResponse struct {
	Chart struct {
		Result []YahooResult `json:"result"`
		Error  interface{}   `json:"error"`
	} `json:"chart"`
}
type YahooResult struct {
	Meta       YahooMeta       `json:"meta"`
	Timestamp  []int64         `json:"timestamp"`
	Indicators YahooIndicators `json:"indicators"`
}
type YahooMeta struct {
	Currency string `json:"currency"`
	Symbol   string `json:"symbol"`
}
type YahooIndicators struct {
	Quote []struct {
		Open   []float64 `json:"open"`
		High   []float64 `json:"high"`
		Low    []float64 `json:"low"`
		Close  []float64 `json:"close"`
		Volume []int64   `json:"volume"`
	} `json:"quote"`
	AdjClose []struct {
		AdjClose []float64 `json:"adjclose"`
	} `json:"adjclose"`
}

// --- API Request/Response Structs ---
type DataFetchRequest struct {
	Tickers   []string `json:"names"`
	StartDate string   `json:"start_date"` // e.g., "2020-01-01"
	Interval  string   `json:"interval"`   // e.g., "1d", "1h", "1m"
}

type DataFetchResponse struct {
	Status  string            `json:"status"`
	Message string            `json:"message"`
	Details map[string]string `json:"details"` // e.g., {"SPY": "251 points written", "MSFT": "No new data"}
}

// --- InfluxDB Configuration (Unchanged) ---
var (
	influxURL    = os.Getenv("INFLUXDB_URL")
	influxToken  = os.Getenv("INFLUXDB_TOKEN")
	influxOrg    = os.Getenv("INFLUXDB_ORG")
	influxBucket = os.Getenv("INFLUXDB_BUCKET")
)

// Global InfluxDB client
var influxClient influxdb2.Client

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	if influxURL == "" || influxToken == "" || influxOrg == "" || influxBucket == "" {
		slog.Error("InfluxDB environment variables not set. Exiting.")
		return
	}

	// Create a single, thread-safe InfluxDB client
	influxClient = influxdb2.NewClient(influxURL, influxToken)
	// Check if the connection is valid
	var influxReady bool
	var err error

	slog.Info("Waiting for InfluxDB to be ready...")
	// Try to connect 10 times over 30 seconds
	for i := 0; i < 10; i++ {
		health, err := influxClient.Health(context.Background())
		// Check if there was no error AND the status is "pass"
		if err == nil && health.Status == "pass" {
			influxReady = true
			break // Success! Exit the loop.
		}

		// Log the warning and wait
		var errMsg string
		if err != nil {
			errMsg = err.Error()
		} else if health != nil {
			errMsg = *health.Message
		}
		slog.Warn("InfluxDB not ready, retrying...", "attempt", i+1, "error", errMsg)
		time.Sleep(3 * time.Second) // Wait 3 seconds before next try
	}

	if !influxReady {
		slog.Error("Failed to connect to InfluxDB after all retries.", "last_error", err)
		return // Exit with code 0 after all retries failed
	}
	// --- End of retry loop ---

	slog.Info("Successfully connected to InfluxDB.")

	// Create Server instance with all dependencies
	server := &Server{
		WriteAPI:   influxClient.WriteAPIBlocking(influxOrg, influxBucket),
		QueryAPI:   influxClient.QueryAPI(influxOrg),
		HTTPClient: &http.Client{Timeout: 10 * time.Second}, // Real HTTP client
	}

	// --- NEW: Start Gin Server ---
	router := gin.Default()
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	// Data endpoints - use server methods
	router.POST("/v1/data/fetch", server.handleFetchData)
	router.POST("/v1/data/query", server.handleQueryData)

	slog.Info("Starting finance-data API server on :8000")
	if err := router.Run(":8000"); err != nil {
		slog.Error("Gin server failed", "error", err)
	}
	defer influxClient.Close()
}

// handleFetchData is the new Gin handler for on-demand fetching
func (s *Server) handleFetchData(c *gin.Context) {
	var req DataFetchRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	if len(req.Tickers) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "No tickers provided"})
		return
	}
	// Default interval to "1d" if not provided
	if req.Interval == "" {
		req.Interval = "1d"
	}

	slog.Info("Handling data fetch request", "tickers", req.Tickers, "interval", req.Interval)

	var wg sync.WaitGroup
	tickerJobs := make(chan string, len(req.Tickers))
	results := make(chan map[string]string, len(req.Tickers))

	// Create worker goroutines
	for i := 0; i < NUM_WORKERS; i++ {
		wg.Add(1)
		// Give each worker access to the server's dependencies
		go s.fetchWorker(i, &wg, tickerJobs, results, req.StartDate, req.Interval)
	}

	// Send jobs
	for _, ticker := range req.Tickers {
		tickerJobs <- ticker
	}
	close(tickerJobs)

	// Wait for all workers to finish
	wg.Wait()
	close(results)

	// Collect results
	finalDetails := make(map[string]string)
	for res := range results {
		for k, v := range res {
			finalDetails[k] = v
		}
	}

	c.JSON(http.StatusOK, DataFetchResponse{
		Status:  "success",
		Message: fmt.Sprintf("Data fetch cycle completed for %d tickers", len(req.Tickers)),
		Details: finalDetails,
	})
}

// fetchWorker processes a single ticker
func (s *Server) fetchWorker(id int, wg *sync.WaitGroup,
	jobs <-chan string, results chan<- map[string]string,
	startDate string, interval string) {

	defer wg.Done()
	for ticker := range jobs {
		slog.Info("Worker processing", "worker_id", id, "ticker", ticker)

		// 1. Find latest timestamp
		latestTime, err := s.getLatestTimestamp(ticker, startDate)
		if err != nil {
			slog.Error("Failed to get latest timestamp", "worker_id", id, "ticker", ticker, "error", err)
			results <- map[string]string{ticker: "Error: " + err.Error()}
			continue
		}

		// 2. Fetch data from Yahoo
		points, err := s.fetchYahooData(ticker, latestTime, interval)
		if err != nil {
			slog.Error("Failed to fetch Yahoo data", "worker_id", id, "ticker", ticker, "error", err)
			results <- map[string]string{ticker: "Error: " + err.Error()}
			continue
		}

		// 3. Write to Influx
		if len(points) > 0 {
			if err := s.WriteAPI.WritePoint(context.Background(), points...); err != nil {
				slog.Error("Failed to write to InfluxDB", "worker_id", id, "ticker", ticker, "error", err)
				results <- map[string]string{ticker: "Error: " + err.Error()}
			}
			results <- map[string]string{ticker: fmt.Sprintf("%d points written", len(points))}
		} else {
			slog.Info("No new data to write", "worker_id", id, "ticker", ticker)
			results <- map[string]string{ticker: "No new data"}
		}
	}
}

// getLatestTimestamp modified to use a default start date if needed
func (s *Server) getLatestTimestamp(ticker string, defaultStartDate string) (time.Time, error) {
	// Parse the provided start date
	defaultStartTime, err := time.Parse("2006-01-02", defaultStartDate)
	if err != nil {
        defaultStartTime, err = time.Parse("20060102", defaultStartDate)
        if err != nil {
            // Fallback if parsing fails (should be validated by client)
            defaultStartTime = time.Now().AddDate(-1, 0, 0) // 1 year ago
        }
	}

	query := fmt.Sprintf(`
        from(bucket: "%s")
          |> range(start: -30d) // Only check recent history
          |> filter(fn: (r) => r._measurement == "stock_prices")
          |> filter(fn: (r) => r.ticker == "%s")
          |> last()
    `, influxBucket, ticker)

	result, err := s.QueryAPI.Query(context.Background(), query)
	if err != nil {
		return defaultStartTime, err
	}

	if result.Next() {
		// We have a record. Use the later of its time or the user's requested start time
		recordTime := result.Record().Time().Add(24 * time.Hour) // +1 day to avoid duplicates
		if recordTime.After(defaultStartTime) {
			return recordTime, nil
		}
	}
	if result.Err() != nil {
		return defaultStartTime, result.Err()
	}

	// No recent record found, use the user's requested start time
	return defaultStartTime, nil
}

// fetchYahooData modified to accept an interval and use injected HTTP client
func (s *Server) fetchYahooData(ticker string, startTime time.Time, interval string) ([]*write.Point, error) {
	start := startTime.Unix()
	end := time.Now().Unix()

	if start > end {
		return nil, nil // Start time is in the future, no data to fetch
	}

	// --- MODIFIED URL ---
	url := fmt.Sprintf(
		"https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d&interval=%s&events=history",
		ticker, start, end, interval,
	)

	// Use the injected HTTP client instead of creating a new one
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create the http request %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

	resp, err := s.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to call Yahoo API: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Yahoo API returned status %s", resp.Status)
	}

	var chartData YahooChartResponse
	if err := json.NewDecoder(resp.Body).Decode(&chartData); err != nil {
		return nil, fmt.Errorf("failed to decode Yahoo JSON: %w", err)
	}

	if chartData.Chart.Error != nil {
		return nil, fmt.Errorf("Yahoo API error: %v", chartData.Chart.Error)
	}

	if len(chartData.Chart.Result) == 0 {
		return nil, fmt.Errorf("no results in Yahoo response for ticker %s", ticker)
	}

	var points []*write.Point
	res := chartData.Chart.Result[0]

	if len(res.Indicators.AdjClose) == 0 || len(res.Indicators.Quote) == 0 {
		return nil, fmt.Errorf("incomplete indicators in Yahoo response for ticker %s", ticker)
	}

	adjCloseData := res.Indicators.AdjClose[0].AdjClose
	quoteData := res.Indicators.Quote[0]

	for i, ts := range res.Timestamp {
		if len(adjCloseData) <= i ||
			len(quoteData.Close) <= i ||
			len(quoteData.Open) <= i ||
			len(quoteData.High) <= i ||
			len(quoteData.Low) <= i ||
			len(quoteData.Volume) <= i {
			slog.Warn("Skipping incomplete data point", "ticker", ticker, "timestamp", ts)
			continue
		}

		p := influxdb2.NewPoint(
			"stock_prices",
			map[string]string{
				"ticker": strings.ReplaceAll(ticker, "-USD", "USDT"),
			},
			map[string]interface{}{
				"open":      quoteData.Open[i],
				"high":      quoteData.High[i],
				"low":       quoteData.Low[i],
				"close":     quoteData.Close[i],
				"adj_close": adjCloseData[i],
				"volume":    quoteData.Volume[i],
			},
			time.Unix(ts, 0),
		)
		points = append(points, p)
	}
	return points, nil
}

// --- Query Data Handler ---

type DataQueryRequest struct {
	Ticker string `json:"ticker"`
	Days   int    `json:"days"`   // Number of days to query
	EndDate string `json:"end_date"` // Optional: end date (defaults to now)
}

type DataPoint struct {
	Time     string  `json:"time"`
	Open     float64 `json:"open"`
	High     float64 `json:"high"`
	Low      float64 `json:"low"`
	Close    float64 `json:"close"`
	Volume   int64   `json:"volume"`
	AdjClose float64 `json:"adj_close"`
}

type DataQueryResponse struct {
	Ticker string      `json:"ticker"`
	Data   []DataPoint `json:"data"`
	Count  int         `json:"count"`
}

func (s *Server) handleQueryData(c *gin.Context) {
	var req DataQueryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	if req.Ticker == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Ticker is required"})
		return
	}

	if req.Days <= 0 {
		req.Days = 252 // Default to 1 year of trading days
	}

	// Build Flux query
	query := fmt.Sprintf(`
		from(bucket: "%s")
		  |> range(start: -%dd)
		  |> filter(fn: (r) => r._measurement == "stock_prices")
		  |> filter(fn: (r) => r.ticker == "%s")
		  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
		  |> sort(columns: ["_time"], desc: false)
	`, influxBucket, req.Days+10, req.Ticker) // +10 days buffer

	slog.Info("Querying InfluxDB", "ticker", req.Ticker, "days", req.Days)

	result, err := s.QueryAPI.Query(context.Background(), query)
	if err != nil {
		slog.Error("Query failed", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Query failed", "details": err.Error()})
		return
	}

	var dataPoints []DataPoint
	for result.Next() {
		record := result.Record()

		dataPoint := DataPoint{
			Time:  record.Time().Format("2006-01-02T15:04:05Z"),
		}

		// Extract values from the pivoted record
		if val, ok := record.ValueByKey("open").(float64); ok {
			dataPoint.Open = val
		}
		if val, ok := record.ValueByKey("high").(float64); ok {
			dataPoint.High = val
		}
		if val, ok := record.ValueByKey("low").(float64); ok {
			dataPoint.Low = val
		}
		if val, ok := record.ValueByKey("close").(float64); ok {
			dataPoint.Close = val
		}
		if val, ok := record.ValueByKey("adj_close").(float64); ok {
			dataPoint.AdjClose = val
		}
		if val, ok := record.ValueByKey("volume").(int64); ok {
			dataPoint.Volume = val
		}

		dataPoints = append(dataPoints, dataPoint)
	}

	if result.Err() != nil {
		slog.Error("Result iteration error", "error", result.Err())
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Query result error", "details": result.Err().Error()})
		return
	}

	// Limit to requested number of days (take last N points)
	if len(dataPoints) > req.Days {
		dataPoints = dataPoints[len(dataPoints)-req.Days:]
	}

	response := DataQueryResponse{
		Ticker: req.Ticker,
		Data:   dataPoints,
		Count:  len(dataPoints),
	}

	slog.Info("Query complete", "ticker", req.Ticker, "points_returned", len(dataPoints))
	c.JSON(http.StatusOK, response)
}
