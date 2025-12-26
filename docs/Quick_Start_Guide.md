# Complete Guide - ENNETIX Connector Service (P1 & P2)

This guide covers everything you need to run both P1 (Pull data from Ennetix API) and P2 (Create Raw Alert) processes.

---

## Table of Contents

1. [Setup & Installation](#setup--installation)
2. [Starting the Service](#starting-the-service)
3. [Phase 1 (P1) - Pull Data from Ennetix API](#phase-1-p1---pull-data-from-ennetix-api)
4. [Phase 2 (P2) - Create Raw Alert](#phase-2-p2---create-raw-alert)
5. [Complete Workflow: P1 → P2](#complete-workflow-p1--p2)
6. [Troubleshooting](#troubleshooting)
7. [API Documentation](#api-documentation)

---

## Setup & Installation

### Step 1: Install Dependencies

```bash
cd /home/spurge/ecs-connector/ennetix-connector-service
pip install -r requirements.txt
```

If you get permission errors, use:
```bash
pip install --user -r requirements.txt
```

Or use a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Verify Imports Work

```bash
python3 test_imports.py
```

This will verify all modules can be imported correctly.

### Step 3: Verify Logic is Preserved

```bash
python3 verify_logic.py
```

This checks that all original logic is intact.

### Step 4: Verify Configuration

Check that your `.env` file has all required variables:

```bash
cat .env
```

Required variables:
- `ENNETIX_API_BASE_URL`
- `ENNETIX_XAUTH` or `ENNETIX_ELASTICSEARCH_USERNAME`/`ENNETIX_ELASTICSEARCH_PASSWORD`
- `CONNECTOR_SERVICE_URL`
- `ELASTICSEARCH_CYGENIQ_USERNAME`
- `ELASTICSEARCH_CYGENIQ_PASSWORD`

---

## Starting the Service

### Option A: Direct Python

```bash
python3 -m app.main
```

### Option B: Using Uvicorn directly

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will start on `http://localhost:8000`

### Verify Service is Running

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "ennetix-connector-service"
}
```

---

## Phase 1 (P1) - Pull Data from Ennetix API

### P1 API Endpoint

**Endpoint:** `POST /api/v1/p1/sync`

This endpoint triggers the P1 process that:
1. Fetches threats from Ennetix API
2. Fetches logs and flows for each alert
3. Stores raw API output data in Cygeniq Elasticsearch (CS1 indices: `ennetix-threats1`, `ennetix-logs1`, `ennetix-flows1`)

### Test P1 Endpoint

#### Option 1: Using curl (Default date range - last 30 days)

```bash
curl -X POST http://localhost:8000/api/v1/p1/sync \
  -H "Content-Type: application/json" \
  -v
```

#### Option 2: Using curl (With custom date range)

```bash
curl -X POST http://localhost:8000/api/v1/p1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01T00:00:00.000Z",
    "end_date": "2024-01-31T23:59:59.000Z"
  }'
```

#### Option 3: Using Python requests

```python
import requests

url = "http://localhost:8000/api/v1/p1/sync"
response = requests.post(url, json={})
print(response.json())
```

#### Option 4: Using Swagger UI

1. Open browser: http://localhost:8000/docs
2. Find the `/api/v1/p1/sync` endpoint
3. Click "Try it out"
4. Click "Execute"

### Expected Response

**Immediate Response (HTTP 200):**
```json
{
  "status": "accepted",
  "message": "P1 sync started - pulling data from Ennetix API",
  "process": "P1 - Populate using Ennetix API"
}
```

**Note:** The actual processing happens in the background. Check the service logs to see progress.

### Monitor P1 Process

Watch the service logs to see:

1. **Initialization:**
   ```
   🚀 Ennetix API -> Cygeniq ECS Data Puller (P1)
   📅 Date range: 2024-01-01T00:00:00.000Z to 2024-01-31T23:59:59.000Z
   ```

2. **Fetching Threats:**
   ```
   STEP 1: Fetching threats from Ennetix API (API 1)
   ✅ Fetched X threat entries
   ```

3. **Processing Alerts:**
   ```
   📋 Processing X threat entries...
   📦 Processing batch 1/N (alerts 1-200)...
   ✅ Batch 1 completed
   ```

4. **Storing Data:**
   ```
   STEP 3: Storing data in Cygeniq Elasticsearch (CS1)
   📤 Indexing X threats documents...
   ✅ Indexed X documents, 0 errors
   ```

5. **Summary:**
   ```
   📊 Summary
   Threats processed: X
   Alerts processed: Y
   Threats indexed: X/Y
   Logs indexed: A/B
   Flows indexed: C/D
   ✨ P1 Script completed!
   ```

### Verify P1 Data Was Stored

After P1 completes, verify data in Cygeniq Elasticsearch:

```bash
# Count documents in each CS1 index
curl -u elastic:password "https://your-cygeniq-es:9200/ennetix-threats1/_count?pretty"
curl -u elastic:password "https://your-cygeniq-es:9200/ennetix-logs1/_count?pretty"
curl -u elastic:password "https://your-cygeniq-es:9200/ennetix-flows1/_count?pretty"

# Get a sample document
curl -u elastic:password "https://your-cygeniq-es:9200/ennetix-threats1/_search?size=1&pretty"
```

### P1 Features

#### ✅ Original Logic Preserved

1. **Three API Calls:**
   - API 1: `/alerts/ip/threats.json` ✅
   - API 2: `/alerts/{ip}/{signatureId}/logs.json` ✅
   - API 3: `/security/{ip}/flows.json` ✅

2. **Processing Logic:**
   - Signature ID extraction from earliest timestamp ✅
   - Flow matching by timestamp ✅
   - Concurrency control with semaphores ✅
   - Retry logic for 500 errors ✅

3. **Data Storage:**
   - Three indices: threats1, logs1, flows1 ✅
   - Bulk indexing with custom _id fields ✅
   - Index auto-creation ✅
   - **Batch processing with immediate push to ES** ✅

4. **Error Handling:**
   - Authentication handling (xauth/username-password) ✅
   - HTML response detection (login page) ✅
   - Retry with exponential backoff ✅

---

## Phase 2 (P2) - Create Raw Alert

### P2 API Endpoint

**Endpoint:** `POST /api/v1/p2/sync`

This endpoint triggers the P2 process that:
1. Reads data from CS1 indices (ennetix-threats1, ennetix-logs1, ennetix-flows1)
2. Builds raw alert documents
3. Stores in CS2 index (c-ecs-raw-alert1)

### Prerequisites

**Important:** P2 requires P1 to be completed first!

- ✅ P1 must have run successfully
- ✅ CS1 indices must contain data:
  - `ennetix-threats1` - must have threat documents
  - `ennetix-logs1` - must have log documents  
  - `ennetix-flows1` - must have flow documents

### Verify P1 Data Exists (Before Running P2)

Before running P2, verify that P1 data exists in CS1 indices:

```bash
# Check threats index
curl -u elastic:password \
  "https://your-cygeniq-es:9200/ennetix-threats1/_count?pretty"

# Check logs index
curl -u elastic:password \
  "https://your-cygeniq-es:9200/ennetix-logs1/_count?pretty"

# Check flows index
curl -u elastic:password \
  "https://your-cygeniq-es:9200/ennetix-flows1/_count?pretty"
```

If all show 0 documents, run P1 first!

### Test P2 Endpoint

#### Option 1: Using curl

```bash
curl -X POST http://localhost:8000/api/v1/p2/sync \
  -H "Content-Type: application/json" \
  -v
```

#### Option 2: Using curl (with pretty output)

```bash
curl -X POST http://localhost:8000/api/v1/p2/sync \
  -H "Content-Type: application/json" | jq .
```

#### Option 3: Using Python requests

```python
import requests

url = "http://localhost:8000/api/v1/p2/sync"
response = requests.post(url)
print(response.json())
```

#### Option 4: Using httpie

```bash
http POST http://localhost:8000/api/v1/p2/sync
```

#### Option 5: Using the Swagger UI

1. Open browser: http://localhost:8000/docs
2. Find the `/api/v1/p2/sync` endpoint
3. Click "Try it out"
4. Click "Execute"

### Expected Response

**Immediate Response (HTTP 200):**
```json
{
  "status": "accepted",
  "message": "P2 sync started - creating raw alerts from CS1 data",
  "process": "P2 - Create Raw Alert"
}
```

**Note:** The actual processing happens in the background. Check the service logs to see progress.

### Monitor P2 Process

Watch the service logs to see:

1. **Initialization:**
   ```
   🚀 Phase 2: Create Raw Alerts from Cygeniq ECS
   CS1 (API Output Data) -> P2 (Create Raw Alert) -> CS2 (Raw Alert)
   ```

2. **Fetching Data:**
   ```
   STEP 1: Fetching data from all 3 indexes
   📋 Index 1: ennetix-threats1
   ✅ Fetched X threats
   📋 Index 2: ennetix-logs1
   ✅ Fetched X log documents for Y unique alert_ids
   📋 Index 3: ennetix-flows1
   ✅ Fetched X flow documents for Y unique alert_ids
   ```

3. **Processing:**
   ```
   STEP 2: Processing threats and building raw alerts (batch-wise)
   📦 Processing batch 1/N (alerts 1-100)...
   📤 Indexing X raw alert documents from batch 1...
   ✅ Batch 1 indexed: X documents, 0 errors (Total: X)
   ```

4. **Summary:**
   ```
   📊 Summary
   Threats processed: X
   Batches processed: Y
   Raw alerts indexed: Z
   Errors: 0
   ✨ Phase 2 completed!
   ```

### Verify P2 Data Was Stored

After P2 completes, verify data in CS2 index:

```bash
# Count documents in raw alert index
curl -u elastic:password \
  "https://your-cygeniq-es:9200/c-ecs-raw-alert1/_count?pretty"

# Get a sample document
curl -u elastic:password \
  "https://your-cygeniq-es:9200/c-ecs-raw-alert1/_search?size=1&pretty"
```

---

## Complete Workflow: P1 → P2

### Step 1: Run P1 (Pull Data from Ennetix API)

```bash
curl -X POST http://localhost:8000/api/v1/p1/sync \
  -H "Content-Type: application/json"
```

Wait for P1 to complete (check logs). You should see:
- Threats fetched from Ennetix API
- Alerts processed in batches
- Data stored in CS1 indices (threats1, logs1, flows1)
- Summary statistics

### Step 2: Verify P1 Data

```bash
# Check P1 data (CS1)
curl -u elastic:password "https://your-es:9200/ennetix-threats1/_count"
curl -u elastic:password "https://your-es:9200/ennetix-logs1/_count"
curl -u elastic:password "https://your-es:9200/ennetix-flows1/_count"
```

### Step 3: Run P2 (Create Raw Alert)

```bash
curl -X POST http://localhost:8000/api/v1/p2/sync \
  -H "Content-Type: application/json"
```

Wait for P2 to complete (check logs). You should see:
- Data fetched from CS1 indices
- Raw alerts built and processed in batches
- Data stored in CS2 index (c-ecs-raw-alert1)
- Summary statistics

### Step 4: Verify P2 Data

```bash
# Check P2 data (CS2)
curl -u elastic:password "https://your-es:9200/c-ecs-raw-alert1/_count"
```

---

## Troubleshooting

### Setup Issues

#### If imports fail:
```bash
# Make sure you're in the project root
pwd
# Should show: /home/spurge/ecs-connector/ennetix-connector-service

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### If service won't start:
```bash
# Check .env file exists
ls -la .env

# Test config loading
python3 -c "from app.config import settings; print('Config OK')"

# Check if port 8000 is already in use
lsof -i :8000
```

### P1 Issues

#### P1 endpoint returns error:
- Check service logs for detailed error messages
- Verify `.env` has all required credentials
- Test Ennetix API connectivity manually
- Verify `ENNETIX_XAUTH` or username/password is correct

#### No data in CS1 indices:
- Check Cygeniq ES connection in logs
- Verify credentials in `.env`
- Check if indices were created: `curl .../_cat/indices/ennetix-*`

#### Authentication errors:
- Verify `ENNETIX_XAUTH` or `ENNETIX_ELASTICSEARCH_USERNAME`/`PASSWORD` in `.env`
- Check if token is expired
- Test API manually with credentials

### P2 Issues

#### P2 returns 404 error:
- Make sure service is running and P2 router is registered
- Check service logs for startup errors
- Verify you're using the correct endpoint: `/api/v1/p2/sync`

#### P2 returns error immediately:
- Check service logs for detailed error messages
- Verify CS1 indices exist and have data
- Check Cygeniq ES connection

#### No data in CS2 index:
- Verify P1 completed successfully
- Check if CS1 indices have data
- Review logs for processing errors

#### "No threats found" error:
- Run P1 first to populate CS1 indices
- Check if indices are named correctly (ennetix-threats1, etc.)

#### Connection errors:
- Verify Cygeniq ES credentials in `.env`
- Test ES connectivity manually
- Check network/firewall settings

---

## API Documentation

Once the service is running, view interactive API docs at:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

You can test both P1 and P2 endpoints directly from the Swagger UI!

---

## Quick Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/ready` | GET | Readiness check (tests ES connections) |
| `/api/v1/p1/sync` | POST | Trigger P1 - Pull data from Ennetix API |
| `/api/v1/p2/sync` | POST | Trigger P2 - Create Raw Alert from CS1 |

### Indices

| Index | Phase | Description |
|-------|-------|-------------|
| `ennetix-threats1` | CS1 (P1) | Threat documents from Ennetix API |
| `ennetix-logs1` | CS1 (P1) | Log documents from Ennetix API |
| `ennetix-flows1` | CS1 (P1) | Flow documents from Ennetix API |
| `c-ecs-raw-alert1` | CS2 (P2) | Raw alert documents |

### Performance Tuning

#### P1 Performance Settings (in `.env`):
```bash
ENNETIX_API_BATCH_SIZE=200        # Concurrent alert processing
ENNETIX_API3_BATCH_SIZE=20        # Concurrent flow API calls
BATCH_SIZE=500                    # Bulk indexing batch size
ENNETIX_API3_DELAY=0.05          # Delay between API 3 calls
```

#### P2 Performance Settings (in `.env`):
```bash
RAW_ALERT_PROCESSING_BATCH_SIZE=100  # Threats processed per batch
BATCH_SIZE=500                      # Bulk indexing batch size
```

---

## Summary

### P1 Endpoint
- **URL:** `POST http://localhost:8000/api/v1/p1/sync`
- **Request Body (optional):**
  ```json
  {
    "start_date": "2024-01-01T00:00:00.000Z",
    "end_date": "2024-01-31T23:59:59.000Z"
  }
  ```
- **Response:**
  ```json
  {
    "status": "accepted",
    "message": "P1 sync started - pulling data from Ennetix API",
    "process": "P1 - Populate using Ennetix API"
  }
  ```

### P2 Endpoint
- **URL:** `POST http://localhost:8000/api/v1/p2/sync`
- **Request Body:** None required (empty body or `{}`)
- **Response:**
  ```json
  {
    "status": "accepted",
    "message": "P2 sync started - creating raw alerts from CS1 data",
    "process": "P2 - Create Raw Alert"
  }
  ```

Both processes run in the background. Monitor logs to see progress and completion.

---

## Next Steps

Once P1 and P2 are verified working:
- Test P3 (Create Canonical Alert) - reads from CS2, creates ECS alerts
- Monitor performance and adjust batch sizes as needed
- Set up automated scheduling if needed

