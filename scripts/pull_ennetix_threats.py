import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from dotenv import load_dotenv

from app.schemas import Threat, ThreatInBulk


# Load variables from .env
load_dotenv()

# Ennetix API configuration
ENNETIX_API_BASE_URL = os.getenv("ENNETIX_API_BASE_URL", "https://demo.xvisor.ai")
ENNETIX_API_ENDPOINT = os.getenv("ENNETIX_API_ENDPOINT", "/alerts/ip/threats.json")
ENNETIX_USERNAME = os.getenv("ENNETIX_USERNAME")
ENNETIX_PASSWORD = os.getenv("ENNETIX_PASSWORD")
ENNETIX_API_KEY = os.getenv("ENNETIX_API_KEY")  # Alternative: API key authentication
ENNETIX_XAUTH = os.getenv("ENNETIX_XAUTH")  # JWT token authentication (xauth header)

# Date range configuration (optional - if not set, uses last 7 days)
ENNETIX_START_DATE = os.getenv("ENNETIX_START_DATE")  # e.g., "2025-12-02T06:30:00.000Z"
ENNETIX_END_DATE = os.getenv("ENNETIX_END_DATE")  # e.g., "2025-12-09T06:30:00.000Z"

# Connector service configuration
CONNECTOR_SERVICE_URL = os.getenv("CONNECTOR_SERVICE_URL")


