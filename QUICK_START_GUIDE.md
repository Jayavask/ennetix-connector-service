# Quick Start Guide - Testing P1 Integration

## Step 1: Install Dependencies

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
source venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Verify Imports Work

```bash
python3 test_imports.py
```

This will verify all modules can be imported correctly.

## Step 3: Verify Logic is Preserved

```bash
python3 verify_logic.py
```

This checks that all original P1 logic is intact.

## Step 4: Start the Service

```bash
python3 -m app.main
```

Or with auto-reload:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will start on `http://localhost:8000`

## Step 5: Test Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Test P1 Endpoint (in another terminal)
```bash
curl -X POST http://localhost:8000/api/v1/p1/sync \
  -H "Content-Type: application/json" \
  -v
```

### Test with Custom Date Range
```bash
curl -X POST http://localhost:8000/api/v1/p1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01T00:00:00.000Z",
    "end_date": "2024-01-31T23:59:59.000Z"
  }'
```

## Step 6: Monitor Logs

Watch the service logs to see:
- ✅ P1 process starting
- ✅ Threats being fetched
- ✅ Alerts being processed
- ✅ Documents being indexed to CS1 (ennetix-threats1, ennetix-logs1, ennetix-flows1)
- ✅ Summary statistics

## What to Verify

### ✅ Original Logic Preserved

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

4. **Error Handling:**
   - Authentication handling (xauth/username-password) ✅
   - HTML response detection (login page) ✅
   - Retry with exponential backoff ✅

### ✅ Microservice Structure

- Code organized into proper modules ✅
- Configuration via environment variables ✅
- Structured logging ✅
- FastAPI endpoints ✅
- Background task processing ✅

## Troubleshooting

### If imports fail:
```bash
# Make sure you're in the project root
pwd
# Should show: /home/spurge/ecs-connector/ennetix-connector-service

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### If service won't start:
```bash
# Check .env file exists
ls -la .env

# Test config loading
python3 -c "from app.config import settings; print('Config OK')"
```

### If P1 endpoint returns error:
- Check service logs for details
- Verify `.env` has all required credentials
- Test Ennetix API connectivity manually

## Expected Behavior

When you call `/api/v1/p1/sync`:

1. **Immediate Response:**
   ```json
   {
     "status": "accepted",
     "message": "P1 sync started - pulling data from Ennetix API",
     "process": "P1 - Populate using Ennetix API"
   }
   ```

2. **Background Process:**
   - Fetches threats from Ennetix API
   - Processes each alert (fetches logs and flows)
   - Stores data in Cygeniq ES indices
   - Logs progress and summary

3. **Check Logs:**
   - Look for "P1 Script completed!" message
   - Check summary statistics at the end

## Verify Data Was Stored

After P1 completes, check Cygeniq Elasticsearch:

```bash
# Count documents in each index
curl -u elastic:password "https://your-cygeniq-es:9200/ennetix-threats1/_count"
curl -u elastic:password "https://your-cygeniq-es:9200/ennetix-logs1/_count"
curl -u elastic:password "https://your-cygeniq-es:9200/ennetix-flows1/_count"
```

## Next Steps

Once P1 is verified working:
- Test P2 (Create Raw Alert) - reads from CS1, creates raw alerts in CS2
- Test P3 (Create Canonical Alert) - reads from CS2, creates ECS alerts

