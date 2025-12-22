FROM --platform=linux/arm64 golang:1.25-alpine AS builder

WORKDIR /src
# Copy go.mod and go.sum first to leverage Docker layer caching
COPY go.mod go.sum ./
RUN go mod download

# Copy the rest of the source code
COPY . .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o /app/finance-data-service ./main.go

# --- Final Image ---
# Use a minimal Alpine image
FROM --platform=linux/arm64 alpine:latest

RUN apk update && \
    apk add --no-cache \
        git \
        curl

WORKDIR /app
# Copy only the compiled binary from the builder stage
COPY --from=builder /app/finance-data-service .
# Add SSL certificates needed for HTTPS calls to Yahoo Finance
RUN apk add --no-cache ca-certificates
RUN chmod +x /app/finance-data-service
# Command to run the service
CMD ["/app/finance-data-service"]