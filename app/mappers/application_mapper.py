"""
Application mapper - maps Ennetix application alerts to ECS format
"""
from typing import Dict, Any, Optional
from app.mappers.base_mapper import BaseMapper
from app.logging import setup_logging

logger = setup_logging()


class ApplicationMapper(BaseMapper):
    """Maps application-related alerts to ECS format"""
    
    def map(self, source_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map application alert to ECS format
        
        Args:
            source_doc: Source document from Ennetix
        
        Returns:
            Mapped document in ECS format
        """
        try:
            mapped = {
                "@timestamp": source_doc.get("@timestamp"),
                "event": {
                    "kind": "alert",
                    "category": "application",
                    "type": source_doc.get("event_type", "unknown"),
                    "severity": source_doc.get("severity", 0),
                },
                "service": {
                    "name": self.handle_null(source_doc.get("service_name")),
                    "type": self.handle_null(source_doc.get("service_type")),
                },
                "application": {
                    "name": self.handle_null(source_doc.get("app_name")),
                    "version": self.handle_null(source_doc.get("app_version")),
                },
                "source": {
                    "ip": self.handle_null(source_doc.get("source_ip")),
                    "port": self.handle_null(source_doc.get("source_port")),
                },
                "destination": {
                    "ip": self.handle_null(source_doc.get("dest_ip")),
                    "port": self.handle_null(source_doc.get("dest_port")),
                },
                "user": {
                    "name": self.handle_null(source_doc.get("username")),
                    "id": self.handle_null(source_doc.get("user_id")),
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
                logger.warning("Application document failed validation")
                return None
                
        except Exception as e:
            logger.error(f"Error mapping application document: {str(e)}")
            return None

