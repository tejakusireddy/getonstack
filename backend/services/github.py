import httpx
from typing import Optional, Dict, Any
from config import get_settings

settings = get_settings()


class GitHubService:
    """Service for GitHub OAuth and API operations."""
    
    OAUTH_URL = "https://github.com/login/oauth/access_token"
    API_URL = "https://api.github.com"
    
    @staticmethod
    async def exchange_code_for_token(code: str) -> Optional[str]:
        """Exchange OAuth code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GitHubService.OAUTH_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            return None
    
    @staticmethod
    async def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
        """Get GitHub user information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GitHubService.API_URL}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
            )
            
            if response.status_code == 200:
                return response.json()
            return None
    
    @staticmethod
    async def get_user_emails(access_token: str) -> Optional[list]:
        """Get user's email addresses from GitHub."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GitHubService.API_URL}/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
            )
            
            if response.status_code == 200:
                return response.json()
            return None