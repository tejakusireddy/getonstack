from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class AgentBase(BaseModel):
    """Base agent schema."""
    name: str
    description: Optional[str] = None
    repository_url: str
    branch: str = "main"


class AgentCreate(AgentBase):
    """Schema for creating an agent."""
    environment_variables: Optional[Dict[str, str]] = None
    config: Optional[Dict[str, Any]] = None


class AgentResponse(AgentBase):
    """Schema for agent response."""
    id: int
    agent_id: str
    framework: Optional[str] = None
    status: str
    endpoint: Optional[str] = None
    created_at: datetime
    deployed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True