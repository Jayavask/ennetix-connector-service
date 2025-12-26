"""
ENV parsing & validation
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Ennetix Elasticsearch settings
    ENNETIX_ELASTICSEARCH_HOSTS: str
    ENNETIX_ELASTICSEARCH_USERNAME: Optional[str] = None
    ENNETIX_ELASTICSEARCH_PASSWORD: Optional[str] = None
    ENNETIX_ELASTICSEARCH_VERIFY_CERTS: str = "true"
    ENNETIX_ELASTICSEARCH_REQUEST_TIMEOUT: int = 100
    ENNETIX_XAUTH: Optional[str] = None
    
    # Cygeniq Elasticsearch settings
    CONNECTOR_SERVICE_URL: str
    ELASTICSEARCH_CYGENIQ_USERNAME: Optional[str] = None
    ELASTICSEARCH_CYGENIQ_PASSWORD: Optional[str] = None
    ELASTICSEARCH_CYGENIQ_REQUEST_TIMEOUT: int = 100
    ELASTICSEARCH_CYGENIQ_MAX_RETRIES: int = 10
    ELASTICSEARCH_CYGENIQ_VERIFY_CERTS: str = "false"
    
    # Ennetix API settings
    ENNETIX_API_BASE_URL: str = "https://demo.xvisor.ai"
    
    # Index settings
    ENNETIX_INDEX_PATTERN: str = "ennetix-*"
    CYGENIQ_INDEX_PREFIX: str = "cygeniq-"
    
    # P1 API Output Data indices (CS1)
    THREATS_INDEX: str = "ennetix-threats1"
    LOGS_INDEX: str = "ennetix-logs1"
    FLOWS_INDEX: str = "ennetix-flows1"
    
    # Fetcher settings
    SCROLL_SIZE: int = 1000
    SCROLL_TIMEOUT: str = "5m"
    BATCH_SIZE: int = 500  # Increased from 100 - larger bulk indexing batches
    
    # P1 API settings
    ENNETIX_API_BATCH_SIZE: int = 200  # Increased from 100 - more concurrent alert processing
    ENNETIX_API3_BATCH_SIZE: int = 20  # Increased from 10 - more concurrent flow API calls
    ENNETIX_MAX_RETRIES: int = 3
    ENNETIX_RETRY_DELAY: float = 1.0
    ENNETIX_API3_DELAY: float = 0.05  # Delay between API 3 calls (reduced from 0.1s)
    P1_DATE_RANGE_DAYS: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

