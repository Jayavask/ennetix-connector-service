"""
Ennetix API HTTP client
"""
import json
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()


class EnnetixAPIClient:
    """HTTP client for Ennetix API calls"""
    
    def __init__(self):
        self.base_url = settings.ENNETIX_API_BASE_URL
        self.xauth = settings.ENNETIX_XAUTH
        self.username = settings.ENNETIX_ELASTICSEARCH_USERNAME
        self.password = settings.ENNETIX_ELASTICSEARCH_PASSWORD
        self.max_retries = settings.ENNETIX_MAX_RETRIES
        self.retry_delay = settings.ENNETIX_RETRY_DELAY
    
    async def fetch_api(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Dict[str, Any] = None,
        retry_count: int = 0,
    ) -> Optional[Any]:
        """Fetch data from Ennetix API with authentication and retry logic."""
        if params is None:
            params = {}

        headers: Dict[str, str] = {}
        auth = None

        if self.xauth:
            headers["xauth"] = self.xauth
        elif self.username and self.password:
            auth = (self.username, self.password)

        try:
            resp = await client.get(
                url,
                params=params,
                headers=headers,
                auth=auth,
                timeout=60,
                follow_redirects=False,
            )

            # If redirected and have xauth, try using it as a cookie
            if resp.status_code == 302 and self.xauth:
                cookies = {"xauth": self.xauth}
                resp = await client.get(
                    url,
                    params=params,
                    cookies=cookies,
                    timeout=60,
                    follow_redirects=False,
                )

            if resp.status_code == 302:
                redirect_location = resp.headers.get("Location", "")
                if '/login' in redirect_location.lower():
                    logger.error(f"Authentication failed: API redirected to login page")
                    return None

            # Handle 500 errors with retry logic
            if resp.status_code == 500:
                if retry_count < self.max_retries:
                    delay = self.retry_delay * (2 ** retry_count)  # Exponential backoff
                    logger.warning(f"HTTP 500 error, retrying in {delay:.1f}s (attempt {retry_count + 1}/{self.max_retries})...")
                    await asyncio.sleep(delay)
                    return await self.fetch_api(client, url, params, retry_count + 1)
                else:
                    logger.error(f"HTTP 500 error after {self.max_retries} retries: {url}")
                    return None

            resp.raise_for_status()

            # Check if response is HTML (login page) instead of JSON
            content_type = resp.headers.get("content-type", "").lower()
            text_content = resp.text

            if "text/html" in content_type or text_content.strip().startswith("<!DOCTYPE html"):
                if self.xauth:
                    cookies = {"xauth": self.xauth}
                    resp = await client.get(
                        url,
                        params=params,
                        cookies=cookies,
                        timeout=60,
                        follow_redirects=False,
                    )
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "").lower()
                    text_content = resp.text
                    if "text/html" in content_type or text_content.strip().startswith("<!DOCTYPE html"):
                        logger.error(f"Response is HTML (likely login page), not JSON")
                        return None
                else:
                    logger.error(f"Response is HTML (likely login page), not JSON")
                    return None

            data = resp.json()
            return data

        except httpx.HTTPStatusError as e:
            # Retry on 500 errors
            if e.response.status_code == 500 and retry_count < self.max_retries:
                delay = self.retry_delay * (2 ** retry_count)
                logger.warning(f"HTTP 500 error, retrying in {delay:.1f}s (attempt {retry_count + 1}/{self.max_retries})...")
                await asyncio.sleep(delay)
                return await self.fetch_api(client, url, params, retry_count + 1)
            logger.error(f"HTTP error {e.response.status_code}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching API: {e}")
            return None
    
    async def fetch_threats(
        self,
        client: httpx.AsyncClient,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """API 1: Fetch threats from /alerts/ip/threats.json"""
        url = f"{self.base_url}/alerts/ip/threats.json"
        params = {
            "start": start_date,
            "end": end_date,
        }

        logger.info(f"Fetching threats from: {url}")
        logger.info(f"Date range: {start_date} to {end_date}")

        data = await self.fetch_api(client, url, params)

        if data is None:
            return []

        if isinstance(data, list):
            threats = data
        elif isinstance(data, dict):
            threats = data.get("threats") or data.get("data") or data.get("results") or []
        else:
            threats = []

        logger.info(f"Fetched {len(threats)} threat entries")
        return threats
    
    async def fetch_logs(
        self,
        client: httpx.AsyncClient,
        ip: str,
        signature_id: str,
        start_date: str,
        end_date: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """API 2: Fetch logs from /alerts/{ip}/{signatureId}/logs.json"""
        url = f"{self.base_url}/alerts/{ip}/{signature_id}/logs.json"
        params = {
            "start": start_date,
            "end": end_date,
        }

        data = await self.fetch_api(client, url, params)
        
        if data is None:
            return None
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("logs") or data.get("data") or []
        else:
            return []
    
    async def fetch_flows(
        self,
        client: httpx.AsyncClient,
        ip: str,
        start_date: str,
        end_date: str,
        service: str,
        role: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """API 3: Fetch flows from /security/{ip}/flows.json"""
        url = f"{self.base_url}/security/{ip}/flows.json"
        params = {
            "start": start_date,
            "end": end_date,
            "service": service,
            "role": role,
        }

        data = await self.fetch_api(client, url, params)
        
        if data is None:
            return None
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("flows") or data.get("data") or []
        else:
            return []

