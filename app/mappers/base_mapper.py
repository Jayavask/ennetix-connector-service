"""
Base mapper class
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.validators.ecs_validator import ECSValidator


class BaseMapper(ABC):
    """Base class for all mappers"""
    
    def __init__(self):
        self.validator = ECSValidator()
    
    @abstractmethod
    def map(self, source_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map source document to ECS format
        
        Args:
            source_doc: Source document from Ennetix
        
        Returns:
            Mapped document in ECS format, or None if mapping fails
        """
        pass
    
    def validate(self, doc: Dict[str, Any]) -> bool:
        """Validate document against ECS schema"""
        return self.validator.validate(doc)
    
    def handle_null(self, value: Any, default: Any = None) -> Any:
        """Handle null values with default"""
        return default if value is None else value

