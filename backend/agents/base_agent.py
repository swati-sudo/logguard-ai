"""Abstract base class for all LogGuard AI agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    enabled: bool = True
    timeout_seconds: int = 30
    retry_count: int = 3
    log_level: str = "INFO"


class BaseAgent(ABC):
    """Abstract base class for all LogGuard AI agents."""

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize agent.
        
        Args:
            config: Agent configuration (uses defaults if None)
        """
        self.config = config or AgentConfig()
        self.name = self.__class__.__name__
        self.initialized_at = datetime.utcnow()

    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        Main processing method - must be implemented by subclasses.
        
        Args:
            data: Input data to process
            
        Returns:
            Processed result
        """
        pass

    def execute(self, data: Any) -> dict[str, Any]:
        """
        Execute agent with error handling and logging.
        
        Args:
            data: Input data to process
            
        Returns:
            Dict with status, result, and metadata
        """
        if not self.config.enabled:
            return {
                "status": "disabled",
                "message": f"{self.name} is disabled",
                "result": None
            }

        try:
            result = self.process(data)
            return {
                "status": "success",
                "agent": self.name,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "agent": self.name,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def validate_input(self, data: Any, required_fields: list[str]) -> bool:
        """
        Validate input data has required fields.
        
        Args:
            data: Data to validate
            required_fields: List of required field names
            
        Returns:
            True if valid, raises Exception if invalid
        """
        if isinstance(data, dict):
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
        elif hasattr(data, "__dict__"):
            for field in required_fields:
                if not hasattr(data, field):
                    raise ValueError(f"Missing required field: {field}")
        else:
            raise TypeError(f"Invalid data type: {type(data)}")
        
        return True

    def get_agent_info(self) -> dict:
        """Get agent metadata."""
        return {
            "name": self.name,
            "initialized_at": self.initialized_at.isoformat(),
            "enabled": self.config.enabled,
            "timeout_seconds": self.config.timeout_seconds
        }
