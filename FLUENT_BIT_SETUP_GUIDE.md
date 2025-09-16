# Fluent Bit Learning Project - Complete Setup Guide

## Overview
This project demonstrates a complete Fluent Bit log aggregation and forwarding system using Docker Compose. It shows how to collect system metrics and application logs, then forward them to a custom HTTP endpoint for processing.

## What We Built

### Architecture
```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   System Logs   │    │              │    │   FastAPI App   │
│   CPU Metrics   │───▶│  Fluent Bit  │───▶│   (Receiver)    │
│   App Logs      │    │              │    │                 │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │                       │
                              ▼                       ▼
                       ┌─────────────┐         ┌─────────────┐
                       │ File Output │         │ ingest.log  │
                       │ (Optional)  │         │ (HTTP logs) │
                       └─────────────┘         └─────────────┘
```

### Components
1. **FastAPI Application**: HTTP server that receives and processes logs
2. **Fluent Bit**: Log collector and forwarder
3. **Docker Compose**: Container orchestration
4. **Log Files**: Persistent storage for collected data

## Technologies Used

### Core Technologies
- **Fluent Bit**: Open-source log processor and forwarder
- **FastAPI**: Modern Python web framework for APIs
- **Docker & Docker Compose**: Containerization and orchestration
- **Python**: Programming language for the receiver application
- **Uvicorn**: ASGI server for FastAPI

### Libraries & Dependencies
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `threading`: Background log generation
- `json`: Data serialization
- `logging`: Python logging framework

## What We Did - Step by Step

### 1. Initial Setup Issues
- **Problem**: Port 8000 was already in use on the system
- **Solution**: Changed all services to use port 8006
- **Files Modified**: `compose.yaml`, `fluent-bit.conf`

### 2. Fixed FastAPI Application Name Issue
- **Problem**: Uvicorn was looking for `app` but FastAPI instance was named `APP`
- **Solution**: Updated Docker Compose command to use `main:APP`
- **File Modified**: `compose.yaml`

### 3. Added Custom Logging Endpoint
- **What**: Created `/test-logs` endpoint to generate realistic application logs
- **Purpose**: Demonstrate how Fluent Bit captures application logs in real-time
- **Features**: 
  - Generates random user actions (login, logout, search, etc.)
  - Creates different log levels (INFO, WARNING, ERROR)
  - Simulates real application scenarios

### 4. Configured Fluent Bit
- **Input Sources**:
  - CPU metrics collection
  - Application log file monitoring (`/logs/app/app.log`)
- **Output Destination**: HTTP endpoint (`app:8006/ingest`)
- **Format**: JSON for structured data

## How to Test if It's Working

### 1. Start the Services
```bash
docker compose up --build
```

### 2. Health Check
Test if the FastAPI app is running:
```bash
curl http://localhost:8006/
# Expected: {"status":"ok"}
```

### 3. Generate Custom Logs
Trigger the custom logging endpoint:
```bash
curl http://localhost:8006/test-logs
# Expected: {"status":"success","message":"Generated logs for user XXXX action YYYY","logs_generated":4}
```

### 4. Verify Log Collection
Check if Fluent Bit is forwarding logs:
```bash
# View the last 20 lines of collected logs
tail -20 _data/logs/received/ingest.log

# Watch logs in real-time
tail -f _data/logs/received/ingest.log
```

### 5. Check Service Status
```bash
# View running containers
docker compose ps

# Check Fluent Bit logs
docker compose logs fluent-bit

# Check FastAPI app logs
docker compose logs app
```

## Expected Output Examples

### CPU Metrics (from Fluent Bit)
```json
{
  "date": 1757999144.866644,
  "cpu_p": 4.0,
  "user_p": 2.625,
  "system_p": 1.375,
  "cpu0.p_cpu": 7.0,
  "cpu1.p_cpu": 6.0,
  ...
}
```

### Application Logs (from /test-logs endpoint)
```json
{
  "date": 1757999144.559988,
  "log": "2025-09-16 05:05:44,554 INFO User 5187 performed action: logout"
}
{
  "date": 1757999144.563278,
  "log": "2025-09-16 05:05:44,559 ERROR Simulated error: Database connection timeout for user 5187"
}
```

### Heartbeat Logs (automatic from FastAPI app)
```json
{
  "date": 1757999143.401391,
  "log": "2025-09-16 05:05:43,393 INFO {\"event\": \"heartbeat\", \"counter\": 5, \"component\": \"demo-app\"}"
}
```

## File Structure
```
learn_fluentbit/
├── app/
│   ├── Dockerfile
│   ├── main.py              # FastAPI application
│   └── requirements.txt     # Python dependencies
├── fluent-bit/
│   ├── fluent-bit.conf     # Fluent Bit configuration
│   └── parsers.conf        # Log parsing rules
├── _data/
│   └── logs/
│       ├── app/            # Application logs (source)
│       ├── collected/      # File output (alternative)
│       └── received/       # HTTP forwarded logs
│           └── ingest.log  # Final collected data
├── compose.yaml            # Docker Compose configuration
└── FLUENT_BIT_SETUP_GUIDE.md  # This documentation
```

## Configuration Details

### Docker Compose (compose.yaml)
- **App Service**: Runs on port 8006, mounts log directories
- **Fluent Bit Service**: Depends on app, uses custom configuration
- **Volumes**: Shared log directories between containers

### Fluent Bit Configuration (fluent-bit.conf)
```ini
[INPUT]
    Name   tail                    # Monitor log files
    Path   /logs/app/app.log      # Application log file
    Tag    app.log

[INPUT]
    Name   cpu                     # Collect CPU metrics
    Tag    metrics.cpu

[OUTPUT]
    Name   http                    # Forward via HTTP
    Match  *                      # All inputs
    Host   app                    # FastAPI container
    Port   8006                   # Custom port
    URI    /ingest                # Endpoint path
    Format json                   # JSON format
```

### FastAPI Application Features
- **Health endpoint**: `GET /` for service checks
- **Log ingestion**: `POST /ingest` receives Fluent Bit data
- **Test endpoint**: `GET /test-logs` generates sample logs
- **Background logging**: Automatic heartbeat messages every 5 seconds

## Troubleshooting

### Common Issues
1. **Port conflicts**: Change port 8006 to another available port
2. **Container startup order**: Fluent Bit depends on the app service
3. **Log file permissions**: Ensure Docker has access to log directories
4. **Network connectivity**: Containers communicate via Docker network

### Debug Commands
```bash
# Check container logs
docker compose logs [service-name]

# Restart specific service
docker compose restart [service-name]

# Rebuild and restart
docker compose up --build

# Stop all services
docker compose down
```

## Learning Outcomes

This project demonstrates:
- **Log Aggregation**: Collecting logs from multiple sources
- **Real-time Processing**: Immediate forwarding of log data
- **Containerization**: Using Docker for consistent environments
- **HTTP APIs**: Building endpoints for data ingestion
- **Configuration Management**: Setting up Fluent Bit inputs/outputs
- **Monitoring**: Understanding system metrics collection
- **Debugging**: Troubleshooting containerized applications

## Next Steps

To extend this project, consider:
1. Adding more input sources (database logs, web server logs)
2. Implementing log filtering and parsing
3. Adding authentication to the HTTP endpoint
4. Setting up log rotation and retention policies
5. Integrating with monitoring systems (Prometheus, Grafana)
6. Adding alerting based on log patterns
