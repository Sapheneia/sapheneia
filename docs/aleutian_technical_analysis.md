# AleutianLocal: Comprehensive Technical Analysis

**Date:** 2025-12-18
**Analyst:** Claude Sonnet 4.5
**Codebase:** AleutianLocal v1.0 (9,308 lines Go + Python services)
**Purpose:** Critical evaluation of architecture, security, and suitability for financial forecast evaluation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Overall Architecture](#overall-architecture)
3. [Service Boundaries & Architecture](#service-boundaries--architecture)
4. [Data Layer & Storage Architecture](#data-layer--storage-architecture)
5. [Security Implementation](#security-implementation)
6. [Observability Stack](#observability-stack)
7. [Code Quality Assessment](#code-quality-assessment)
8. [Strengths of AleutianLocal](#strengths-of-aleutianlocal)
9. [Weaknesses & Technical Concerns](#weaknesses--technical-concerns)
10. [Fit for Financial Forecast Evaluation](#fit-for-financial-forecast-evaluation)
11. [Alternative Approaches](#alternative-approaches)
12. [Recommendations & Priority Actions](#recommendations--priority-actions)

---

## Executive Summary

**AleutianLocal** is a **privacy-first, self-hosted AI platform** designed as a secure enterprise intelligence appliance. It combines RAG (Retrieval-Augmented Generation), multi-backend LLM support, and built-in Data Loss Prevention (DLP) into a containerized microservices architecture.

### Key Findings

✅ **Strengths:**
- Excellent architectural separation of concerns
- Multi-backend LLM support (Ollama, OpenAI, Claude, local models)
- Comprehensive observability (OpenTelemetry, InfluxDB, Jaeger)
- Privacy by design with embedded policy engine
- Good foundation for forecast evaluation (TimesFM integration, trading strategy execution)

❌ **Critical Weaknesses:**
- **No authentication/authorization** - Services assume internal-only network access
- **Hardcoded secrets** in code (development artifacts in production)
- **WebSocket security issues** - CORS always returns true, CSRF vulnerable
- **Minimal test coverage** (~0.16% on Go services)
- **Missing backtesting framework** - Single-point evaluation only

### Production Readiness: **65%**

| Category | Score | Notes |
|----------|-------|-------|
| Architecture | 90% | Clean microservices, modular design |
| Security | 40% | Critical gaps: no auth, hardcoded secrets |
| Testing | 20% | 15 Go test files for 9,300 LOC |
| Documentation | 70% | Good README, sparse code comments |
| Observability | 85% | OpenTelemetry on all handlers |
| Financial Evaluation | 75% | Good foundation, missing backtesting |

**Verdict:** Strong technical foundation with **critical security gaps**. Suitable for internal use, but requires significant hardening for public or multi-tenant deployment.

---

## 1. Overall Architecture

### Project Identity & Purpose

AleutianLocal is a **self-contained microservices system** that bridges proprietary data with modern LLMs while maintaining data sovereignty. The core philosophy:

- **Privacy by design** - Offline-first, data never leaves infrastructure unless explicit
- **Opinionated production-ready security** - Policies compiled into binary
- **Multi-backend LLM support** - Ollama, OpenAI, Anthropic, local Llama.cpp, HuggingFace
- **Institutional memory** - Vector DB (Weaviate) for semantic search
- **Autonomous agent capabilities** - Code analysis, RAG pipelines

### Technology Stack

```
Backend:         Go 1.25.3 (9,308 lines across services)
Web Framework:   Gin-Gonic (REST HTTP router with middleware)
Vector DB:       Weaviate v1.33.0 (semantic search, document ingestion)
Time Series DB:  InfluxDB 2.x (evaluation metrics, financial data)
Orchestration:   Podman Compose (containerized microservices)
LLM Backends:    Ollama, OpenAI, Anthropic Claude, local Llama.cpp, HuggingFace
RAG Engine:      Python FastAPI with multiple pipelines
Observability:   OpenTelemetry (Jaeger, Prometheus, Loki)
CLI Tool:        Cobra (command-based with deep configuration)
```

### Code Metrics

```
Go Codebase:          ~9,300 lines
Handler Layer:         2,772 lines across 14 files
Go Test Files:         15 files (~0.16% coverage ratio)
Python Test Files:     1,890+ files (RAG/embeddings highly tested)
Configuration:         40+ environment variables
Docker Compose:        15 services defined
```

---

## 2. Service Boundaries & Architecture

### Microservices Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI Application (Cobra-based)                                  │
│  - aleutian stack start/stop/destroy                            │
│  - aleutian ask [question] → RAG                                │
│  - aleutian populate vectordb [path]                            │
│  - aleutian evaluate [--ticker SPY --model model-id]            │
│  - aleutian trace [--codebase path] → Agent                     │
│  - aleutian pull [model-id] → Download & cache                  │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │  Orchestrator Service │ (Go + Gin, Port 12210)
         │  - Central Router     │
         │  - Policy Engine      │
         │  - Handler Layer      │
         └───────────┬───────────┘
         ┌───────────┴───────────────────────────────┐
         │                                           │
    ┌────▼─────┐  ┌──────────────┐  ┌───────────┐
    │Weaviate   │  │InfluxDB      │  │ RAG Engine│ (Python FastAPI)
    │Vector DB  │  │Time Series   │  │Pipelines  │
    │Port 12127 │  │Port 12130    │  │Port 12125 │
    │(Search)   │  │(Metrics)     │  │(Python)   │
    └──────────┘  └──────────────┘  └───────────┘
         │
    ┌────▼──────────────────────────────────┐
    │  LLM Backends (Environment Selected)  │
    ├───────────────────────────────────────┤
    │- Ollama (Port 11434)                  │
    │- OpenAI (https://api.openai.com)      │
    │- Anthropic/Claude (https://api...)    │
    │- Local Llama.cpp (Port 8080)          │
    │- HuggingFace TGI/vLLM                 │
    └───────────────────────────────────────┘
         │
    ┌────▼──────────────────────────────────┐
    │  Auxiliary Services                   │
    ├───────────────────────────────────────┤
    │- Embedding Server (Port 12126)        │
    │- GGUF Converter (Port 12140)          │
    │- OTel Collector (Port 4317)           │
    │- Trading Service / Sapheneia          │
    │- Forecast Services (TimesFM, etc)     │
    └───────────────────────────────────────┘
```

### Orchestrator Responsibilities

The **Orchestrator** (Go service, port 12210) is the central router for all operations:

1. **Public-facing REST API** - Gin HTTP router
2. **Health checks** - Service status monitoring
3. **Session management** - Conversation tracking
4. **Document ingestion** - With policy scanning, chunking, embedding, Weaviate storage
5. **Direct chat** - Policy-gated LLM interactions
6. **RAG orchestration** - Proxy to Python RAG engine
7. **WebSocket chat** - Real-time chat with session tracking
8. **Time series forecasting** - Dynamic model routing (TimesFM, Chronos, etc.)
9. **Trading signal generation** - Multi-model evaluation
10. **Agent step execution** - Autonomous code analysis
11. **Weaviate admin** - Backup, delete, schema management
12. **Policy enforcement** - Embedded classification engine
13. **LLM client abstraction** - Multi-backend support

### Handler Organization (14 Handlers)

| Handler | File | Purpose | Lines |
|---------|------|---------|-------|
| `chat.go` | 156 | Direct chat with policy scanning | Critical path |
| `websocket.go` | 398 | Real-time WebSocket chat | Most complex |
| `documents.go` | 287 | Document ingestion pipeline | I/O heavy |
| `rag.go` | 98 | RAG pipeline orchestration | Proxy |
| `timeseries.go` | 243 | Forecast routing | Financial core |
| `trading.go` | 122 | Trading signal generation | Financial core |
| `evaluator.go` | 357 | Full evaluation pipeline | **Financial critical** |
| `agent.go` | 145 | Agent step execution | Autonomous |
| `models.go` | 98 | Model pulling (HuggingFace) | Downloads |
| `sessions.go` | 67 | Session CRUD | State mgmt |
| `memory.go` | 89 | Conversation memory | State mgmt |
| `session_summary.go` | 112 | Summary generation | LLM call |
| `weaviate_admin.go` | 234 | Vector DB admin ops | Admin |
| `misc.go` | 366 | Health checks, misc | Utilities |

**Critical Observation:** The `evaluator.go` handler (357 lines) is the **core of the financial evaluation framework** and has **no test coverage**.

### Internal Packages

```
internal/policy_engine/          - Embedded DLP with compiled regex patterns
internal/policy_engine/enforcement/ - Embedded YAML policy (baked into binary)
services/llm/                    - Multi-backend LLM abstraction
services/orchestrator/datatypes/ - Type definitions & schemas
services/orchestrator/routes/    - Gin route setup
cmd/aleutian/                    - CLI entry point
cmd/aleutian/config/             - Configuration loader
```

---

## 3. Data Layer & Storage Architecture

### Multi-Store Pattern

AleutianLocal uses a **multi-store approach** optimized for different data types:

#### 1. Weaviate (Vector Database)

```
Purpose:    Semantic search for RAG pipelines
Schema:     Document collection
Fields:     parent_source, chunk_content, data_space,
            version_tag, session_id, ingested_at
Port:       12127 (external), 8080 (internal)
Failover:   Gracefully degrades if unavailable (lightweight mode)
Usage:      Session-aware filtering (global docs vs. session-specific)
```

**Schema Example:**
```json
{
  "class": "Document",
  "properties": [
    {"name": "parent_source", "dataType": ["text"]},
    {"name": "chunk_content", "dataType": ["text"]},
    {"name": "data_space", "dataType": ["text"]},
    {"name": "version_tag", "dataType": ["text"]},
    {"name": "session_id", "dataType": ["text"]},
    {"name": "ingested_at", "dataType": ["date"]}
  ],
  "vectorizer": "none"  // External embedding service
}
```

#### 2. InfluxDB (Time Series)

```
Purpose:        Evaluation metrics, financial OHLC data
Bucket:         financial-data (configurable via env)
Measurements:   forecast_evaluations, stock_prices
Tags:           ticker, model, evaluation_date, run_id,
                forecast_horizon, strategy_type
Fields:         forecast_price, current_price, action, size,
                value, available_cash, position_after
Port:           12130 (external), 8086 (internal)
Auth:           Token-based (fallback: your_super_secret_admin_token)
```

**Example Point:**
```go
influxdb2.NewPointWithMeasurement("forecast_evaluations").
    AddTag("ticker", "SPY").
    AddTag("model", "google/timesfm-2.0-500m-pytorch").
    AddTag("evaluation_date", "20250118").
    AddTag("run_id", "abc123").
    AddTag("forecast_horizon", "1").
    AddTag("strategy_type", "threshold").
    AddField("forecast_price", 580.0).
    AddField("current_price", 575.0).
    AddField("action", "BUY").
    AddField("size", 10.0).
    AddField("value", 5750.0).
    AddField("available_cash", 44250.0).
    AddField("position_after", 110.0).
    SetTime(time.Now())
```

#### 3. Local File System (Models Cache)

```
Path:     ./models_cache (mounted volume)
Purpose:  HuggingFace model caching (~20GB+)
Sharing:  Shared across services via Podman volumes
```

#### 4. Podman Secrets

```
Secrets:     anthropic_api_key, openai_api_key, aleutian_hf_token
Location:    /run/secrets/ (read at container runtime)
Override:    Environment variables take precedence
```

### Data Flow for Forecast Evaluation

```
┌──────────────────────────────────────────────────────────────┐
│ 1. CLI Command                                               │
│    ./aleutian evaluate --ticker SPY --model timesfm-2.0      │
└────────────────────┬─────────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────────┐
│ 2. Evaluator.RunEvaluation()                                 │
│    For each ticker/model:                                    │
│      a. GetCurrentPrice() → Query InfluxDB for last close    │
│      b. CallForecastService() → POST /v1/timeseries/forecast │
│      c. For each forecast horizon (1-20):                    │
│         - CallTradingService() → POST /trading/execute       │
│         - Update portfolio state (position, cash)            │
│         - StoreResult() → Write to InfluxDB                  │
└────────────────────┬─────────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────────┐
│ 3. InfluxDB Storage                                          │
│    Measurement: forecast_evaluations                         │
│    Tags: ticker=SPY, model=timesfm-2.0, run_id=abc123        │
│    Fields: forecast_price, action, size, position_after      │
└──────────────────────────────────────────────────────────────┘
```

### Key Schemas & Data Models

```go
// Evaluation Configuration
type EvaluationConfig struct {
    Tickers         []TickerInfo
    Models          []string
    EvaluationDate  string  // "20250117"
    RunID           string
    StrategyType    string  // "threshold", "return", "quantile"
    StrategyParams  map[string]interface{}
    ContextSize     int     // Historical window (e.g., 252 days)
    HorizonSize     int     // Forecast days (e.g., 20 days)
    InitialCapital  float64
    InitialPosition float64
    InitialCash     float64
}

// Evaluation Result (stored in InfluxDB)
type EvaluationResult struct {
    Ticker          string
    Model           string
    EvaluationDate  string
    RunID           string
    ForecastHorizon int
    StrategyType    string
    ForecastPrice   float64
    CurrentPrice    float64
    Action          string  // "buy", "sell", "hold"
    Size            float64
    Value           float64
    Reason          string
    AvailableCash   float64
    PositionAfter   float64
    Stopped         bool
    ThresholdValue  float64
    ExecutionSize   float64
    Timestamp       time.Time
}

// Forecast Result (from service)
type ForecastResult struct {
    Name     string    `json:"name"`
    Forecast []float64 `json:"forecast"`  // 20 values
    Message  string    `json:"message"`
}

// Trading Signal Response (from Sapheneia)
type TradingSignalResponse struct {
    Action        string  `json:"action"`
    Size          float64 `json:"size"`
    Value         float64 `json:"value"`
    Reason        string  `json:"reason"`
    AvailableCash float64 `json:"available_cash"`
    PositionAfter float64 `json:"position_after"`
    Stopped       bool    `json:"stopped"`
}
```

---

## 4. Security Implementation

### Authentication Mechanisms

#### 1. Policy Engine (Embedded DLP)

**Type:** Regex-based data classification at runtime
**Coverage:** API keys, PII (SSN, credit cards), secrets (AWS keys, DB passwords), custom patterns
**Implementation:**
- Embedded YAML patterns **baked into binary** at compile time (immutable)
- PolicyEngine loads patterns, compiles regex, sorts by priority
- Two modes:
  - `ClassifyData()` - Quick boolean check
  - `ScanFileContent()` - Detailed findings with line-level matches

**Usage Points:**
```go
// 1. HandleDirectChat() - Scans user messages before LLM call
findings := pe.ScanFileContent(req.Message)
if len(findings) > 0 {
    slog.Warn("Policy violation detected in chat message")
    c.JSON(http.StatusForbidden, gin.H{"error": "Message contains sensitive data"})
    return
}

// 2. HandleChatWebSocket() - Scans uploaded files for approval/block
classification := pe.ClassifyData(fileContent)
if classification.HighestClassification != "PUBLIC" {
    ws.WriteJSON(gin.H{"error": "File contains restricted content"})
    return
}

// 3. Document ingestion - Prevents secret-laden content from VectorDB
if pe.ClassifyData(chunkContent).HighestClassification == "SECRET" {
    slog.Error("Secret detected in chunk, skipping ingestion")
    continue
}
```

**Policy Pattern Example:**
```yaml
ClassificationPatterns:
  - Name: "SECRET"
    Priority: 1  # Highest
    Patterns:
      - Id: "aws_access_key"
        Pattern: "AKIA[0-9A-Z]{16}"
        Confidence: 0.99
      - Id: "private_key"
        Pattern: "-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"
        Confidence: 1.0

  - Name: "CONFIDENTIAL"
    Priority: 2
    Patterns:
      - Id: "api_key"
        Pattern: "api[_-]?key['\"]?\\s*[:=]\\s*['\"]?[a-zA-Z0-9]{20,}"
        Confidence: 0.85

  - Name: "PII"
    Priority: 3
    Patterns:
      - Id: "ssn"
        Pattern: "\\d{3}-\\d{2}-\\d{4}"
        Confidence: 0.95
      - Id: "credit_card"
        Pattern: "\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}"
        Confidence: 0.90

  - Name: "PUBLIC"
    Priority: 999  # Default fallback
```

**Strengths:**
- ✅ Embedded in binary (cannot be tampered at runtime)
- ✅ Multi-level classification (SECRET > CONFIDENTIAL > PII > PUBLIC)
- ✅ Line-level scanning with match capture
- ✅ Confidence scores for each pattern

**Weaknesses:**
- ❌ Patterns are static (no dynamic rule updates without recompilation)
- ❌ Regex-based (can be bypassed with obfuscation)
- ❌ No machine learning-based anomaly detection
- ❌ Logs detailed scan findings (revealing what was blocked → information leakage)

#### 2. API-Level Security

**Current State:**
```go
// NO explicit API key validation
// NO JWT token verification
// NO session authentication

// Relies ENTIRELY on Podman network isolation:
// - Services communicate via internal network (aleutian-network)
// - External access only via exposed ports (12210, 12126, etc.)
```

**Service-to-Service Auth:**
```go
// Trading/Forecast services use Bearer tokens
if apiKey := os.Getenv("SAPHENEIA_TRADING_API_KEY"); apiKey != "" {
    httpReq.Header.Set("Authorization", "Bearer "+apiKey)
}

// Default: Uses hardcoded key from podman-compose.yml
apiKey = "default_trading_api_key_please_change"
```

**Podman Secrets:**
```go
// Read from /run/secrets/ at runtime
func readSecret(secretName string) (string, error) {
    secretPath := fmt.Sprintf("/run/secrets/%s", secretName)
    data, err := os.ReadFile(secretPath)
    if err != nil {
        return "", err
    }
    return strings.TrimSpace(string(data)), nil
}

// Example usage:
anthropicKey := readSecret("anthropic_api_key")
```

#### 3. Input Validation

**Current State:**
```go
// Minimal validation - relies on JSON binding only
var req DirectChatRequest
if err := c.BindJSON(&req); err != nil {
    c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request body"})
    return
}

// NO length checks
// NO struct tag validation (go-playground/validator imported but unused)
// NO rate limiting
// NO request size limits (except WebSocket buffers: 10MB)
```

**Missing Patterns:**
```go
// SHOULD have:
type DirectChatRequest struct {
    Message string `json:"message" validate:"required,min=1,max=10000"`
    Stream  bool   `json:"stream"`
}

// With validation:
validate := validator.New()
if err := validate.Struct(req); err != nil {
    // Return validation errors
}
```

#### 4. Secret Management

**Environment Variables as Primary Store:**
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
ALEUTIAN_HF_TOKEN=hf_...
INFLUXDB_TOKEN=your_super_secret_admin_token  # ⚠️ HARDCODED FALLBACK
```

**Critical Issue - Hardcoded Fallback:**
```go
// evaluator.go:306
token := os.Getenv("INFLUXDB_TOKEN")
if token == "" {
    // ⚠️ DANGEROUS: Fallback to hardcoded token
    token = "your_super_secret_admin_token"
}
```

**Impact:** If environment variable is not set, **system uses default token**, which is:
- Committed to version control
- Visible in code
- Shared across all deployments

#### 5. Authorization Patterns

**Resource Ownership:**
```go
// ❌ NOT implemented
// No user_id checks in queries
// No WHERE user_id = ? clauses
// Anyone can access any session/document

// Example of what's MISSING:
// Query: SELECT * FROM sessions WHERE session_id = ? AND user_id = ?
// Current: SELECT * FROM sessions WHERE session_id = ?
```

**Session-Aware Filtering:**
```go
// ✅ Partial implementation in Weaviate queries
where := map[string]interface{}{
    "operator": "And",
    "operands": []map[string]interface{}{
        {
            "path":     []string{"session_id"},
            "operator": "Equal",
            "valueText": sessionID,
        },
    },
}

// BUT: No user ownership check
// Anyone with session_id can access the session
```

**No RBAC:**
- No role-based access control
- No admin vs. user distinction
- No resource-level permissions

#### 6. WebSocket Security

**Critical Vulnerability:**
```go
// websocket.go:52
upgrader := websocket.Upgrader{
    ReadBufferSize:  10 * 1024 * 1024,  // 10MB
    WriteBufferSize: 10 * 1024 * 1024,  // 10MB
    CheckOrigin: func(r *http.Request) bool {
        return true  // ⚠️ ALLOWS ALL ORIGINS (CSRF VULNERABLE)
    },
}
```

**Impact:**
- ✅ **ALLOWS**: Malicious website can connect to WebSocket
- ✅ **ALLOWS**: Cross-site request forgery (CSRF) attacks
- ✅ **ALLOWS**: Session hijacking if session_id is guessable

**Should be:**
```go
CheckOrigin: func(r *http.Request) bool {
    origin := r.Header.Get("Origin")
    allowedOrigins := []string{
        "http://localhost:3000",
        "http://localhost:8080",
        os.Getenv("ALLOWED_ORIGIN"),
    }
    for _, allowed := range allowedOrigins {
        if origin == allowed {
            return true
        }
    }
    return false
},
```

### Security Summary Table

| Category | Implementation | Status | Risk Level |
|----------|----------------|--------|------------|
| Authentication | None (network isolation only) | ❌ Missing | **CRITICAL** |
| Authorization | No RBAC, no user isolation | ❌ Missing | **CRITICAL** |
| Input Validation | JSON binding only, no length checks | ⚠️ Weak | **HIGH** |
| Secret Management | Env vars + hardcoded fallbacks | ⚠️ Weak | **HIGH** |
| Policy Engine | Regex-based DLP, embedded patterns | ✅ Good | **LOW** |
| WebSocket CORS | Always returns true | ❌ Vulnerable | **CRITICAL** |
| API Rate Limiting | None | ❌ Missing | **MEDIUM** |
| Session Management | UUID-based, no expiration | ⚠️ Weak | **MEDIUM** |

**Overall Security Grade: D+ (40%)**

---

## 5. Observability Stack

### OpenTelemetry Integration

#### 1. Tracing Setup

```go
// Exporter: OTLP gRPC to Jaeger
exporter, err := otlptracegrpc.New(
    ctx,
    otlptracegrpc.WithEndpoint(os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
    otlptracegrpc.WithInsecure(),  // No TLS in dev
)

// Tracer Provider
tp := trace.NewTracerProvider(
    trace.WithSampler(trace.AlwaysSample()),  // 100% sampling
    trace.WithBatcher(exporter),              // Batch for performance
    trace.WithResource(resource.NewWithAttributes(
        semconv.SchemaURL,
        semconv.ServiceName("orchestrator-service"),
    )),
)
otel.SetTracerProvider(tp)
```

**Span Hierarchy Example:**
```
HandleDirectChat (span_id: abc123)
├─ PolicyEngine.ScanFileContent (span_id: def456)
│  └─ Regex pattern matching (internal)
├─ LLMClient.Chat (span_id: ghi789)
│  └─ Ollama HTTP POST (span_id: jkl012)
│     └─ Model inference (external)
└─ Response write (internal)
```

**Instrumentation Points:**
```go
// 1. Gin middleware (auto-instruments all HTTP endpoints)
router.Use(otelgin.Middleware("orchestrator-service"))

// 2. Manual span creation in handlers
ctx, span := tracer.Start(c.Request.Context(), "HandleDirectChat")
defer span.End()

// 3. Error recording
if err != nil {
    span.RecordError(err)
    span.SetStatus(codes.Error, err.Error())
}

// 4. Attribute tagging
span.SetAttributes(
    attribute.String("ticker", ticker),
    attribute.String("model", model),
    attribute.Int("horizon", horizonSize),
)
```

#### 2. Logging Strategy

**Format:** Structured JSON via `log/slog`

```go
// Info logging
slog.Info("Websocket client connected",
    "session_id", sessionID,
    "remote_addr", ws.RemoteAddr())

// Error logging with context
slog.Error("LLMClient.Chat failed",
    "backend", "ollama",
    "error", err,
    "model", modelName)

// Warning logging
slog.Warn("Policy violation detected",
    "classification", "CONFIDENTIAL",
    "line_number", finding.LineNumber,
    "pattern_id", finding.PatternID)
```

**Output Destination:**
- stdout → Container logs
- Collected by Podman
- Forwarded to Loki (via OTel Collector)

**Concerns:**
```go
// ⚠️ Logging may leak sensitive data:
slog.Info("Received chat request", "message", req.Message)  // Could log PII
slog.Error("InfluxDB query failed", "query", query)         // Could log secrets

// Should redact:
slog.Info("Received chat request", "message_length", len(req.Message))
```

#### 3. Metrics

**Current State:**
- OpenTelemetry SDK initialized
- No explicit Prometheus metrics in Go services
- RAG engine (Python) has counters:
  ```python
  rag_requests_total = Counter('rag_requests_total',
      'Total RAG requests',
      ['pipeline', 'status'])
  ```

**Missing Metrics:**
```go
// SHOULD have:
// - HTTP request duration (histogram)
// - Active WebSocket connections (gauge)
// - InfluxDB query latency (histogram)
// - LLM token usage (counter)
// - Policy engine violations (counter)
// - Evaluation runs per ticker (counter)
```

#### 4. Observability Stack Services

```yaml
# otel-collector (Port 4317)
# - Receives traces/metrics/logs
# - Exports to Jaeger, Prometheus, Loki

otel-collector:
  image: otel/opentelemetry-collector-contrib:latest
  ports:
    - "4317:4317"   # OTLP gRPC
    - "4318:4318"   # OTLP HTTP
    - "8889:8889"   # Prometheus exporter
    - "14250:14250" # Jaeger gRPC

# jaeger (Port 16686)
# - Distributed tracing UI
# - Accepts OTLP traces from collector

aleutian-jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"  # UI
  environment:
    - COLLECTOR_OTLP_ENABLED=true

# prometheus (Port 9090)
# - Metrics scraping and storage
# - Queries from Grafana

prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./observability/prometheus.yaml:/etc/prometheus/prometheus.yaml

# grafana (Port 3000)
# - Visualization dashboards
# - Queries Prometheus + Jaeger

grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  volumes:
    - ./observability/grafana/provisioning:/etc/grafana/provisioning
```

### Observability Summary

| Component | Status | Coverage | Grade |
|-----------|--------|----------|-------|
| Tracing | ✅ Implemented | All HTTP handlers | A |
| Logging | ✅ Implemented | Structured JSON | B+ |
| Metrics | ⚠️ Partial | RAG only, missing Go metrics | C |
| Dashboards | ✅ Provisioned | Grafana + Jaeger UI | B |
| Alerting | ❌ Missing | No alerts configured | F |

**Overall Observability Grade: B (75%)**

---

## 6. Code Quality Assessment

### Strengths

#### 1. Clean Separation of Concerns

```
✅ Handlers isolated by feature:
   - chat.go → Direct chat with LLM
   - websocket.go → Real-time WebSocket chat
   - documents.go → Document ingestion pipeline
   - timeseries.go → Forecast routing
   - evaluator.go → Evaluation framework

✅ Datatypes in separate package:
   - evaluator.go → EvaluationConfig, EvaluationResult
   - agent.go → AgentRequest, AgentResponse
   - rag.go → RAGRequest, RAGResponse

✅ LLM abstraction with interface:
   type LLMClient interface {
       Chat(ctx, messages) (string, error)
   }
   - OllamaClient
   - OpenAIClient
   - AnthropicClient
   - LlamaCppClient

✅ Policy engine as independent module:
   - policy_engine/policy_engine.go
   - policy_engine/enforcement/data_classification_patterns.yaml
```

#### 2. Error Handling

```go
// ✅ Consistent pattern: check → log → return
if err := c.BindJSON(&req); err != nil {
    slog.Error("Failed to parse", "error", err)
    c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request body"})
    return
}

// ✅ Error wrapping with context
if err != nil {
    return fmt.Errorf("forecast failed for %s: %w", ticker, err)
}

// ✅ Proper defer for cleanup
resp, err := httpClient.Do(req)
if err != nil {
    return nil, err
}
defer resp.Body.Close()  // ✅ Guaranteed cleanup
```

#### 3. Configuration Management

```go
// ✅ Comprehensive config loader
type AleutianConfig struct {
    ProfileMode string
    ProfilePath string
    // Auto-detected:
    RAMTotalGB        float64
    HasExternalDrive  bool
    PodmanMachineName string
    PodmanMachineRAM  int
    // User-specified:
    CustomModelCachePath string
    LLMBackend           string
}

// ✅ Environment variable overrides
func Load() error {
    config.LLMBackend = getEnvOrDefault("LLM_BACKEND_TYPE", "ollama")
    config.RAMTotalGB = detectRAM()
    config.HasExternalDrive = detectExternalDrives()
    // ...
}

// ✅ Dynamic profile selection
func SelectProfile() string {
    if config.RAMTotalGB < 16 {
        return "standard"
    } else if config.RAMTotalGB < 32 {
        return "performance"
    }
    return "ultra"
}
```

#### 4. Type Safety

```go
// ✅ Struct-based request/response
type DirectChatRequest struct {
    Message string `json:"message"`
    Stream  bool   `json:"stream"`
}

type DirectChatResponse struct {
    Reply string `json:"reply"`
}

// ✅ Explicit JSON tags
type EvaluationResult struct {
    Ticker string `json:"ticker"`
    Model  string `json:"model"`
    // ...
}

// ✅ Interface-based polymorphism
type LLMClient interface {
    Chat(context.Context, []LLMMessage) (string, error)
}
```

#### 5. Observability Integration

```go
// ✅ Every handler starts a span
ctx, span := tracer.Start(c.Request.Context(), "HandleDirectChat")
defer span.End()

// ✅ Structured logging
slog.Info("Evaluating", "ticker", ticker, "model", model)

// ✅ Error recording in spans
if err != nil {
    span.RecordError(err)
    span.SetStatus(codes.Error, err.Error())
}
```

### Weaknesses & Technical Debt

#### 1. Test Coverage (CRITICAL)

```
📊 Code Coverage Analysis:

Go Codebase:          9,308 lines
Go Test Files:        15 files
Test Coverage Ratio:  ~0.16%

Test Files:
✅ cmd/aleutian/cmd_chat_test.go         (38 lines)
✅ cmd/aleutian/cmd_data_test.go         (104 lines)
✅ cmd/aleutian/cmd_policy_test.go       (143 lines)
✅ cmd/aleutian/cmd_stack_test.go        (29 lines)
✅ cmd/aleutian/cmd_timeseries_test.go   (45 lines)
✅ cmd/aleutian/helpers_test.go          (58 lines)
... 9 more test files

❌ NO TESTS FOR:
- services/orchestrator/handlers/evaluator.go (357 lines) ⚠️ CRITICAL
- services/orchestrator/handlers/websocket.go (398 lines)
- services/orchestrator/handlers/documents.go (287 lines)
- services/orchestrator/handlers/timeseries.go (243 lines)
- services/orchestrator/handlers/trading.go (122 lines)
- services/llm/*.go (LLM clients)

Python Side (RAG/Embeddings):
Test Files: 1,890+ files
Coverage:   Extensive (60-80% estimated)
```

**Impact:**
- ✅ **CLI commands** are tested → Good user-facing reliability
- ❌ **Core handlers** untested → High risk of regression bugs
- ❌ **Evaluator logic** untested → Financial calculations could be wrong
- ❌ **LLM clients** untested → Backend switching could break silently

**What's Missing:**
```go
// evaluator_test.go (DOES NOT EXIST)
func TestEvaluateTickerModel(t *testing.T) {
    // Mock forecast service
    // Mock trading service
    // Assert InfluxDB writes
}

func TestGetCurrentPrice(t *testing.T) {
    // Mock InfluxDB query
    // Test error handling
}

// websocket_test.go (DOES NOT EXIST)
func TestWebSocketIngestion(t *testing.T) {
    // Mock Weaviate
    // Test file upload flow
}
```

#### 2. Input Validation (HIGH PRIORITY)

```go
// ❌ NO validation beyond JSON parsing
type DirectChatRequest struct {
    Message string `json:"message"`  // No min/max length
    Stream  bool   `json:"stream"`
}

// ⚠️ go-playground/validator imported but UNUSED
import "github.com/go-playground/validator/v10"  // Not used anywhere

// SHOULD have:
type DirectChatRequest struct {
    Message string `json:"message" validate:"required,min=1,max=10000"`
    Stream  bool   `json:"stream"`
}

validate := validator.New()
if err := validate.Struct(req); err != nil {
    c.JSON(http.StatusBadRequest, gin.H{"errors": err.Error()})
    return
}
```

**Missing Validations:**
- ❌ String length limits (could cause memory exhaustion)
- ❌ Ticker symbol format (e.g., uppercase, alphanumeric)
- ❌ Model name whitelist (accepts any string)
- ❌ Date format validation (YYYYMMDD expected but not enforced)
- ❌ Numeric range checks (e.g., context_size > 0)

#### 3. Error Messages Leak Details

```go
// ⚠️ Exposes internal error details to client
c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})

// Examples of leaked info:
// "failed to connect to weaviate: dial tcp 127.0.0.1:8080: connection refused"
// "InfluxDB query failed: unauthorized access to bucket financial-data"
// "LLM backend error: Ollama model llama2:7b not found"

// SHOULD return generic message:
c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
slog.Error("Detailed error", "error", err)  // Log details internally
```

**Impact:**
- Information leakage (reveals internal architecture)
- Aids attackers in reconnaissance
- May expose credentials or tokens in error messages

#### 4. Hardcoded Values

```go
// ⚠️ Port numbers scattered across code
orchestratorURL := "http://localhost:12210"
tradingURL := "http://localhost:12132"
dataServiceURL := "http://localhost:8001"

// ⚠️ Model IDs in switch statement (timeseries.go:156)
switch req.Model {
case "google/timesfm-1.0-200m", "google/timesfm-2.0-500m-pytorch":
    return handleTimesFM20Forecast(c, req)
case "amazon/chronos-t5-tiny", "amazon/chronos-t5-mini":
    return handleChronosForecast(c, req)
// ... 10 more cases
}

// ⚠️ Fallback tokens (evaluator.go:306)
token := "your_super_secret_admin_token"

// SHOULD be:
// - Ports from environment variables with defaults
// - Model registry/config file
// - NO fallback tokens
```

#### 5. Timeout Configuration

```go
// ⚠️ Very long timeouts
httpClient := &http.Client{Timeout: 5 * time.Minute}  // Evaluator
httpClient := &http.Client{Timeout: 60 * time.Second} // Anthropic

// ⚠️ No context deadlines propagated
req, _ := http.NewRequestWithContext(ctx, "POST", url, body)
// ctx has no deadline set

// SHOULD have:
ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
defer cancel()
```

**Impact:**
- Could hang indefinitely waiting for slow services
- Resource exhaustion (goroutines blocked)
- Poor user experience (no timeout feedback)

#### 6. Resource Management

```go
// ⚠️ WebSocket buffers: 10MB each (read + write = 20MB per connection)
upgrader := websocket.Upgrader{
    ReadBufferSize:  10 * 1024 * 1024,
    WriteBufferSize: 10 * 1024 * 1024,
}

// ⚠️ No limit on document chunk count
for i := 0; i < totalChunks; i++ {
    chunks = append(chunks, chunk)  // Unbounded growth
}

// ⚠️ InfluxDB client not always closed
storage, err := NewInfluxDBStorage()
defer storage.Close()  // Only if function returns normally

// SHOULD use buffered channels:
chunkChan := make(chan string, 100)  // Limit in-flight chunks
```

#### 7. Dependency Management

```
go.mod shows 138 total dependencies (incl. transitive)

⚠️ Pinned versions:
- github.com/weaviate/weaviate v1.33.0-rc.1 (release candidate!)
- github.com/influxdata/influxdb-client-go/v2 v2.15.1
- github.com/gin-gonic/gin v1.10.0

⚠️ Open-ended versions:
- Many transitive deps with no version constraints

🔍 Security vulnerabilities:
- Run: go list -m -u all | grep -v indirect
- Recommended: Snyk or Dependabot scanning
```

#### 8. Documentation

```go
// ⚠️ Large functions lack docstrings
func HandleChatWebSocket(/* 12 parameters */) gin.HandlerFunc {
    return func(c *gin.Context) {
        // 398 lines of code
        // NO function-level comment
    }
}

// ⚠️ Complex logic without inline comments
for _, message := range messages {
    if message.Role == "user" {
        pe.ScanFileContent(message.Content)
        // What happens if scan fails? No comment.
    }
}

// ✅ Good example (rare):
// PolicyEngine scans content against embedded classification patterns.
// Returns detailed findings including line numbers and matched patterns.
func (pe *PolicyEngine) ScanFileContent(content string) []Finding {
    // ...
}
```

**Documentation Coverage:**
- ✅ README: Comprehensive (installation, usage, architecture)
- ⚠️ Code-level: Sparse (function docstrings ~20%)
- ❌ API documentation: None (no OpenAPI/Swagger spec)
- ❌ Architecture diagrams: None (no official diagrams)

### Code Quality Summary

| Category | Grade | Rationale |
|----------|-------|-----------|
| Architecture | A- | Clean separation, modular design |
| Error Handling | B+ | Consistent pattern, but leaks details |
| Configuration | A | Flexible, hardware-aware, defaults |
| Type Safety | A | Strong typing, interfaces |
| Observability | B+ | OTel on all handlers, structured logs |
| **Testing** | **D** | **15 test files for 9,308 LOC** |
| **Input Validation** | **C-** | **JSON binding only, no rules** |
| **Security** | **D+** | **No auth, hardcoded secrets** |
| Documentation | C+ | Good README, sparse code comments |
| Dependency Mgmt | B- | Managed, but some RC versions |

**Overall Code Quality Grade: C+ (70%)**

---

## 7. Strengths of AleutianLocal

### Architectural Strengths

#### 1. Privacy by Design ✅

```
Core Philosophy: Data sovereignty and GDPR/HIPAA compliance

Implementation:
- Policy engine embedded in binary (immutable at runtime)
- Regex-based DLP scans ALL user input before LLM calls
- Document ingestion checks for secrets before vectorization
- Optional offline mode (Ollama-only, no cloud API calls)
- Weaviate runs locally (no external vector DB services)

Benefits:
- Suitable for regulated industries (healthcare, finance)
- No accidental data leakage to cloud LLMs
- Audit trail via OpenTelemetry tracing
```

**Example:**
```go
// Before sending to LLM, scan for secrets
findings := pe.ScanFileContent(req.Message)
if len(findings) > 0 {
    slog.Warn("Policy violation", "findings", findings)
    return gin.H{"error": "Message contains sensitive data"}
}

// Only if clean, send to LLM
llmResponse := llmClient.Chat(ctx, messages)
```

#### 2. Multi-Backend LLM Support ✅

```
Abstraction Layer: services/llm/llm.go

Supported Backends:
1. Ollama (local, open-source models)
2. OpenAI (GPT-4, GPT-3.5)
3. Anthropic Claude (Sonnet, Opus)
4. Local Llama.cpp (custom GGUF models)
5. HuggingFace TGI/vLLM (self-hosted)

Switching: Single environment variable
export LLM_BACKEND_TYPE=anthropic

Adding New Backend:
1. Implement LLMClient interface
2. Add to NewLLMClient() factory
3. No changes to handlers
```

**Interface:**
```go
type LLMClient interface {
    Chat(ctx context.Context, messages []LLMMessage) (string, error)
}

// Factory pattern for easy switching
func NewLLMClient() (LLMClient, error) {
    backend := os.Getenv("LLM_BACKEND_TYPE")
    switch backend {
    case "ollama":
        return NewOllamaClient(), nil
    case "openai":
        return NewOpenAIClient(), nil
    case "anthropic":
        return NewAnthropicClient(), nil
    case "llamacpp":
        return NewLlamaCppClient(), nil
    default:
        return NewOllamaClient(), nil  // Default fallback
    }
}
```

#### 3. Microservices Separation ✅

```
Clean Boundaries:
- Orchestrator (Go)    → Routing, policy, handler logic
- RAG Engine (Python)  → Pipelines (standard, reranking, agent, verified)
- Weaviate (Vector DB) → Semantic search, vector storage
- InfluxDB (Time Series) → Metrics, financial data
- Embedding Server (Python) → Model inference (Gemma, BERT, etc.)

Benefits:
- Independent scaling (can run 3 RAG engine replicas)
- Language-specific optimization (Python for ML, Go for concurrency)
- Fault isolation (RAG engine crash doesn't kill orchestrator)
- Easy replacement (swap Weaviate for Pinecone with minimal changes)
```

**Service Independence:**
```yaml
# Can run RAG engine in HA mode
rag-engine:
  replicas: 3
  ports: ["12125:8000"]

# Orchestrator load balances across replicas
RAG_ENGINE_URL: http://rag-engine:8000
```

#### 4. Vector DB Integration ✅

```
Weaviate Integration:
- Schema management (create, backup, restore)
- Session-aware filtering (global vs. session-specific docs)
- Graceful degradation (works without Weaviate in lightweight mode)
- Admin operations (wipeout, delete docs, summary)

Use Cases:
- Corporate knowledge base (ingested PDFs, docs)
- Session-specific context (user-uploaded files)
- Code analysis (ingested source code for RAG)
```

**Session Filtering Example:**
```go
// Query only docs from this session
where := map[string]interface{}{
    "operator": "Equal",
    "path": []string{"session_id"},
    "valueText": sessionID,
}

// OR query global docs (session_id = "global")
where := map[string]interface{}{
    "operator": "Equal",
    "path": []string{"session_id"},
    "valueText": "global",
}
```

#### 5. Time Series Support ✅

```
InfluxDB Integration:
- Native storage for evaluation metrics
- Query API for historical data retrieval
- Tag-based filtering (ticker, model, strategy)
- Time-series aggregations

Benefits for Finance:
- Store OHLCV data (Open, High, Low, Close, Volume)
- Track portfolio state over time
- Compare strategies across models
- Calculate performance metrics (Sharpe, drawdown)
```

**Evaluation Flow:**
```go
// 1. Store evaluation result
result := &EvaluationResult{
    Ticker: "SPY",
    Model: "timesfm-2.0",
    ForecastPrice: 580.0,
    CurrentPrice: 575.0,
    Action: "BUY",
    PositionAfter: 110.0,
}
storage.StoreResult(ctx, result)

// 2. Query historical results
results := storage.QueryResults(ctx, "SPY", startDate, endDate)

// 3. Calculate metrics
sharpe := calculateSharpeRatio(results)
maxDrawdown := calculateMaxDrawdown(results)
```

#### 6. Self-Contained CLI ✅

```
Single Binary:
- Stack management (start, stop, destroy)
- Document ingestion (populate vectordb)
- Model downloads (pull model-id)
- RAG queries (ask "question")
- Forecasting (timeseries forecast SPY)
- Evaluation (evaluate --ticker SPY --model timesfm)
- Admin (weaviate backup, session list)

Benefits:
- No need to remember docker-compose commands
- Integrated configuration management
- User-friendly (./aleutian --help)
```

**Example Workflow:**
```bash
# 1. Start stack
./aleutian stack start --backend ollama

# 2. Ingest docs
./aleutian populate vectordb /path/to/docs

# 3. Ask question
./aleutian ask "What is the refund policy?"

# 4. Run evaluation
./aleutian evaluate --ticker SPY --model timesfm-2.0
```

#### 7. Hardware Auto-Detection ✅

```
Configuration Loader:
- Detects total RAM (sysctl, free, wmic)
- Selects profile (Standard/Performance/Ultra)
- Finds external drives (for model cache)
- Configures Podman machine (RAM, CPU allocation)

Profiles:
- Standard:     <16GB RAM → Tiny models, low parallelism
- Performance:  16-32GB RAM → Medium models, 4 workers
- Ultra:        >32GB RAM → Large models, 8 workers
```

**Auto-Selection:**
```go
func SelectProfile() string {
    ramGB := detectRAM()
    if ramGB < 16 {
        slog.Info("Selected Standard profile", "ram_gb", ramGB)
        return "standard"
    } else if ramGB < 32 {
        slog.Info("Selected Performance profile", "ram_gb", ramGB)
        return "performance"
    }
    slog.Info("Selected Ultra profile", "ram_gb", ramGB)
    return "ultra"
}
```

#### 8. Session Management ✅

```
Features:
- UUID-based session IDs
- WebSocket real-time chat
- Session-specific document filtering
- Conversation memory (last N messages)

Use Cases:
- Multi-user chat (each user has session)
- Session-specific context (user uploads doc → only visible in that session)
```

**Session Flow:**
```go
// 1. Create session
sessionID := uuid.New().String()

// 2. User uploads file
HandleChatWebSocket() → ingest file → tag with session_id

// 3. User asks question
RAG query → filter by session_id → only sees their docs
```

### Implementation Strengths

#### 1. Observability First ✅

```
Every Handler Traced:
ctx, span := tracer.Start(c.Request.Context(), "HandleDirectChat")
defer span.End()

Structured Logging:
slog.Info("Evaluating", "ticker", ticker, "model", model)

Error Recording:
span.RecordError(err)
span.SetStatus(codes.Error, err.Error())
```

#### 2. Graceful Degradation ✅

```
Lightweight Mode:
- Orchestrator checks Weaviate availability
- If unavailable, disables RAG features
- Direct chat still works (LLM-only mode)

Benefits:
- System doesn't crash if Weaviate is down
- Partial functionality better than complete failure
```

**Implementation:**
```go
weaviateClient, err := weaviate.NewClient(weaviateURL)
if err != nil {
    slog.Warn("Weaviate unavailable, running in lightweight mode")
    weaviateClient = nil  // Handlers check for nil
}
```

#### 3. Modular LLM Layer ✅

```
Adding New Backend:
1. Create client struct
2. Implement LLMClient interface
3. Add to factory switch
4. No handler changes required

Example:
type GeminiClient struct {
    apiKey  string
    baseURL string
}

func (c *GeminiClient) Chat(ctx context.Context, messages []LLMMessage) (string, error) {
    // Implementation
}
```

#### 4. Comprehensive Evaluation Framework ✅

```
Full Pipeline:
1. Fetch current price from InfluxDB
2. Call forecast service (TimesFM, Chronos, etc.)
3. For each forecast horizon:
   a. Call trading service (Sapheneia)
   b. Update portfolio state
   c. Store result in InfluxDB

Configurable:
- Strategy type (threshold, return, quantile)
- Strategy params (threshold value, execution size)
- Context size (historical window)
- Horizon size (forecast days)
```

#### 5. Policy Scanning at Ingestion ✅

```
Document Ingestion Flow:
1. User uploads file
2. PolicyEngine.ClassifyData(fileContent)
3. If classification == "SECRET", reject
4. If classification == "PUBLIC", proceed
5. Chunk → Embed → Store in Weaviate

Prevents:
- Secrets from entering VectorDB
- Accidental PII exposure in RAG responses
```

#### 6. Clean HTTP Error Handling ✅

```
Consistent Pattern:
if err != nil {
    slog.Error("Operation failed", "error", err)
    c.JSON(http.StatusInternalServerError, gin.H{"error": "..."})
    return
}

JSON Error Responses:
c.JSON(400, gin.H{"error": "invalid request body"})
c.JSON(500, gin.H{"error": "internal server error"})
```

### Operational Strengths

#### 1. Container-Native ✅

```
Podman Compose:
- All services containerized
- Volume management for models, data
- Network isolation (aleutian-network)
- Health checks on all services

Benefits:
- Easy deployment (podman-compose up)
- Consistent environments (dev == prod)
- Resource limits (CPU, memory constraints)
```

#### 2. Extensible Configuration ✅

```
YAML Config + Env Vars:
- aleutian.yaml → Default config
- Environment variables → Override config
- Command-line flags → Override both

Flexibility:
- Development: Use config file
- Production: Use env vars (Kubernetes ConfigMaps)
- Testing: Use flags (--backend=ollama)
```

#### 3. Flexible Backend Selection ✅

```
Local Development:
export LLM_BACKEND_TYPE=ollama
./aleutian stack start

Production:
export LLM_BACKEND_TYPE=openai
export OPENAI_API_KEY=sk-...
./aleutian stack start

No Code Changes Required
```

#### 4. Model Caching ✅

```
HuggingFace Integration:
- Models downloaded to ./models_cache
- Shared volume across services
- Automatic resume on partial downloads

Benefits:
- No repeated downloads (saves bandwidth)
- Faster startup (models pre-cached)
- Offline operation (models available locally)
```

#### 5. Secrets Management ✅

```
Podman Secrets:
echo "sk-..." | podman secret create openai_api_key -
podman-compose up

Services read from /run/secrets/openai_api_key

Benefits:
- Not in environment variables (ps aux doesn't show)
- Not in config files (no accidental commits)
- Encrypted at rest
```

---

## 8. Weaknesses & Technical Concerns

### Critical Issues (Must Fix Before Production)

#### 1. No Authentication/Authorization ❌

**Current State:**
```go
// NO authentication checks
// NO user identification
// NO session validation

// Endpoints are completely open:
POST /api/chat           → Anyone can chat
POST /api/documents      → Anyone can ingest
DELETE /api/weaviate/documents → Anyone can delete
POST /api/timeseries/forecast  → Anyone can forecast
```

**Impact:**
- ✅ **ALLOWS**: Unauthorized access to all data
- ✅ **ALLOWS**: Data exfiltration (download all documents)
- ✅ **ALLOWS**: Data tampering (delete documents, inject malicious data)
- ✅ **ALLOWS**: Resource exhaustion (spam forecast requests)

**Risk Level: CRITICAL (10/10)**

**What's Needed:**
```go
// 1. JWT/OAuth2 authentication
func AuthMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        token := c.GetHeader("Authorization")
        claims, err := ValidateJWT(token)
        if err != nil {
            c.JSON(401, gin.H{"error": "Unauthorized"})
            c.Abort()
            return
        }
        c.Set("user_id", claims.UserID)
        c.Next()
    }
}

// 2. User-based isolation
func QueryDocuments(c *gin.Context) {
    userID := c.GetString("user_id")
    where := map[string]interface{}{
        "operator": "Equal",
        "path": []string{"user_id"},
        "valueText": userID,
    }
    // Only returns user's docs
}
```

#### 2. Hardcoded Secrets ❌

**Location:** `evaluator.go:306`

```go
token := os.Getenv("INFLUXDB_TOKEN")
if token == "" {
    // ⚠️ CRITICAL: Hardcoded fallback token
    token = "your_super_secret_admin_token"
}
```

**Impact:**
- ✅ **ALLOWS**: Anyone with code access knows the token
- ✅ **ALLOWS**: Shared token across all deployments
- ✅ **ALLOWS**: Token visible in version control history

**Risk Level: CRITICAL (10/10)**

**What's Needed:**
```go
// 1. Remove hardcoded fallback
token := os.Getenv("INFLUXDB_TOKEN")
if token == "" {
    return nil, fmt.Errorf("INFLUXDB_TOKEN not set")
}

// 2. Use secret management
token := readFromVault("influxdb/token")

// 3. Rotate tokens regularly
// - Generate new token
// - Update Podman secret
// - Restart services
```

#### 3. WebSocket CORS Vulnerability ❌

**Location:** `websocket.go:52`

```go
upgrader := websocket.Upgrader{
    CheckOrigin: func(r *http.Request) bool {
        return true  // ⚠️ ALLOWS ALL ORIGINS
    },
}
```

**Attack Scenario:**
```html
<!-- Malicious website: evil.com -->
<script>
const ws = new WebSocket("ws://aleutian.local:12210/ws/chat");
ws.onopen = () => {
    ws.send(JSON.stringify({
        message: "Transfer all money to account 123456",
        session_id: "user-session-id"
    }));
};
</script>
```

**Impact:**
- ✅ **ALLOWS**: Cross-site WebSocket hijacking
- ✅ **ALLOWS**: Session hijacking (if session_id is guessable)
- ✅ **ALLOWS**: Data exfiltration (read chat history)

**Risk Level: CRITICAL (9/10)**

**What's Needed:**
```go
CheckOrigin: func(r *http.Request) bool {
    origin := r.Header.Get("Origin")
    allowed := []string{
        "http://localhost:3000",
        "http://localhost:8080",
        os.Getenv("ALLOWED_ORIGIN"),
    }
    for _, a := range allowed {
        if origin == a {
            return true
        }
    }
    slog.Warn("Rejected WebSocket from origin", "origin", origin)
    return false
},
```

### High Priority Issues

#### 4. Input Validation Gaps ⚠️

**Missing Validations:**

```go
// 1. No string length limits
type DirectChatRequest struct {
    Message string `json:"message"`  // Could be 1GB string
}

// 2. No numeric range checks
type ForecastRequest struct {
    ContextPeriodSize  int  // Could be negative or INT_MAX
    ForecastPeriodSize int  // Could be negative or INT_MAX
}

// 3. No format validation
type EvaluationConfig struct {
    EvaluationDate string  // Expects "20250117" but accepts "invalid"
}
```

**Exploitation:**
```bash
# Memory exhaustion attack
curl -X POST localhost:12210/api/chat \
  -d '{"message": "'$(python3 -c 'print("A"*1000000000)')'"}'

# Integer overflow
curl -X POST localhost:12210/api/timeseries/forecast \
  -d '{"context_period_size": 2147483647, "forecast_period_size": 2147483647}'
```

**Impact:**
- ✅ **ALLOWS**: Memory exhaustion (DoS)
- ✅ **ALLOWS**: Integer overflow (crashes)
- ✅ **ALLOWS**: Malformed data in database

**Risk Level: HIGH (7/10)**

**What's Needed:**
```go
import "github.com/go-playground/validator/v10"

type DirectChatRequest struct {
    Message string `json:"message" validate:"required,min=1,max=10000"`
    Stream  bool   `json:"stream"`
}

func Validate(req interface{}) error {
    validate := validator.New()
    return validate.Struct(req)
}
```

#### 5. Missing Timeouts & Deadlines ⚠️

**Current State:**
```go
// 5-minute timeout (too long)
httpClient := &http.Client{Timeout: 5 * time.Minute}

// No context deadline
req, _ := http.NewRequestWithContext(ctx, "POST", url, body)
```

**Impact:**
- ✅ **ALLOWS**: Goroutines blocked indefinitely
- ✅ **ALLOWS**: Resource exhaustion (too many waiting goroutines)
- ✅ **ALLOWS**: Cascade failures (one slow service hangs everything)

**Risk Level: HIGH (6/10)**

**What's Needed:**
```go
// 1. Reasonable timeouts
httpClient := &http.Client{Timeout: 30 * time.Second}

// 2. Context deadlines
ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
defer cancel()

req, _ := http.NewRequestWithContext(ctx, "POST", url, body)

// 3. Circuit breaker pattern
if consecutiveFailures > 5 {
    return ErrCircuitOpen
}
```

#### 6. Test Coverage ⚠️

**Coverage Analysis:**
```
Critical Handlers (UNTESTED):
- evaluator.go (357 lines) → Financial calculations
- websocket.go (398 lines) → Real-time chat
- timeseries.go (243 lines) → Forecast routing
- trading.go (122 lines) → Trading signals

Impact of No Tests:
- Regression bugs go undetected
- Refactoring is risky
- Financial calculations could be wrong
- Integration failures only caught in production
```

**Risk Level: HIGH (8/10)**

**What's Needed:**
```go
// evaluator_test.go
func TestEvaluateTickerModel(t *testing.T) {
    // 1. Mock InfluxDB
    mockStorage := &MockInfluxDBStorage{
        GetCurrentPriceFunc: func(ticker string) (float64, error) {
            return 575.0, nil
        },
    }

    // 2. Mock forecast service
    mockForecastServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Write([]byte(`{"forecast": [580.0, 582.0]}`))
    }))
    defer mockForecastServer.Close()

    // 3. Run evaluation
    evaluator := &Evaluator{storage: mockStorage}
    err := evaluator.EvaluateTickerModel(ctx, "SPY", "timesfm", config, 575.0)

    // 4. Assert
    assert.NoError(t, err)
    assert.Equal(t, 1, len(mockStorage.StoredResults))
    assert.Equal(t, "SPY", mockStorage.StoredResults[0].Ticker)
}
```

#### 7. Dependency on Release Candidate ⚠️

**go.mod:**
```go
github.com/weaviate/weaviate v1.33.0-rc.1  // ⚠️ Release Candidate
```

**Impact:**
- RC versions may have bugs
- Breaking changes before stable release
- No security patch guarantees

**Risk Level: MEDIUM (5/10)**

**What's Needed:**
```go
// Pin to stable version
github.com/weaviate/weaviate v1.33.0  // Wait for stable release

// OR use client library only (stable)
github.com/weaviate/weaviate-go-client/v5 v5.5.0
```

### Medium Priority Issues

#### 8. Session Management ⚠️

**Current Implementation:**
```go
// Session IDs are UUIDs (good)
sessionID := uuid.New().String()

// BUT:
// - No session expiration
// - No logout mechanism
// - No CSRF tokens
// - Session IDs in URL params (should be in headers)
```

**Impact:**
- ✅ **ALLOWS**: Session hijacking (if session_id leaked)
- ✅ **ALLOWS**: Unlimited session growth (memory leak)

**Risk Level: MEDIUM (5/10)**

**What's Needed:**
```go
type Session struct {
    ID        string
    UserID    string
    CreatedAt time.Time
    ExpiresAt time.Time
}

func ValidateSession(sessionID string) (*Session, error) {
    session := GetSession(sessionID)
    if time.Now().After(session.ExpiresAt) {
        return nil, ErrSessionExpired
    }
    return session, nil
}
```

#### 9. Concurrency Issues ⚠️

**Location:** `websocket.go:221`

```go
// Spawns goroutine without wait group
go func() {
    runWebSocketIngestion(ws, req, weaviateClient, pe)
}()

// If process exits, goroutine is abandoned
// Data loss possible
```

**Impact:**
- Data loss on shutdown
- Orphaned goroutines
- No graceful shutdown

**Risk Level: MEDIUM (4/10)**

**What's Needed:**
```go
var wg sync.WaitGroup

wg.Add(1)
go func() {
    defer wg.Done()
    runWebSocketIngestion(ws, req, weaviateClient, pe)
}()

// On shutdown:
wg.Wait()  // Wait for all ingestion to complete
```

#### 10. Error Handling Inconsistencies ⚠️

**Examples:**
```go
// Sometimes logged, sometimes not
if err != nil {
    slog.Error("Error", "error", err)
    return err
}

// Sometimes returns 500, sometimes 400 for same error
c.JSON(http.StatusInternalServerError, ...)  // Same error
c.JSON(http.StatusBadRequest, ...)           // Same error

// io.ReadAll() results sometimes discarded
body, _ := io.ReadAll(resp.Body)  // Error ignored
```

**Risk Level: MEDIUM (4/10)**

**What's Needed:**
```go
// Consistent error handling
if err != nil {
    slog.Error("Operation failed", "error", err)
    c.JSON(determineStatusCode(err), gin.H{"error": sanitizeError(err)})
    return
}

// Check all errors
body, err := io.ReadAll(resp.Body)
if err != nil {
    return fmt.Errorf("failed to read response: %w", err)
}
```

#### 11. Resource Cleanup ⚠️

**Missing defer in some paths:**
```go
storage, err := NewInfluxDBStorage()
if err != nil {
    return err  // Storage not closed
}
defer storage.Close()  // Only closes on normal return

// Should be:
defer func() {
    if storage != nil {
        storage.Close()
    }
}()
```

**Risk Level: MEDIUM (3/10)**

#### 12. Configuration Validation ⚠️

**Current State:**
```go
// No validation on startup
// Missing env vars silently use defaults

ollama_base_url := os.Getenv("OLLAMA_BASE_URL")
if ollama_base_url == "" {
    ollama_base_url = "http://host.containers.internal:11434"  // Assume default
}

// Could connect to wrong service silently
```

**Risk Level: MEDIUM (4/10)**

**What's Needed:**
```go
// Validate critical config on startup
func ValidateConfig() error {
    if os.Getenv("LLM_BACKEND_TYPE") == "openai" {
        if os.Getenv("OPENAI_API_KEY") == "" {
            return fmt.Errorf("OPENAI_API_KEY required for openai backend")
        }
    }
    // ... more checks
}

// In main():
if err := ValidateConfig(); err != nil {
    log.Fatal("Configuration error:", err)
}
```

### Low Priority Issues

#### 13. Performance ⚠️

**Inefficiencies:**
```go
// 1. No connection pooling
httpClient := &http.Client{}  // New connection per request

// 2. Synchronous embedding requests
for _, chunk := range chunks {
    embedding := callEmbeddingService(chunk)  // Blocks
}

// 3. No caching of Weaviate schema
schema := weaviateClient.Schema().Get()  // Every request
```

**Risk Level: LOW (2/10)**

**What's Needed:**
```go
// 1. Connection pooling
httpClient := &http.Client{
    Transport: &http.Transport{
        MaxIdleConns:        100,
        MaxIdleConnsPerHost: 100,
    },
}

// 2. Parallel embedding
var wg sync.WaitGroup
embeddingChan := make(chan Embedding, len(chunks))
for _, chunk := range chunks {
    wg.Add(1)
    go func(c string) {
        defer wg.Done()
        emb := callEmbeddingService(c)
        embeddingChan <- emb
    }(chunk)
}
wg.Wait()
close(embeddingChan)

// 3. Cache schema
var cachedSchema *Schema
if cachedSchema == nil {
    cachedSchema = weaviateClient.Schema().Get()
}
```

#### 14. Logging Verbosity ⚠️

**Potential Data Leakage:**
```go
slog.Info("Received chat request", "message", req.Message)  // Logs PII

slog.Error("Query failed", "query", query)  // Could log secrets
```

**Risk Level: LOW (3/10)**

**What's Needed:**
```go
// Redact sensitive fields
slog.Info("Received chat request", "message_length", len(req.Message))

// Use custom logger with redaction
type RedactingLogger struct {
    *slog.Logger
}

func (l *RedactingLogger) Info(msg string, args ...interface{}) {
    redacted := redactSecrets(args)
    l.Logger.Info(msg, redacted...)
}
```

---

## 9. Fit for Financial Forecast Evaluation

### Why AleutianLocal is GOOD for Financial Evaluation

#### 1. Multi-Model Support ✅

```
Built-in Routing for 40+ Models:
- Google TimesFM (1.0, 2.0)
- Amazon Chronos (T5, Bolt)
- Salesforce Moirai
- IBM Granite
- AutoNLab Moment
- Alibaba YingLong
- Lag-Llama, Kairos, TimeMoE, TIMER

Implementation:
switch req.Model {
case "google/timesfm-2.0-500m-pytorch":
    return handleTimesFM20Forecast(c, req)
case "amazon/chronos-t5-base":
    return handleChronosForecast(c, req)
// ... 15+ cases
}

Benefits:
- Evaluate 15+ models in a single run
- Compare model performance systematically
- Easy to add new models (just add case)
```

**Example:**
```bash
# Evaluate all default models (10 models)
./aleutian evaluate --ticker SPY

# Evaluates:
# - google/timesfm-2.0-500m-pytorch
# - amazon/chronos-t5-base
# - salesforce/moirai-1.1-R-large
# - ibm/granite-ttm-r2
# ... 6 more
```

#### 2. Time Series Integration ✅

```
InfluxDB Native Support:
- Measurement: stock_prices (OHLCV data)
- Measurement: forecast_evaluations (results)
- Tags: ticker, model, strategy_type
- Fields: forecast_price, action, position_after

Query API:
- GetCurrentPrice() → Last close price
- GetHistoricalWindow() → Context window for forecasting
- StoreResult() → Write evaluation result

Benefits:
- Purpose-built for time-series data
- Fast queries (indexed by time + tags)
- Aggregations (avg, max, min, percentile)
- Downsampling (hourly → daily → weekly)
```

**Schema:**
```go
influxdb2.NewPointWithMeasurement("forecast_evaluations").
    AddTag("ticker", "SPY").
    AddTag("model", "google/timesfm-2.0-500m-pytorch").
    AddTag("evaluation_date", "20250118").
    AddTag("run_id", "abc123").
    AddField("forecast_price", 580.0).
    AddField("current_price", 575.0).
    AddField("action", "BUY").
    AddField("position_after", 110.0).
    SetTime(time.Now())
```

#### 3. Trading Strategy Integration ✅

```
Sapheneia Integration:
- Native HTTP client to trading service
- Strategy parameters abstracted
- Portfolio state tracking

Supported Strategies:
1. Threshold (absolute, percentage, std_dev, ATR)
2. Return (fixed, proportional, normalized)
3. Quantile (empirical distribution-based)

Configuration:
config := &EvaluationConfig{
    StrategyType: "threshold",
    StrategyParams: map[string]interface{}{
        "threshold_type":  "absolute",
        "threshold_value": 2.0,
        "execution_size":  10.0,
    },
}
```

**Evaluation Flow:**
```go
// 1. Generate forecast
forecast := CallForecastService(ticker, model, contextSize, horizonSize)

// 2. For each horizon (1-20 days)
for horizon := 1; horizon <= 20; horizon++ {
    // 3. Generate trading signal
    signal := CallTradingService(
        ticker,
        forecast[horizon],
        currentPosition,
        availableCash,
        strategyParams,
    )

    // 4. Update portfolio
    currentPosition = signal.PositionAfter
    availableCash = signal.AvailableCash

    // 5. Store result
    StoreResult(ticker, model, horizon, signal)
}
```

#### 4. Evaluation Harness ✅

```
Full Pipeline:
1. Fetch data → InfluxDB query for current price
2. Forecast → POST /v1/timeseries/forecast
3. Trade → POST /trading/execute
4. Store → InfluxDB write

CLI Command:
./aleutian evaluate --ticker SPY --model timesfm-2.0

Output:
- forecast_evaluations measurement (2,268 records for 10 years)
- Portfolio evolution over time
- Performance metrics per ticker/model
```

**Extensible Configuration:**
```go
type EvaluationConfig struct {
    Tickers []TickerInfo     // Which assets
    Models []string          // Which models
    StrategyType string       // Which strategy
    StrategyParams map[...]   // Strategy config
    ContextSize int           // Historical window
    HorizonSize int           // Forecast length
    InitialCapital float64    // Starting capital
}
```

#### 5. Privacy/Security ✅

```
All Data Stays Local:
- InfluxDB runs in Podman container
- Weaviate runs locally
- Forecast models downloaded to ./models_cache
- No cloud services required (except LLM backend if configured)

Policy Engine:
- Scans all data before ingestion
- Blocks secrets/PII from entering database
- Suitable for regulated financial data

Benefits:
- GDPR/HIPAA compliant (data sovereignty)
- No accidental credential leakage
- Audit trail via OpenTelemetry
```

#### 6. Observability ✅

```
OpenTelemetry Tracing:
- Every evaluation run is traced
- Spans: GetCurrentPrice → Forecast → Trade → Store
- Trace IDs link entire pipeline

InfluxDB Storage:
- Long-term analysis (years of data)
- Compare strategies over time
- Backtest different models

Metrics:
- Portfolio value evolution
- Trade counts per strategy
- Model performance (Sharpe ratio, max drawdown)
```

**Example Trace:**
```
RunEvaluation (span_id: abc123)
├─ GetCurrentPrice (span_id: def456) → InfluxDB query
├─ CallForecastService (span_id: ghi789) → TimesFM API
├─ CallTradingService (span_id: jkl012) → Sapheneia API
└─ StoreResult (span_id: mno345) → InfluxDB write
```

#### 7. Scalability ✅

```
Podman Allows:
- Multiple forecast service replicas
- Load balancing across replicas
- Horizontal scaling

InfluxDB:
- Time-series optimized (fast writes)
- Cardinality-aware (tags vs. fields)
- Downsampling for long-term storage

Evaluation:
- Can run in parallel (goroutines per ticker)
- Batch processing (10 tickers at a time)
```

**Parallel Evaluation:**
```go
var wg sync.WaitGroup
for _, ticker := range tickers {
    wg.Add(1)
    go func(t string) {
        defer wg.Done()
        EvaluateTickerModel(t, model, config)
    }(ticker)
}
wg.Wait()
```

---

### Why AleutianLocal is BAD for Financial Evaluation

#### 1. No Authentication ❌

```
Financial Data is Sensitive:
- Stock prices (proprietary if real-time)
- Trading strategies (intellectual property)
- Portfolio positions (confidential)

Current State:
- NO user authentication
- NO data isolation
- NO access control

Impact:
- Anyone on network can see all data
- Anyone can run evaluations (resource theft)
- Anyone can delete results (data loss)
```

**Risk Level: CRITICAL for Production**

#### 2. Missing Confidence Intervals ❌

```
Evaluator Only Stores Point Forecasts:
forecast := []float64{580.0, 582.0, 584.0}  // Mean only

Missing:
- Percentile bands (P5, P95)
- Confidence intervals (95% CI)
- Uncertainty quantification

Impact:
- Can't assess forecast reliability
- Can't implement risk-adjusted strategies
- No way to filter low-confidence predictions
```

**What's Needed:**
```go
type ForecastResult struct {
    Mean []float64
    P05  []float64  // 5th percentile
    P50  []float64  // Median
    P95  []float64  // 95th percentile
    StdDev []float64
}

// Risk-adjusted trading:
if (forecast.P95 - forecast.P05) > threshold {
    // Too uncertain, skip trade
    return "HOLD"
}
```

#### 3. Single-Path Trading Logic ❌

```
Evaluator Doesn't Handle:
- Slippage (price moves between signal and execution)
- Execution delays (real markets aren't instant)
- Market impact (large orders move prices)
- Transaction costs (commissions, spreads)

Current Implementation:
signal := CallTradingService(forecastPrice, currentPrice)
// Assumes instant execution at currentPrice

Real World:
- Order placed at $575
- Executed at $575.50 (slippage)
- Commission: $0.005/share
- Market impact: +0.02% for large orders
```

**What's Needed:**
```go
type ExecutionModel struct {
    SlippagePercent float64  // 0.1% typical
    Commission      float64  // $0.005/share
    Delay           time.Duration  // 100ms typical
    ImpactFactor    float64  // Price impact per $1M notional
}

func SimulateExecution(signal TradingSignal, model ExecutionModel) ExecutedTrade {
    // Apply slippage
    executedPrice := signal.Price * (1 + model.SlippagePercent)

    // Apply commission
    totalCost := signal.Size * executedPrice + model.Commission

    // Apply delay (next bar's price)
    // Apply market impact for large orders
}
```

#### 4. Simplified Portfolio State ❌

```
Current Portfolio Tracking:
type PortfolioState struct {
    Position float64
    Cash     float64
}

Missing:
- Multiple positions (only tracks 1 ticker at a time)
- Margin/leverage
- Risk limits (max drawdown, position limits)
- Portfolio-level risk (correlation, diversification)

Impact:
- Can't backtest multi-asset strategies
- Can't model realistic portfolio construction
- No risk management
```

**What's Needed:**
```go
type Portfolio struct {
    Positions map[string]float64  // ticker → size
    Cash      float64
    Margin    float64
    RiskLimits struct {
        MaxDrawdown      float64
        MaxPositionSize  float64
        MaxLeverage      float64
    }
}

func (p *Portfolio) CanTrade(ticker string, size float64) bool {
    // Check risk limits
    newPosition := p.Positions[ticker] + size
    if math.Abs(newPosition) > p.RiskLimits.MaxPositionSize {
        return false
    }
    // Check drawdown
    // Check leverage
    return true
}
```

#### 5. No Backtesting Framework ❌

```
Current: Single-Point Evaluation
- Runs ONE forecast at current time
- Loops through horizons (1-20 days)
- Stores results

Missing: Walk-Forward Backtesting
- For each day D in [start...end]:
  * Read historical window (D-252 to D)
  * Generate forecast for D+1 to D+20
  * Simulate trade on D+1
  * Update portfolio
  * Repeat

Example:
10 years of SPY data = 2,520 trading days
Context period = 252 days
Backtestable days = 2,520 - 252 = 2,268 days

Current: 1 evaluation run
Needed: 2,268 evaluation runs (1 per day)
```

**What's Needed:**
```go
func (e *Evaluator) BacktestRollingWindow(
    ticker string,
    model string,
    startDate, endDate time.Time,
) error {
    tradingDays := GetTradingDays(ticker, startDate, endDate)

    for _, day := range tradingDays[contextSize:] {
        // 1. Read historical window (day-252 to day)
        window := GetHistoricalWindow(ticker, day, 252)

        // 2. Generate forecast
        forecast := CallForecastService(ticker, model, window, 20)

        // 3. Trade on day+1 forecast only
        signal := CallTradingService(ticker, forecast[0], portfolio)

        // 4. Update portfolio
        portfolio.Apply(signal)

        // 5. Store result
        StoreResult(ticker, model, day, signal, portfolio)
    }

    return nil
}
```

#### 6. Limited Data Sources ❌

```
Current Data Fetching:
- Yahoo Finance only (hardcoded in some services)
- Daily interval (no intraday)
- Limited history (5 years typical)

Missing:
- Alternative data providers (IEX, Polygon, Bloomberg)
- Real-time feeds (WebSocket streams)
- Tick data (sub-second granularity)
- Alternative data (sentiment, news, social media)

Impact:
- Can't backtest intraday strategies
- Limited historical depth
- No real-time evaluation
```

**What's Needed:**
```go
type DataProvider interface {
    FetchOHLCV(ticker string, start, end time.Time, interval string) ([]OHLCV, error)
}

type YahooFinanceProvider struct{}
type IEXCloudProvider struct{}
type PolygonIOProvider struct{}

func NewDataProvider(providerName string) DataProvider {
    switch providerName {
    case "yahoo":
        return &YahooFinanceProvider{}
    case "iex":
        return &IEXCloudProvider{}
    case "polygon":
        return &PolygonIOProvider{}
    }
}
```

#### 7. Evaluation Gaps ❌

```
Missing Analysis:
1. Baseline Comparison
   - No buy-and-hold benchmark
   - No random walk baseline
   - Can't assess if strategy adds value

2. Statistical Significance
   - No hypothesis testing
   - No confidence intervals on performance metrics
   - Can't distinguish luck from skill

3. Correlation Analysis
   - No cross-model correlation
   - No regime detection (bull/bear markets)
   - Can't identify when models agree/disagree

4. Transaction Cost Modeling
   - No commissions
   - No bid-ask spreads
   - No market impact
```

**What's Needed:**
```go
// 1. Baseline comparison
func CompareToBuyAndHold(strategyReturns, benchmarkReturns []float64) float64 {
    strategyTotal := cumulativeReturn(strategyReturns)
    benchmarkTotal := cumulativeReturn(benchmarkReturns)
    return strategyTotal - benchmarkTotal  // Alpha
}

// 2. Statistical significance
func TestStrategySignificance(returns []float64) (tStat float64, pValue float64) {
    mean := average(returns)
    stdErr := stddev(returns) / math.Sqrt(float64(len(returns)))
    tStat = mean / stdErr
    pValue = tDistribution(tStat, len(returns)-1)
    return
}

// 3. Correlation analysis
func CrossModelCorrelation(model1Results, model2Results []float64) float64 {
    return pearsonCorrelation(model1Results, model2Results)
}
```

#### 8. Testing ❌

```
No Tests for Evaluator Logic:
- evaluator.go (357 lines) → 0 tests
- timeseries.go (243 lines) → 0 tests
- trading.go (122 lines) → 0 tests

Impact:
- Financial calculations could be wrong
- Bugs in portfolio state tracking
- Incorrect strategy implementation

Example Bug (Undetected):
// currentPosition should be updated AFTER trade, not before
currentPosition = signal.PositionAfter  // ✅ Correct
availableCash = signal.AvailableCash

// But what if signal calculation is wrong?
// NO TESTS to catch this
```

**What's Needed:**
```go
// evaluator_test.go
func TestPortfolioStateTracking(t *testing.T) {
    // Given: Portfolio with $100k, 0 shares
    portfolio := &Portfolio{Cash: 100000, Position: 0}

    // When: BUY 100 shares at $575
    signal := &TradingSignal{
        Action: "BUY",
        Size: 100,
        Value: 57500,
        PositionAfter: 100,
        AvailableCash: 42500,
    }
    portfolio.Apply(signal)

    // Then: Portfolio has 100 shares, $42.5k cash
    assert.Equal(t, 100.0, portfolio.Position)
    assert.Equal(t, 42500.0, portfolio.Cash)

    // When: SELL 50 shares at $580
    signal = &TradingSignal{
        Action: "SELL",
        Size: -50,
        Value: 29000,
        PositionAfter: 50,
        AvailableCash: 71500,
    }
    portfolio.Apply(signal)

    // Then: Portfolio has 50 shares, $71.5k cash
    assert.Equal(t, 50.0, portfolio.Position)
    assert.Equal(t, 71500.0, portfolio.Cash)
}
```

#### 9. State Management ❌

```
Current:
- InfluxDB token hardcoded
- No user-specific data isolation
- Portfolio state not persisted between runs

Impact:
- Can't resume interrupted evaluations
- Can't share results across users
- No audit trail of who ran what

Example:
# User 1 runs evaluation
./aleutian evaluate --ticker SPY

# User 2 sees User 1's results (no isolation)
influx query 'SELECT * FROM forecast_evaluations'
```

**What's Needed:**
```go
// 1. User-based isolation
type EvaluationRun struct {
    RunID   string
    UserID  string  // NEW: Isolate by user
    Ticker  string
    Model   string
    Status  string  // "running", "completed", "failed"
}

// 2. Resume capability
func ResumeEvaluation(runID string) error {
    run := GetEvaluationRun(runID)
    if run.Status == "completed" {
        return fmt.Errorf("already completed")
    }

    // Resume from last completed day
    lastDay := GetLastCompletedDay(runID)
    tradingDays := GetTradingDays(run.Ticker, lastDay, time.Now())

    for _, day := range tradingDays {
        // Continue evaluation
    }
}
```

---

### What Would Need to Change (Priority Order)

#### 1. Authentication & Authorization (CRITICAL)

```go
// Add JWT middleware
router.Use(AuthMiddleware())

// Implement user-based isolation
where := map[string]interface{}{
    "operator": "And",
    "operands": []map[string]interface{}{
        {"path": []string{"user_id"}, "valueText": userID},
        {"path": []string{"ticker"}, "valueText": ticker},
    },
}

// Add RBAC
if !user.HasPermission("evaluation:run") {
    return ErrUnauthorized
}
```

#### 2. Remove Hardcoded Secrets (CRITICAL)

```go
// Remove fallback tokens
token := os.Getenv("INFLUXDB_TOKEN")
if token == "" {
    return nil, fmt.Errorf("INFLUXDB_TOKEN required")
}

// Use vault for secrets
token := vault.GetSecret("influxdb/token")
```

#### 3. Add Input Validation (HIGH)

```go
import "github.com/go-playground/validator/v10"

type ForecastRequest struct {
    Ticker             string `validate:"required,uppercase,min=1,max=10"`
    ContextPeriodSize  int    `validate:"required,min=1,max=1000"`
    ForecastPeriodSize int    `validate:"required,min=1,max=100"`
    Model              string `validate:"required,oneof=timesfm chronos moirai"`
}
```

#### 4. Implement Walk-Forward Backtesting (HIGH)

```go
func (e *Evaluator) BacktestRollingWindow(
    ticker string,
    model string,
    startDate, endDate time.Time,
    contextSize, horizonSize int,
) error {
    tradingDays := GetTradingDays(ticker, startDate, endDate)

    for _, day := range tradingDays[contextSize:] {
        window := GetHistoricalWindow(ticker, day, contextSize)
        forecast := CallForecastService(ticker, model, window, horizonSize)

        // Trade on day+1 forecast only
        signal := CallTradingService(ticker, forecast[0], portfolio)
        portfolio.Apply(signal)

        StoreResult(ticker, model, day, signal, portfolio)
    }

    return nil
}
```

#### 5. Add Confidence Intervals (HIGH)

```go
type ForecastResult struct {
    Mean   []float64
    P05    []float64
    P50    []float64
    P95    []float64
    StdDev []float64
}

// Store in InfluxDB
for i, mean := range forecast.Mean {
    p.AddField(fmt.Sprintf("day_%02d_mean", i+1), mean)
    p.AddField(fmt.Sprintf("day_%02d_p05", i+1), forecast.P05[i])
    p.AddField(fmt.Sprintf("day_%02d_p95", i+1), forecast.P95[i])
}
```

#### 6. Transaction Cost Modeling (MEDIUM)

```go
type ExecutionModel struct {
    SlippagePercent float64
    Commission      float64
    MarketImpactFactor float64
}

func (m *ExecutionModel) Execute(signal TradingSignal, price float64) ExecutedTrade {
    executedPrice := price * (1 + m.SlippagePercent)
    totalCost := signal.Size * executedPrice + m.Commission
    return ExecutedTrade{Price: executedPrice, Cost: totalCost}
}
```

#### 7. Multi-Asset Portfolio (MEDIUM)

```go
type Portfolio struct {
    Positions map[string]float64  // ticker → size
    Cash      float64
    Margin    float64
    RiskLimits RiskLimitConfig
}

func (p *Portfolio) Rebalance(targets map[string]float64) []TradingSignal {
    signals := []TradingSignal{}
    for ticker, targetWeight := range targets {
        currentWeight := p.GetWeight(ticker)
        delta := targetWeight - currentWeight
        if math.Abs(delta) > 0.01 {  // 1% threshold
            signals = append(signals, TradingSignal{
                Ticker: ticker,
                Size: delta * p.TotalValue(),
            })
        }
    }
    return signals
}
```

#### 8. Write Tests (MEDIUM)

```go
// evaluator_test.go
func TestBacktestRollingWindow(t *testing.T) {
    // Mock data
    // Mock forecast service
    // Mock trading service
    // Run backtest
    // Assert results
}

func TestPortfolioStateTracking(t *testing.T) {
    // Test position updates
    // Test cash updates
    // Test P&L calculation
}

func TestTransactionCosts(t *testing.T) {
    // Test slippage
    // Test commission
    // Test market impact
}
```

#### 9. Baseline Comparison (LOW)

```go
func CompareToBuyAndHold(
    strategyResults []EvaluationResult,
    ticker string,
    startDate, endDate time.Time,
) ComparisonReport {
    // Calculate strategy return
    strategyReturn := calculateReturn(strategyResults)

    // Calculate buy-and-hold return
    startPrice := GetPrice(ticker, startDate)
    endPrice := GetPrice(ticker, endDate)
    buyHoldReturn := (endPrice - startPrice) / startPrice

    // Calculate alpha
    alpha := strategyReturn - buyHoldReturn

    return ComparisonReport{
        StrategyReturn: strategyReturn,
        BuyHoldReturn: buyHoldReturn,
        Alpha: alpha,
    }
}
```

#### 10. Performance Metrics (LOW)

```go
func CalculateMetrics(results []EvaluationResult) PerformanceMetrics {
    returns := extractReturns(results)

    return PerformanceMetrics{
        SharpeRatio:   calculateSharpe(returns),
        MaxDrawdown:   calculateMaxDrawdown(returns),
        WinRate:       calculateWinRate(results),
        AverageTrade:  calculateAverageTrade(results),
        TotalReturn:   calculateTotalReturn(returns),
    }
}
```

---

## 10. Alternative Approaches

### 1. Replace InfluxDB with TimescaleDB

**Current:** InfluxDB 2.x (time-series database)

**Alternative:** TimescaleDB (PostgreSQL extension)

**Pros:**
- SQL queries (more familiar to developers)
- ACID transactions (data integrity guarantees)
- Better for analytics (JOINs, complex aggregations)
- Lower cardinality limits (InfluxDB struggles with high cardinality)

**Cons:**
- Slower writes than InfluxDB
- Requires PostgreSQL knowledge
- More complex setup

**When to Use:**
- Need complex analytics queries
- Require ACID transactions
- High cardinality tags (many unique values)

**Example:**
```sql
-- TimescaleDB
CREATE TABLE forecast_evaluations (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    model TEXT NOT NULL,
    forecast_price DOUBLE PRECISION,
    current_price DOUBLE PRECISION,
    action TEXT,
    position_after DOUBLE PRECISION
);

SELECT create_hypertable('forecast_evaluations', 'time');

-- Query: Average forecast error by model
SELECT
    model,
    AVG(ABS(forecast_price - current_price)) AS mae
FROM forecast_evaluations
WHERE ticker = 'SPY'
GROUP BY model
ORDER BY mae;
```

---

### 2. Ray Tune / Optuna for Hyperparameter Optimization

**Current:** Manual strategy parameter tuning

**Alternative:** Automated hyperparameter search

**Ray Tune:**
```python
from ray import tune

def train_strategy(config):
    evaluator = Evaluator(
        threshold_value=config["threshold"],
        execution_size=config["size"],
    )
    results = evaluator.run(ticker="SPY", model="timesfm")
    return {"sharpe": results.sharpe_ratio}

analysis = tune.run(
    train_strategy,
    config={
        "threshold": tune.grid_search([1.0, 2.0, 3.0]),
        "size": tune.grid_search([5.0, 10.0, 20.0]),
    },
)

best = analysis.get_best_config(metric="sharpe", mode="max")
print(f"Best config: {best}")
```

**Optuna:**
```python
import optuna

def objective(trial):
    threshold = trial.suggest_float("threshold", 0.5, 5.0)
    size = trial.suggest_float("size", 5.0, 50.0)

    evaluator = Evaluator(threshold, size)
    results = evaluator.run("SPY", "timesfm")
    return results.sharpe_ratio

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)

print(f"Best params: {study.best_params}")
```

**Pros:**
- Automated search (no manual grid search)
- Smart sampling (Bayesian optimization)
- Parallelizable (run multiple trials)

**Cons:**
- Requires Python integration
- Can be slow for large search spaces
- Risk of overfitting

---

### 3. Message Queue for Async Evaluation

**Current:** Synchronous HTTP calls (blocking)

**Alternative:** Celery + RabbitMQ (async job queue)

**Architecture:**
```
┌─────────────────────┐
│  Orchestrator       │
│  (Go)               │
└─────────┬───────────┘
          │ Publish job to queue
          ↓
┌─────────────────────┐
│  RabbitMQ           │
│  (Message Broker)   │
└─────────┬───────────┘
          │ Workers poll queue
          ↓
┌─────────────────────┐  ┌─────────────────────┐
│  Worker 1 (Python)  │  │  Worker 2 (Python)  │
│  - Fetch data       │  │  - Fetch data       │
│  - Run forecast     │  │  - Run forecast     │
│  - Run trading      │  │  - Run trading      │
│  - Store result     │  │  - Store result     │
└─────────────────────┘  └─────────────────────┘
```

**Benefits:**
- Non-blocking (orchestrator doesn't wait)
- Scalable (add more workers)
- Fault-tolerant (retries on failure)
- Priority queues (high-priority tickers first)

**Example:**
```python
# tasks.py
from celery import Celery

app = Celery('tasks', broker='pyamqp://guest@localhost//')

@app.task
def run_evaluation(ticker, model, config):
    evaluator = Evaluator(config)
    results = evaluator.run(ticker, model)
    results.save_to_influxdb()
    return results.to_dict()

# orchestrator.go
func EnqueueEvaluation(ticker, model string, config Config) (string, error) {
    jobID := uuid.New().String()
    payload := map[string]interface{}{
        "ticker": ticker,
        "model": model,
        "config": config,
    }
    err := publishToQueue("evaluation_queue", payload)
    return jobID, err
}

// Poll for results
func GetEvaluationStatus(jobID string) (string, error) {
    return queryJobStatus(jobID)  // "pending", "running", "completed"
}
```

---

### 4. Policy Engine Upgrades

**Current:** Embedded regex patterns (immutable at runtime)

**Alternatives:**

#### Option A: CEL (Common Expression Language)

```yaml
# data_classification_patterns.yaml
patterns:
  - name: "secret"
    expression: |
      has(data.aws_key) && data.aws_key.matches('AKIA[0-9A-Z]{16}')
    confidence: 0.99

  - name: "pii"
    expression: |
      has(data.ssn) && data.ssn.matches('\\d{3}-\\d{2}-\\d{4}')
    confidence: 0.95
```

**Pros:**
- More expressive (boolean logic, nested conditions)
- Safer than regex (no ReDoS attacks)
- Easier to test

**Cons:**
- Requires CEL library
- Steeper learning curve

#### Option B: OPA (Open Policy Agent)

```rego
# policy.rego
package aleutian.policy

default allow = false

allow {
    not contains_secret(input.content)
    not contains_pii(input.content)
}

contains_secret(content) {
    regex.match("AKIA[0-9A-Z]{16}", content)
}

contains_pii(content) {
    regex.match("\\d{3}-\\d{2}-\\d{4}", content)
}
```

**Pros:**
- Industry standard (used by Kubernetes)
- Policy-as-code (version control, CI/CD)
- Testable (unit tests for policies)

**Cons:**
- Requires OPA server
- Adds dependency

---

### 5. Distributed Tracing Alternatives

**Current:** OTLP → Jaeger

**Alternatives:**

#### Option A: OpenSearch (ELK-compatible)

**Pros:**
- Open-source alternative to Elasticsearch
- Better cost efficiency
- Integrated logs + traces
- No licensing issues

**Cons:**
- Heavier than Jaeger
- More complex setup

#### Option B: Grafana Tempo

**Pros:**
- Cost-efficient (object storage backend: S3, GCS)
- Integrates with Grafana
- Simple to deploy
- No indexing (uses object storage directly)

**Cons:**
- Limited query capabilities (no full-text search)
- Requires Grafana for visualization

**Example:**
```yaml
# docker-compose.yml
tempo:
  image: grafana/tempo:latest
  command: ["-config.file=/etc/tempo.yaml"]
  volumes:
    - ./tempo.yaml:/etc/tempo.yaml
  ports:
    - "3200:3200"  # Tempo HTTP
    - "4317:4317"  # OTLP gRPC

# tempo.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

storage:
  trace:
    backend: s3
    s3:
      bucket: tempo-traces
      endpoint: s3.amazonaws.com
```

---

### 6. API Gateway

**Current:** Direct Gin router (no versioning, no rate limiting)

**Alternative:** Kong / Tyk / Ambassador

**Kong Example:**
```yaml
# kong.yml
_format_version: "2.1"

services:
  - name: orchestrator
    url: http://orchestrator:12210
    routes:
      - name: chat
        paths:
          - /api/chat
        plugins:
          - name: rate-limiting
            config:
              minute: 60
              hour: 1000
          - name: jwt
            config:
              secret_is_base64: false

      - name: evaluation
        paths:
          - /api/evaluate
        plugins:
          - name: request-size-limiting
            config:
              allowed_payload_size: 10  # MB
```

**Benefits:**
- Rate limiting (prevent abuse)
- API versioning (/v1/chat, /v2/chat)
- Authentication (JWT, OAuth2)
- Analytics (request counts, latencies)
- Load balancing (multiple orchestrator instances)

---

### 7. Model Registry / Marketplace

**Current:** Hardcoded model list in evaluator config

**Alternative:** Model registry (like Hugging Face Model Hub)

**Architecture:**
```
┌─────────────────────┐
│  Model Registry     │
│  (PostgreSQL)       │
├─────────────────────┤
│ id | name | version│
│ 1  | timesfm | 2.0 │
│ 2  | chronos | 1.1 │
│ 3  | moirai | 1.0  │
└─────────────────────┘
          ↓
┌─────────────────────┐
│  Orchestrator       │
│  - Query registry   │
│  - Select models    │
│  - Run evaluation   │
└─────────────────────┘
```

**API:**
```go
// GET /api/models
{
  "models": [
    {
      "id": "timesfm-2.0",
      "name": "Google TimesFM 2.0",
      "version": "2.0.500m",
      "parameters": 500000000,
      "supported_horizons": [1, 128],
      "context_size_range": [32, 2048]
    },
    {
      "id": "chronos-t5-base",
      "name": "Amazon Chronos T5 Base",
      "version": "1.0",
      "parameters": 200000000,
      "supported_horizons": [1, 64],
      "context_size_range": [64, 512]
    }
  ]
}

// POST /api/evaluate
{
  "models": ["timesfm-2.0", "chronos-t5-base"],  // From registry
  "tickers": ["SPY", "QQQ"]
}
```

**Benefits:**
- Dynamic model selection
- Version management (rollback to previous model)
- Metadata (parameters, supported horizons)
- A/B testing (compare model versions)

---

## 11. Recommendations & Priority Actions

### Immediate Actions (Week 1)

#### 1. Security Hardening (CRITICAL)

```bash
# Remove hardcoded secrets
git grep -n "your_super_secret_admin_token"
# Replace with:
token := os.Getenv("INFLUXDB_TOKEN")
if token == "" {
    log.Fatal("INFLUXDB_TOKEN required")
}

# Fix WebSocket CORS
# evaluator.go:52
CheckOrigin: func(r *http.Request) bool {
    origin := r.Header.Get("Origin")
    return origin == os.Getenv("ALLOWED_ORIGIN")
},

# Add input validation
go get github.com/go-playground/validator/v10
# Add struct tags:
type ForecastRequest struct {
    Ticker string `validate:"required,uppercase,min=1,max=10"`
    // ...
}
```

#### 2. Test Coverage (HIGH)

```bash
# Create test files for critical handlers
touch services/orchestrator/handlers/evaluator_test.go
touch services/orchestrator/handlers/timeseries_test.go
touch services/orchestrator/handlers/trading_test.go

# Set up mocks
go get github.com/stretchr/testify/mock

# Run tests
go test -v -cover ./...
```

#### 3. Documentation (MEDIUM)

```bash
# Add docstrings to handlers
# evaluator.go
// EvaluateTickerModel runs a forecast evaluation for a single ticker/model pair.
// It generates a forecast, loops through horizons, calls the trading service,
// and stores results in InfluxDB.
func (e *Evaluator) EvaluateTickerModel(
    ctx context.Context,
    ticker string,
    model string,
    config *datatypes.EvaluationConfig,
    currentPrice float64,
) error {
    // ...
}
```

---

### Short-Term (Month 1)

#### 4. Authentication & Authorization

```go
// Add JWT middleware
import "github.com/golang-jwt/jwt/v5"

func AuthMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        tokenString := c.GetHeader("Authorization")
        if tokenString == "" {
            c.JSON(401, gin.H{"error": "Unauthorized"})
            c.Abort()
            return
        }

        token, err := jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
            return []byte(os.Getenv("JWT_SECRET")), nil
        })

        if err != nil || !token.Valid {
            c.JSON(401, gin.H{"error": "Invalid token"})
            c.Abort()
            return
        }

        claims := token.Claims.(jwt.MapClaims)
        c.Set("user_id", claims["user_id"])
        c.Next()
    }
}

// Apply to routes
router.Use(AuthMiddleware())
```

#### 5. Walk-Forward Backtesting

```go
// Add BacktestRollingWindow method
func (e *Evaluator) BacktestRollingWindow(
    ticker string,
    model string,
    startDate, endDate time.Time,
    contextSize, horizonSize int,
) error {
    tradingDays := e.storage.GetTradingDays(ctx, ticker, startDate, endDate)

    for _, day := range tradingDays[contextSize:] {
        window := e.storage.GetHistoricalWindow(ctx, ticker, day, contextSize)
        forecast := e.CallForecastService(ctx, ticker, model, window, horizonSize)

        // Trade on day+1 forecast only
        currentPrice := window[len(window)-1].Close
        signal := e.CallTradingService(ctx, TradingSignalRequest{
            Ticker: ticker,
            ForecastPrice: forecast.Forecast[0],
            CurrentPrice: &currentPrice,
            // ...
        })

        e.storage.StoreResult(ctx, &EvaluationResult{
            Ticker: ticker,
            Model: model,
            ForecastPrice: forecast.Forecast[0],
            CurrentPrice: currentPrice,
            Action: signal.Action,
            // ...
        })
    }

    return nil
}
```

---

### Medium-Term (Quarter 1)

#### 6. Confidence Intervals & Uncertainty

```go
// Update ForecastResult
type ForecastResult struct {
    Name     string      `json:"name"`
    Forecast []float64   `json:"forecast"`  // Mean
    P05      []float64   `json:"p05"`       // 5th percentile
    P50      []float64   `json:"p50"`       // Median
    P95      []float64   `json:"p95"`       // 95th percentile
    StdDev   []float64   `json:"std_dev"`
}

// Store in InfluxDB
for i, mean := range forecast.Forecast {
    p.AddField(fmt.Sprintf("day_%02d_mean", i+1), mean)
    p.AddField(fmt.Sprintf("day_%02d_p05", i+1), forecast.P05[i])
    p.AddField(fmt.Sprintf("day_%02d_p50", i+1), forecast.P50[i])
    p.AddField(fmt.Sprintf("day_%02d_p95", i+1), forecast.P95[i])
}
```

#### 7. Transaction Cost Modeling

```go
type ExecutionModel struct {
    SlippagePercent    float64  // 0.1% typical
    Commission         float64  // $0.005/share
    MarketImpactFactor float64  // 0.01% per $1M notional
}

func (m *ExecutionModel) Simulate(signal TradingSignal, price float64, notional float64) ExecutedTrade {
    slippage := price * m.SlippagePercent
    marketImpact := price * m.MarketImpactFactor * (notional / 1000000)

    executedPrice := price + slippage + marketImpact
    totalCost := signal.Size * executedPrice + m.Commission

    return ExecutedTrade{
        Price: executedPrice,
        Cost: totalCost,
        Slippage: slippage,
        MarketImpact: marketImpact,
    }
}
```

---

### Long-Term (Quarter 2+)

#### 8. Multi-Asset Portfolio

```go
type Portfolio struct {
    Positions map[string]float64  // ticker → size
    Cash      float64
    Margin    float64
    RiskLimits struct {
        MaxDrawdown     float64
        MaxPositionSize float64
        MaxLeverage     float64
    }
}

func (p *Portfolio) Rebalance(targets map[string]float64, prices map[string]float64) []TradingSignal {
    signals := []TradingSignal{}
    totalValue := p.TotalValue(prices)

    for ticker, targetWeight := range targets {
        currentValue := p.Positions[ticker] * prices[ticker]
        currentWeight := currentValue / totalValue

        delta := (targetWeight - currentWeight) * totalValue
        if math.Abs(delta) > totalValue*0.01 {  // 1% threshold
            signals = append(signals, TradingSignal{
                Ticker: ticker,
                Size: delta / prices[ticker],
            })
        }
    }

    return signals
}
```

#### 9. Baseline Comparison & Metrics

```go
func CompareToBuyAndHold(
    strategyResults []EvaluationResult,
    ticker string,
    startDate, endDate time.Time,
) ComparisonReport {
    // Calculate strategy return
    strategyReturn := 0.0
    for _, r := range strategyResults {
        strategyReturn += r.PortfolioValue
    }
    strategyReturn = (strategyReturn - 100000) / 100000  // Assume $100k initial

    // Calculate buy-and-hold return
    startPrice := GetPrice(ticker, startDate)
    endPrice := GetPrice(ticker, endDate)
    buyHoldReturn := (endPrice - startPrice) / startPrice

    // Calculate metrics
    returns := extractReturns(strategyResults)
    sharpe := calculateSharpe(returns)
    maxDrawdown := calculateMaxDrawdown(returns)

    return ComparisonReport{
        StrategyReturn: strategyReturn,
        BuyHoldReturn: buyHoldReturn,
        Alpha: strategyReturn - buyHoldReturn,
        SharpeRatio: sharpe,
        MaxDrawdown: maxDrawdown,
    }
}
```

---

## Summary Table: Action Priority Matrix

| Priority | Action | Impact | Effort | Timeline |
|----------|--------|--------|--------|----------|
| 🔴 **CRITICAL** | Remove hardcoded secrets | Security | Low | Week 1 |
| 🔴 **CRITICAL** | Fix WebSocket CORS | Security | Low | Week 1 |
| 🔴 **CRITICAL** | Add authentication | Security | High | Month 1 |
| 🟠 **HIGH** | Add input validation | Reliability | Medium | Week 2 |
| 🟠 **HIGH** | Write tests for evaluator | Quality | High | Month 1 |
| 🟠 **HIGH** | Implement walk-forward backtest | Feature | High | Month 1 |
| 🟡 **MEDIUM** | Add confidence intervals | Feature | Medium | Quarter 1 |
| 🟡 **MEDIUM** | Transaction cost modeling | Accuracy | Medium | Quarter 1 |
| 🟢 **LOW** | Multi-asset portfolio | Feature | High | Quarter 2 |
| 🟢 **LOW** | Baseline comparison | Analysis | Low | Quarter 2 |

---

## Final Verdict

**AleutianLocal is a SOLID FOUNDATION** for building a financial forecast evaluation system, but requires **significant security hardening** and **backtesting framework development** before production use.

**Best For:**
- Internal use (single user / small team)
- Research & development (model comparison)
- Offline-first deployments (air-gapped networks)
- Privacy-sensitive applications (regulated industries)

**Not Recommended For:**
- Public-facing applications (no auth)
- Multi-tenant SaaS (no user isolation)
- Real-time trading (synchronous evaluation)
- Production backtesting (missing walk-forward framework)

**Overall Grade: C+ (70%)**
- Architecture: A-
- Security: D+
- Testing: D
- Financial Evaluation: B-
- Production Readiness: 65%

**Recommendation:** Invest 1-2 months in security + testing + backtesting before using for critical financial analysis.

---

**End of Technical Analysis**
