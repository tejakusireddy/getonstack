from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta

from core.database import get_db
from core.security import create_access_token
from models.user import User
from schemas.user import Token
from services.github import GitHubService
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/github")
async def github_login():
    """Redirect to GitHub OAuth."""
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
        f"&scope=user:email,repo"
    )
    return RedirectResponse(url=github_auth_url)


@router.get("/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback."""
    
    # Exchange code for access token
    access_token = await GitHubService.exchange_code_for_token(code)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get access token from GitHub"
        )
    
    # Get user info from GitHub
    github_user = await GitHubService.get_user_info(access_token)
    if not github_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from GitHub"
        )
    
    # Get user email
    emails = await GitHubService.get_user_emails(access_token)
    primary_email = next(
        (email["email"] for email in emails if email.get("primary")),
        None
    )
    
    if not primary_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No primary email found in GitHub account"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.github_id == str(github_user["id"])).first()
    
    if not user:
        # Create new user
        user = User(
            email=primary_email,
            github_id=str(github_user["id"]),
            github_username=github_user["login"],
            full_name=github_user.get("name"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update existing user info
        user.github_username = github_user["login"]
        user.full_name = github_user.get("name")
        user.email = primary_email
        db.commit()
    
    # Create JWT token
    token_data = {"sub": str(user.id)}
    jwt_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Redirect to frontend with token
    frontend_url = "http://localhost:3000"
    return RedirectResponse(url=f"{frontend_url}/auth/success?token={jwt_token}")


@router.post("/token", response_model=Token)
async def login(code: str, db: Session = Depends(get_db)):
    """Alternative endpoint for getting token (for API clients)."""
    
    # Exchange code for access token
    access_token = await GitHubService.exchange_code_for_token(code)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization code"
        )
    
    # Get user info
    github_user = await GitHubService.get_user_info(access_token)
    if not github_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info"
        )
    
    # Find user in database
    user = db.query(User).filter(User.github_id == str(github_user["id"])).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please complete OAuth flow first."
        )
    
    # Create JWT token
    token_data = {"sub": str(user.id)}
    jwt_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return Token(access_token=jwt_token, token_type="bearer")