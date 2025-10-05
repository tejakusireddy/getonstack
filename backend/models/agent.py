from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Agent(Base):
    """Agent deployment model."""
    
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Repository info
    repository_url = Column(String, nullable=False)
    branch = Column(String, default="main")
    commit_hash = Column(String, nullable=True)
    
    # Framework
    framework = Column(String, nullable=True)
    
    # Deployment status
    status = Column(String, default="pending")
    endpoint = Column(String, nullable=True)
    
    # Configuration
    environment_variables = Column(JSON, nullable=True)
    config = Column(JSON, nullable=True)
    
    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", backref="agents")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)