def get_date_range(days_back: int = 7) -> Tuple[str, str]:
    """Generate date range for API query (default: last 7 days)."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)
    return (
        start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    )


async def fetch_threats_from_ennetix(client: httpx.AsyncClient, start_date: str = None, end_date: str = None) -> List[Threat]:
    """Fetch threats from Ennetix API.
    
    Date range can be set via:
    1. Function parameters (start_date, end_date)
    2. Environment variables (ENNETIX_START_DATE, ENNETIX_END_DATE)
    3. Auto-generated (last 7 days) if not specified
    """
    
    # Use environment variables if function parameters not provided
    if not start_date:
        start_date = ENNETIX_START_DATE
    if not end_date:
        end_date = ENNETIX_END_DATE
    
    # Auto-generate date range if still not set
    if not start_date or not end_date:
        start_date, end_date = get_date_range()
    
    url = f"{ENNETIX_API_BASE_URL}{ENNETIX_API_ENDPOINT}"
    params = {
        "start": start_date,
        "end": end_date
    }
    
    # Prepare authentication headers
    headers = {}
    auth = None
    
    if ENNETIX_XAUTH:
        # JWT token authentication (xauth header)
        headers["xauth"] = ENNETIX_XAUTH
        print(f"\n🔐 Using xauth token authentication")
        print(f"   Token loaded: {ENNETIX_XAUTH[:30]}...")
        print(f"   Header 'xauth' will be sent with request")
    elif ENNETIX_API_KEY:
        # API key authentication
        headers["Authorization"] = f"Bearer {ENNETIX_API_KEY}"
        print(f"\n🔐 Using API key authentication")
    elif ENNETIX_USERNAME and ENNETIX_PASSWORD:
        # Basic authentication
        auth = (ENNETIX_USERNAME, ENNETIX_PASSWORD)
        print(f"\n🔐 Using basic authentication (username: {ENNETIX_USERNAME})")
    else:
        print(f"\n⚠️  Warning: No authentication credentials found in .env")
        print("   The API may require authentication. Add ENNETIX_XAUTH, ENNETIX_USERNAME/ENNETIX_PASSWORD, or ENNETIX_API_KEY to .env")
    
    print(f"\n🔍 Fetching threats from: {url}")
    print(f"📅 Date range: {start_date} to {end_date}")
    if headers:
        print(f"📤 Request headers: {list(headers.keys())}")
    
    # Configure client to follow redirects but raise on auth errors
    # Try with headers first
    resp = await client.get(
        url, 
        params=params, 
        headers=headers,
        auth=auth,
        timeout=60,
        follow_redirects=False  # Don't follow redirects automatically so we can check
    )
    
    # If we get redirected and have xauth, try using it as a cookie instead
    if resp.status_code == 302 and ENNETIX_XAUTH and not headers.get("Cookie"):
        print(f"\n🔄 Got redirect, trying xauth as cookie instead...")
        cookies = {"xauth": ENNETIX_XAUTH}
        resp = await client.get(
            url,
            params=params,
            cookies=cookies,
            timeout=60,
            follow_redirects=False
        )
        print(f"📥 Response status (with cookie): {resp.status_code}")
    
    print(f"\n📥 Response status: {resp.status_code}")
    
    # Check if we got redirected to login
    if resp.status_code == 302:
        redirect_location = resp.headers.get("Location", "")
        print(f"⚠️  Got redirect (302) to: {redirect_location}")
        if '/login' in redirect_location.lower():
            print(f"\n❌ Authentication failed - redirected to login page")
            print(f"   This usually means:")
            print(f"   1. The xauth token is expired or invalid")
            print(f"   2. The header name might be wrong (trying 'xauth')")
            print(f"   3. The API might require cookies instead of headers")
            print(f"\n   Response headers received: {dict(resp.headers)}")
            raise httpx.HTTPStatusError(
                "Authentication failed: API redirected to login page. "
                "Please verify your ENNETIX_XAUTH token is valid and not expired.",
                request=resp.request,
                response=resp
            )
    
    resp.raise_for_status()
    
    data = resp.json()
    
    # Save raw API response to JSON file
    output_file = Path(__file__).parent.parent / "data" / "ennetix_threats.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved raw API response to: {output_file}")
    
    # Print raw response for inspection
    print(f"\n📊 Raw API Response:")
    print(f"Response type: {type(data)}")
    if isinstance(data, list):
        print(f"Total items: {len(data)}")
        if len(data) > 0:
            print(f"\n📋 Sample threat (first item):")
            print(json.dumps(data[0], indent=2))
    elif isinstance(data, dict):
        print(f"Response keys: {list(data.keys())}")
        print(f"\n📋 Full response (first 500 chars):")
        print(json.dumps(data, indent=2)[:500] + "..." if len(json.dumps(data, indent=2)) > 500 else json.dumps(data, indent=2))
    
    # Convert API response to Threat objects
    threats = []
    if isinstance(data, list):
        for idx, item in enumerate(data):
            # Map API response to Threat schema
            # Adjust field mapping based on actual API response structure
            threat = Threat(
                id=str(item.get("id", item.get("_id", idx))),
                name=str(item.get("name", item.get("title", item.get("ip", "Unknown")))),
                severity=str(item.get("severity", item.get("level", "MEDIUM"))).upper(),
                source="ennetix",
                metadata=item
            )
            threats.append(threat)
    elif isinstance(data, dict):
        # Handle case where API returns a dict with threats in a nested structure
        threats_list = data.get("threats", data.get("data", data.get("results", [])))
        for idx, item in enumerate(threats_list):
            threat = Threat(
                id=str(item.get("id", item.get("_id", idx))),
                name=str(item.get("name", item.get("title", item.get("ip", "Unknown")))),
                severity=str(item.get("severity", item.get("level", "MEDIUM"))).upper(),
                source="ennetix",
                metadata=item
            )
            threats.append(threat)
    
    return threats


async def send_to_connector(client: httpx.AsyncClient, threats: List[Threat]) -> None:
    """Send threats to the connector service."""
    payload = ThreatInBulk(threats=threats)
    resp = await client.post(
        f"{CONNECTOR_SERVICE_URL}/threats/bulk",
        json=payload.model_dump(),
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"\n✅ Successfully sent {result.get('count', len(threats))} threats to connector service.")


async def main() -> None:
    """Main execution function."""
    print("=" * 60)
    print("🚀 Ennetix Threat Puller Script")
    print("=" * 60)
    
    # Create HTTP client with redirect following enabled
    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        # Fetch threats from Ennetix API
        # You can pass custom dates here, or they'll be read from .env or auto-generated
        threats = await fetch_threats_from_ennetix(http_client)
        
        if not threats:
            print("\n⚠️  No threats found in API response.")
            return
        
        print(f"\n✅ Successfully fetched {len(threats)} threats from Ennetix.")
        
        print(f"\n📝 Sample parsed threats (first 3):")
        for i, threat in enumerate(threats[:3], 1):
            print(f"\n  Threat {i}:")
            print(f"    ID: {threat.id}")
            print(f"    Name: {threat.name}")
            print(f"    Severity: {threat.severity}")
            print(f"    Source: {threat.source}")
        
        # Send to connector service
        print(f"\n📤 Sending threats to connector service at {CONNECTOR_SERVICE_URL}...")
        try:
            await send_to_connector(http_client, threats)
        except httpx.ConnectError:
            print(f"\n⚠️  Warning: Could not connect to connector service at {CONNECTOR_SERVICE_URL}")
            print("   Make sure the microservice is running (see README.md)")
        except Exception as e:
            print(f"\n❌ Error sending to connector service: {e}")
    
    print("\n" + "=" * 60)
    print("✨ Script completed!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
