"""
HTTP client for Neobookings API.
"""

import httpx
import json
from typing import Dict, Any, Optional
import structlog
from .base import NeobookingsConfig, NeobookingsError, APIError, AuthenticationError

logger = structlog.get_logger()


class NeobookingsHTTPClient:
    """HTTP client for Neobookings API."""
    
    def __init__(self, config: NeobookingsConfig):
        self.config = config
        self.token: Optional[str] = None
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    def set_token(self, token: str) -> None:
        """Set the authentication token for subsequent requests."""
        self.token = token
        self._client.headers["Authorization"] = f"Bearer {token}"
    
    async def post(self, endpoint: str, data: Dict[str, Any], require_auth: bool = True) -> Dict[str, Any]:
        """
        Make a POST request to the specified endpoint.
        
        Args:
            endpoint: API endpoint path
            data: Request payload
            require_auth: Whether authentication token is required
            
        Returns:
            Response data as dictionary
            
        Raises:
            AuthenticationError: If authentication is required but token is missing
            APIError: If the API call fails
        """
        if require_auth and not self.token:
            raise AuthenticationError("Authentication token required but not set")
        
        # Log the request (without sensitive data)
        logger.info(
            "Making API request",
            endpoint=endpoint,
            has_token=bool(self.token),
            request_id=data.get("Request", {}).get("RequestId")
        )
        
        try:
            response = await self._client.post(endpoint, json=data)
            
            # Log response status
            logger.info(
                "API response received",
                endpoint=endpoint,
                status_code=response.status_code,
                request_id=data.get("Request", {}).get("RequestId")
            )
            
            # Handle different response status codes
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed - invalid token or credentials")
            elif response.status_code == 404:
                raise APIError(f"Endpoint not found: {endpoint}")
            elif response.status_code >= 400:
                error_text = response.text
                raise APIError(f"API request failed with status {response.status_code}: {error_text}")
            
            # Parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                raise APIError(f"Failed to parse JSON response: {e}")
            
            # Check for API-level errors in the response
            if "Response" in response_data:
                response_info = response_data["Response"]
                status_code = response_info.get("StatusCode", 0)
                
                if status_code != 200:
                    errors = response_info.get("Error", [])
                    if errors:
                        error_messages = [f"{err.get('Code', 'UNKNOWN')}: {err.get('Description', 'Unknown error')}" for err in errors]
                        raise APIError(f"API returned errors: {'; '.join(error_messages)}")
                    else:
                        raise APIError(f"API returned status code {status_code}")
            
            return response_data
            
        except httpx.TimeoutException:
            logger.error("Request timeout", endpoint=endpoint)
            raise APIError(f"Request timeout for endpoint: {endpoint}")
        except httpx.RequestError as e:
            logger.error("Request error", endpoint=endpoint, error=str(e))
            raise APIError(f"Request failed for endpoint {endpoint}: {e}")
        except Exception as e:
            logger.error("Unexpected error", endpoint=endpoint, error=str(e))
            raise APIError(f"Unexpected error for endpoint {endpoint}: {e}")
    
    async def authenticate(self, credentials_data: Dict[str, Any]) -> str:
        """
        Authenticate with the API and return the token.
        
        Args:
            credentials_data: Authentication request data
            
        Returns:
            Authentication token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            response = await self.post("/AuthenticatorRQ", credentials_data, require_auth=False)
            
            token = response.get("Token")
            if not token:
                raise AuthenticationError("No token received from authentication endpoint")
            
            self.set_token(token)
            logger.info("Authentication successful")
            return token
            
        except APIError as e:
            logger.error("Authentication failed", error=str(e))
            raise AuthenticationError(f"Authentication failed: {e}")
