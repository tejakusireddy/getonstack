from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import secrets

from core.database import get_db, SessionLocal
from models.agent import Agent
from schemas.agent import AgentCreate, AgentResponse
from api.dependencies import get_current_user
from models.user import User
from services.framework_detector import FrameworkDetector

router = APIRouter(prefix="/api/agents", tags=["agents"])


async def process_agent_deployment(agent_id: int):
    """Background task to clone repo and detect framework."""
    db: Session = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return

        detector = FrameworkDetector()
        repo_path = None

        try:
            # Update status to cloning
            agent.status = "cloning"
            db.commit()

            # Validate repository URL
            if not detector.validate_repo_url(agent.repository_url):
                raise Exception("Invalid GitHub repository URL")

            # Clone repository
            repo_path = detector.clone_repo(agent.repository_url, agent.branch)

            # Update status to detecting
            agent.status = "detecting"
            db.commit()

            # Detect framework and get commit hash
            framework, commit_hash = detector.detect_framework(repo_path)

            # Update agent with detected information
            agent.framework = framework
            agent.commit_hash = commit_hash
            agent.status = "detected"
            db.commit()

        except Exception as e:
            # Update status to failed with error
            if agent:
                agent.status = "failed"
                db.commit()
            print(f"Agent {getattr(agent, 'agent_id', agent_id)} deployment failed: {str(e)}")

        finally:
            # Always cleanup the cloned repository
            if repo_path:
                detector.cleanup(repo_path)
    finally:
        db.close()


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new agent deployment."""
    
    # Generate unique agent ID
    agent_id = f"agt_{secrets.token_hex(8)}"
    
    # Create agent in database
    agent = Agent(
        agent_id=agent_id,
        name=agent_data.name,
        description=agent_data.description,
        repository_url=agent_data.repository_url,
        branch=agent_data.branch,
        environment_variables=agent_data.environment_variables,
        config=agent_data.config,
        user_id=current_user.id,
        status="pending"
    )
    
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    # Trigger background deployment process
    background_tasks.add_task(process_agent_deployment, agent.id)
    
    return agent


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str = None
):
    """List all agents for the current user."""
    
    query = db.query(Agent).filter(Agent.user_id == current_user.id)
    
    # Optional filter by status
    if status:
        query = query.filter(Agent.status == status)
    
    agents = query.order_by(Agent.created_at.desc()).all()
    
    return agents


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific agent by ID."""
    
    agent = db.query(Agent).filter(
        Agent.agent_id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )
    
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an agent."""
    
    agent = db.query(Agent).filter(
        Agent.agent_id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )
    
    # TODO: Stop and remove Docker container if running
    
    db.delete(agent)
    db.commit()
    
    return None