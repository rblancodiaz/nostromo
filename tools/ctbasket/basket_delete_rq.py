"""
BasketDeleteRQ - Delete Shopping Basket Tool

This tool handles the complete deletion of a shopping basket in the Neobookings system.
"""

import json
from typing import Dict, Any
from mcp.types import Tool
from mcp.types import TextContent, ImageContent, EmbeddedResource
import structlog

from config import (
    NeobookingsConfig, 
    NeobookingsHTTPClient,
    create_standard_request,
    format_response,
    ValidationError,
    AuthenticationError,
    APIError,
    logger,
    sanitize_string
)

# Tool definition
BASKET_DELETE_RQ_TOOL = Tool(
    name="basket_delete_rq",
    description="""
    Delete a shopping basket completely from the Neobookings system.
    
    This tool permanently removes a basket and all its contents from the system.
    This action cannot be undone.
    
    Parameters:
    - basket_id (required): Identifier of the basket to delete
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Confirmation of basket deletion
    - Final basket status
    - Deletion metadata
    
    Example usage:
    "Delete basket 'BASKET123'"
    "Remove basket completely"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "basket_id": {
                "type": "string",
                "description": "Identifier of the basket to delete",
                "minLength": 1
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["basket_id"],
        "additionalProperties": False
    }
)


class BasketDeleteRQHandler:
    """Handler for the BasketDeleteRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_delete_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the basket deletion request.
        
        Args:
            arguments: Tool arguments containing basket ID to delete
            
        Returns:
            Dictionary containing the deletion confirmation
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            basket_id = sanitize_string(arguments["basket_id"])
            language = arguments.get("language", "es")
            
            self.logger.info(
                "Deleting basket",
                basket_id=basket_id,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                **request_data,
                "BasketId": basket_id
            }
            
            # Make API call with authentication
            async with NeobookingsHTTPClient(self.config) as client:
                # First authenticate
                auth_request = {
                    "Request": request_data["Request"],
                    "Credentials": {
                        "ClientCode": self.config.client_code,
                        "SystemCode": self.config.system_code,
                        "Username": self.config.username,
                        "Password": self.config.password
                    }
                }
                auth_response = await client.post("/AuthenticatorRQ", auth_request, require_auth=False)
                token = auth_response.get("Token")
                if not token:
                    raise AuthenticationError("Failed to obtain authentication token")
                
                client.set_token(token)
                
                # Make the basket deletion request
                response = await client.post("/BasketDeleteRQ", request_payload)
            
            # Extract basket details from response
            basket_detail = response.get("BasketDetail", {})
            
            # Log successful operation
            self.logger.info(
                "Basket deleted successfully",
                basket_id=basket_id,
                basket_status=basket_detail.get("BasketStatus"),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "basket_id": basket_id,
                "basket_detail": basket_detail,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "deletion_confirmed": True
            }
            
            return format_response(
                response_data,
                success=True,
                message="Basket deleted successfully"
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
handler = BasketDeleteRQHandler()


async def call_basket_delete_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketDeleteRQ endpoint.
    
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
            basket_detail = data["basket_detail"]
            
            response_text = f"""🗑️ **Basket Deleted Successfully**

✅ **Deletion Confirmation:**
- **Basket ID**: {data['basket_id']}
- **Final Status**: {basket_detail.get('BasketStatus', 'Unknown')}
- **Deletion Confirmed**: {'Yes' if data.get('deletion_confirmed') else 'No'}

⚠️ **Important Notice:**
The basket and all its contents have been permanently removed from the system. 
This action cannot be undone.

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **What Happens Next:**
- The basket is no longer accessible
- All products in the basket have been removed
- Any temporary holds or locks have been released
- Use `basket_create_rq` to create a new basket if needed

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Delete Basket**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the basket ID exists and is accessible
- Check if the basket is already deleted
- Ensure the basket is not in a locked or confirmed state
- Verify your authentication credentials
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while deleting the basket:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
