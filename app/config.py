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
    
    # Index settings
    ENNETIX_INDEX_PATTERN: str = "ennetix-*"
    CYGENIQ_INDEX_PREFIX: str = "cygeniq-"
    
    # Fetcher settings
    SCROLL_SIZE: int = 1000
    SCROLL_TIMEOUT: str = "5m"
    BATCH_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

