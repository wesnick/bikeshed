from typing import Dict, List, Optional, Any
import httpx
from pydantic import BaseModel


class MCPServer(BaseModel):
    """Model representing a server from the PulseMCP API"""
    name: str
    url: str
    external_url: Optional[str] = None
    short_description: Optional[str] = None
    source_code_url: Optional[str] = None
    github_stars: Optional[int] = None
    package_registry: Optional[str] = None
    package_name: Optional[str] = None
    package_download_count: Optional[int] = None
    EXPERIMENTAL_ai_generated_description: Optional[str] = None


class ServerListResponse(BaseModel):
    """Response model for the server list endpoint"""
    servers: List[MCPServer]
    next: Optional[str] = None
    total_count: int


class PulseMCPAPIError(Exception):
    """Exception raised for errors in the PulseMCP API."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class PulseMCPAPI:
    """Client for the PulseMCP API"""
    
    BASE_URL = "https://api.pulsemcp.com/v0beta"
    USER_AGENT = "mcp-agent/1.0"
    
    def __init__(self, base_url: Optional[str] = None, user_agent: Optional[str] = None):
        """
        Initialize the PulseMCP API client.
        
        Args:
            base_url: Optional override for the API base URL
            user_agent: Optional override for the User-Agent header
        """
        self.base_url = base_url or self.BASE_URL
        self.user_agent = user_agent or self.USER_AGENT
        self.headers = {"User-Agent": self.user_agent}
    
    async def get_servers(
        self, 
        query: Optional[str] = None, 
        count_per_page: int = 5000, 
        offset: int = 0
    ) -> ServerListResponse:
        """
        Get a list of MCP servers.
        
        Args:
            query: Optional search term to filter servers
            count_per_page: Number of results per page (maximum: 5000)
            offset: Number of results to skip for pagination
            
        Returns:
            ServerListResponse object containing the list of servers
            
        Raises:
            PulseMCPAPIError: If the API returns an error
            httpx.HTTPError: For network-related errors
        """
        params: Dict[str, Any] = {
            "count_per_page": count_per_page,
            "offset": offset
        }
        
        if query:
            params["query"] = query
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/servers",
                params=params,
                headers=self.headers
            )
            
            if response.status_code != 200:
                try:
                    error_data = response.json().get("error", {})
                    raise PulseMCPAPIError(
                        code=error_data.get("code", "UNKNOWN_ERROR"),
                        message=error_data.get("message", "Unknown error occurred")
                    )
                except (ValueError, AttributeError):
                    # If we can't parse the error JSON
                    raise PulseMCPAPIError(
                        code="API_ERROR",
                        message=f"API error: HTTP {response.status_code}"
                    )
            
            return ServerListResponse(**response.json())
