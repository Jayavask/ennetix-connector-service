"""
Ensures schema completeness for ECS format
"""
from typing import Dict, Any, List, Optional
from app.logging import setup_logging

logger = setup_logging()


class ECSValidator:
    """Validates documents against ECS schema requirements"""
    
    REQUIRED_FIELDS = [
        "@timestamp",
        "event.kind",
        "event.category",
    ]
    
    def __init__(self):
        self.errors: List[str] = []
    
    def validate(self, doc: Dict[str, Any]) -> bool:
        """
        Validate document against ECS schema
        
        Args:
            doc: Document to validate
        
        Returns:
            True if valid, False otherwise
        """
        self.errors.clear()
        
        # Check required fields
        for field_path in self.REQUIRED_FIELDS:
            if not self._get_nested_value(doc, field_path):
                self.errors.append(f"Missing required field: {field_path}")
        
        # Validate timestamp format
        if "@timestamp" in doc:
            if not self._validate_timestamp(doc["@timestamp"]):
                self.errors.append("Invalid @timestamp format")
        
        # Validate event structure
        if "event" in doc:
            if not isinstance(doc["event"], dict):
                self.errors.append("event must be an object")
            else:
                if "kind" in doc["event"] and doc["event"]["kind"] not in ["alert", "event", "metric"]:
                    self.errors.append("event.kind must be one of: alert, event, metric")
        
        if self.errors:
            logger.debug(f"Validation errors: {self.errors}")
            return False
        
        return True
    
    def _get_nested_value(self, doc: Dict[str, Any], path: str) -> Optional[Any]:
        """Get nested value from document using dot notation"""
        keys = path.split(".")
        value = doc
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def _validate_timestamp(self, timestamp: Any) -> bool:
        """Validate timestamp format"""
        if not timestamp:
            return False
        
        # Accept ISO 8601 format strings
        if isinstance(timestamp, str):
            # Basic check for ISO format
            return "T" in timestamp or timestamp.endswith("Z")
        
        # Accept numeric timestamps (epoch)
        if isinstance(timestamp, (int, float)):
            return True
        
        return False
    
    def get_errors(self) -> List[str]:
        """Get validation errors"""
        return self.errors.copy()

