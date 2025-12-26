"""
Network mapper - maps Ennetix network alerts to ECS format
"""
from typing import Dict, Any, Optional
from app.mappers.base_mapper import BaseMapper
from app.logging import setup_logging

logger = setup_logging()


class NetworkMapper(BaseMapper):
    """Maps network-related alerts to ECS format"""
    
    def map(self, source_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map network alert to ECS format
        
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
                    "category": "network",
                    "type": source_doc.get("event_type", "unknown"),
                    "severity": source_doc.get("severity", 0),
                },
                "network": {
                    "protocol": self.handle_null(source_doc.get("protocol")),
                    "transport": self.handle_null(source_doc.get("transport")),
                    "bytes": self.handle_null(source_doc.get("bytes")),
                    "packets": self.handle_null(source_doc.get("packets")),
                },
                "source": {
                    "ip": self.handle_null(source_doc.get("source_ip")),
                    "port": self.handle_null(source_doc.get("source_port")),
                    "mac": self.handle_null(source_doc.get("source_mac")),
                },
                "destination": {
                    "ip": self.handle_null(source_doc.get("dest_ip")),
                    "port": self.handle_null(source_doc.get("dest_port")),
                    "mac": self.handle_null(source_doc.get("dest_mac")),
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
                logger.warning("Network document failed validation")
                return None
                
        except Exception as e:
            logger.error(f"Error mapping network document: {str(e)}")
            return None

