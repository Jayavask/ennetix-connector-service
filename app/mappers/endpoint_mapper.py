"""
Endpoint mapper - maps Ennetix endpoint alerts to ECS format
"""
from typing import Dict, Any, Optional
from app.mappers.base_mapper import BaseMapper
from app.logging import setup_logging

logger = setup_logging()


class EndpointMapper(BaseMapper):
    """Maps endpoint-related alerts to ECS format"""
    
    def map(self, source_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map endpoint alert to ECS format
        
        Args:
            source_doc: Source document from Ennetix
        
        Returns:
            Mapped document in ECS format
        """
        try:
            # Extract common fields
            mapped = {
                "@timestamp": source_doc.get("@timestamp"),
                "event": {
                    "kind": "alert",
                    "category": "endpoint",
                    "type": source_doc.get("event_type", "unknown"),
                    "severity": source_doc.get("severity", 0),
                },
                "host": {
                    "name": self.handle_null(source_doc.get("hostname")),
                    "ip": self.handle_null(source_doc.get("host_ip")),
                },
                "source": {
                    "ip": self.handle_null(source_doc.get("source_ip")),
                    "port": self.handle_null(source_doc.get("source_port")),
                },
                "destination": {
                    "ip": self.handle_null(source_doc.get("dest_ip")),
                    "port": self.handle_null(source_doc.get("dest_port")),
                },
                "message": self.handle_null(source_doc.get("message")),
            }
            
            # Add custom fields
            if "custom_fields" in source_doc:
                mapped["ennetix"] = source_doc["custom_fields"]
            
            # Validate before returning
            if self.validate(mapped):
                return mapped
            else:
                logger.warning("Endpoint document failed validation")
                return None
                
        except Exception as e:
            logger.error(f"Error mapping endpoint document: {str(e)}")
            return None

