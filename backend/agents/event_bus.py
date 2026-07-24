"""Event bus for inter-agent communication and pub/sub."""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Callable, Any, Optional, List
from enum import Enum
import json


class EventType(str, Enum):
    """Types of events in the system."""
    # Incident events
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_ESCALATED = "incident.escalated"
    INCIDENT_RESOLVED = "incident.resolved"
    
    # Alert events
    ALERT_GENERATED = "alert.generated"
    ALERT_AGGREGATED = "alert.aggregated"
    
    # Control events
    CONTROL_APPLIED = "control.applied"
    CONTROL_FAILED = "control.failed"
    CONTROL_ROLLED_BACK = "control.rolled_back"
    
    # Recovery events
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_STAGED = "recovery.staged"
    RECOVERY_COMPLETED = "recovery.completed"
    
    # Reporting events
    REPORT_GENERATED = "report.generated"


@dataclass
class Event:
    """System event for inter-agent communication."""
    event_type: EventType
    source_agent: str  # Name of agent that created the event
    timestamp: datetime
    data: dict
    correlation_id: Optional[str] = None  # Link related events
    severity: Optional[str] = None  # LOW, MEDIUM, HIGH, CRITICAL
    
    def to_dict(self) -> dict:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "correlation_id": self.correlation_id,
            "severity": self.severity
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class EventBus:
    """
    Simple in-memory event bus for agent communication.
    
    For production, this would be replaced with Kafka/RabbitMQ.
    """
    
    def __init__(self):
        """Initialize event bus."""
        self.subscribers: dict[EventType, list[Callable]] = {}
        self.event_history: list[Event] = []
        self.max_history: int = 10000
    
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(callback)
    
    def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event: Event to publish
        """
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)
        
        # Notify subscribers
        if event.event_type in self.subscribers:
            for callback in self.subscribers[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in event subscriber: {e}")
    
    def get_history(
        self,
        event_type: Optional[EventType] = None,
        source_agent: Optional[str] = None,
        limit: int = 100
    ) -> list[Event]:
        """
        Get event history filtered by criteria.
        
        Args:
            event_type: Filter by event type (optional)
            source_agent: Filter by source agent (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of events matching criteria
        """
        filtered = self.event_history
        
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        
        if source_agent:
            filtered = [e for e in filtered if e.source_agent == source_agent]
        
        # Return most recent events first
        return filtered[-limit:][::-1]
    
    def get_correlation_chain(self, correlation_id: str) -> list[Event]:
        """
        Get all events with the same correlation ID.
        
        Args:
            correlation_id: Correlation ID to filter by
            
        Returns:
            List of related events in chronological order
        """
        return [
            e for e in self.event_history
            if e.correlation_id == correlation_id
        ]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self.event_history.clear()


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create global event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset global event bus (for testing)."""
    global _event_bus
    _event_bus = None
