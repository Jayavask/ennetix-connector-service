## ennetix-connector-service

**Goal**: Python microservice that accepts threat data (from Ennetix) and exposes simple APIs for other services to consume.

### 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

---

### 🚀 Quick Start Guide

#### Step 1: Setup Environment

Create a `.env` file in the project root with your configuration:

```bash
# Elasticsearch configuration (for future use)
ELASTICSEARCH_HOSTS="https://demoes.xvisor.ai"
ELASTICSEARCH_USERNAME="cygeniqdev"
ELASTICSEARCH_PASSWORD="TidxPass@54321"
ELASTICSEARCH_VERIFY_CERTS="true"
ELASTICSEARCH_REQUEST_TIMEOUT=100
ELASTICSEARCH_MAX_RETRIES=10

# Ennetix API configuration
ENNETIX_API_BASE_URL="https://demo.xvisor.ai"
ENNETIX_API_ENDPOINT="/alerts/ip/threats.json"

# Ennetix Authentication (required - choose one method)
# Option 1: xauth JWT Token (recommended for xVisor)
ENNETIX_XAUTH="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImFkbWluQGVubmV0aXguY29tIiwiZXhwIjoxNzg3NzMxOTkxfQ.1zZEtlnIsvpGipKuoXebPy5npV52O_rA-PfsdMVH4K8"

# Option 2: Username/Password (Basic Auth)
# ENNETIX_USERNAME="your_username"
# ENNETIX_PASSWORD="your_password"

# Option 3: API Key (if supported)
# ENNETIX_API_KEY="your_api_key"

# Connector service URL
CONNECTOR_SERVICE_URL="http://localhost:8000"
```

#### Step 2: Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

#### Step 3: Run the Microservice

**Terminal 1** - Start the microservice:

```bash
uvicorn app.main:app --reload --port 8000
```

✅ The service will be available at:
- **API**: `http://localhost:8000`
- **Interactive Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

#### Step 4: Run the Threat Puller Script

**Terminal 2** (keep Terminal 1 running) - Fetch threats from Ennetix:

Make sure you're in the project root directory:

```bash
cd /home/spurge/EnCnSr-MicroService
python scripts/pull_ennetix_threats.py
```

Or if you're already in the project root:

```bash
python scripts/pull_ennetix_threats.py
```

This script will:
1. 🔍 Fetch threats from the Ennetix API (`https://demo.xvisor.ai/alerts/ip/threats.json`)
2. 📊 Print the raw API response and parsed threats
3. 📤 Send the threats to your connector service at `"https://k8s-elastics-elastics-f997d45943-a13c2fc4f6b88171.elb.us-east-2.amazonaws.com:9200/"`

---

### 📝 What You'll See

When you run the script, you'll see:
- The API endpoint being called
- Date range used for the query
- Raw API response (first item sample)
- Total number of threats fetched
- Sample parsed threats (first 3)
- Confirmation of successful send to connector service

---

### 🔧 API Endpoints

The microservice exposes:

- `GET /health` - Health check endpoint
- `POST /threats/bulk` - Accept bulk threat ingestion
- `GET /threats` - List all ingested threats

Visit `http://localhost:8000/docs` for interactive API documentation.

---

### ⚙️ Configuration

You can customize the date range in the script by modifying the `get_date_range()` function or passing custom dates to `fetch_threats_from_ennetix()`.
