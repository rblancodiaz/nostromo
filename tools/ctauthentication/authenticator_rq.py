"""
AuthenticatorRQ - Neobookings Authentication Tool

This tool handles authentication with the Neobookings API system.
It creates a session and returns an authentication token for subsequent API calls.
"""

import json
from typing import Dict, Any, Optional
from mcp.types import Tool
from mcp.types import TextContent, ImageContent, EmbeddedResource
import structlog

from config import (
    NeobookingsConfig, 
    NeobookingsHTTPClient,
    create_authentication_request,
    format_response,
    ValidationError,
    AuthenticationError,
    APIError,
    logger
)

# Tool definition
AUTHENTICATOR_RQ_TOOL = Tool(
    name="authenticator_rq",
    description="""
    Authenticate with the Neobookings API system and create a session.
    
    This tool establishes authentication with the Neobookings API using the configured 
    credentials and returns a session token that can be used for subsequent API calls.
    
    Parameters:
    - language (optional): Language code for the session (default: "es")
                          Valid values: "es", "en", "fr", "de", "it", "pt"
    
    Returns:
    - Authentication token for API access
    - Request metadata (RequestId, Timestamp, etc.)
    - Session information
    
    Example usage:
    "Authenticate with the Neobookings system"
    "Get an authentication token for API access"
    "Login to Neobookings with Spanish language"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "Language code for the session",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "additionalProperties": False
    }
)


class AuthenticatorRQHandler:
    """Handler for the AuthenticatorRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="authenticator_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the authentication request.
        
        Args:
            arguments: Tool arguments containing optional language parameter
            
        Returns:
            Dictionary containing the authentication response
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            language = arguments.get("language", "es")
            
            # Validate language code
            valid_languages = ["es", "en", "fr", "de", "it", "pt"]
            if language not in valid_languages:
                raise ValidationError(
                    f"Invalid language code: {language}. Valid options: {', '.join(valid_languages)}"
                )
            
            self.logger.info("Starting authentication", language=language)
            
            # Create authentication request
            auth_request = create_authentication_request(self.config, language)
            
            # Make API call
            async with NeobookingsHTTPClient(self.config) as client:
                response = await client.post("/AuthenticatorRQ", auth_request, require_auth=False)
            
            # Extract token from response
            token = response.get("Token")
            if not token:
                raise AuthenticationError("No authentication token received from API")
            
            # Log successful authentication
            self.logger.info(
                "Authentication successful", 
                token_length=len(token),
                language=language,
                request_id=auth_request["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "token": token,
                "language": language,
                "request_metadata": auth_request["Request"],
                "api_response": response.get("Response", {}),
                "session_info": {
                    "client_code": self.config.client_code,
                    "system_code": self.config.system_code,
                    "username": self.config.username,
                    "base_url": self.config.base_url
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message="Authentication successful. Token is ready for API calls."
            )
            
        except ValidationError as e:
            self.logger.error("Validation error", error=str(e))
            return format_response(
                {"error_code": e.error_code, "details": e.details},
                success=False,
                message=f"Validation error: {e.message}"
            )
            
        except AuthenticationError as e:
            self.logger.error("Authentication error", error=str(e))
            return format_response(
                {"error_code": e.error_code, "details": e.details},
                success=False,
                message=f"Authentication failed: {e.message}"
            )
            
        except APIError as e:
            self.logger.error("API error", error=str(e))
            return format_response(
                {"error_code": e.error_code, "details": e.details},
                success=False,
                message=f"API error: {e.message}"
            )
            
        except Exception as e:
            self.logger.error("Unexpected error", error=str(e))
            return format_response(
                {"error_type": type(e).__name__},
                success=False,
                message=f"Unexpected error: {str(e)}"
            )


# Global handler instance
handler = AuthenticatorRQHandler()


async def call_authenticator_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the AuthenticatorRQ endpoint.
    
    Args:
        arguments: Arguments passed to the tool
        
    Returns:
        List containing the response as TextContent
    """
    try:
        result = await handler.execute(arguments)
        
        # Format the result as a readable text response
        if result["success"]:
            data = result["data"]
            response_text = f"""🔐 **Authentication Successful**

✅ **Session Details:**
- **Token**: `{data['token'][:20]}...` (truncated for security)
- **Language**: {data['language']}
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

🏨 **API Configuration:**
- **Base URL**: {data['session_info']['base_url']}
- **Client Code**: {data['session_info']['client_code']}
- **System Code**: {data['session_info']['system_code']}
- **Username**: {data['session_info']['username']}

💡 **Next Steps:**
The authentication token is now available for making authenticated API calls to the Neobookings system. You can now proceed with hotel searches, reservations, and other operations.

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Authentication Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify your Neobookings credentials are correct
- Check your network connection
- Ensure the API endpoint is accessible
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while processing the authentication request:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
