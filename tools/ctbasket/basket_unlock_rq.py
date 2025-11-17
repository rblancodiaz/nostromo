"""
BasketUnLockRQ - Unlock Shopping Basket Tool

This tool handles unlocking a previously locked shopping basket in the Neobookings system
to allow modifications again.
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
BASKET_UNLOCK_RQ_TOOL = Tool(
    name="basket_unlock_rq",
    description="""
    Unlock a previously locked shopping basket in the Neobookings system.
    
    This tool unlocks a basket that was previously locked, allowing modifications
    to its contents again. This is useful when you need to make changes after
    starting the confirmation process.
    
    Parameters:
    - basket_id (required): Identifier of the basket to unlock
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Unlocked basket details
    - Updated basket status
    - Unlock confirmation
    
    Example usage:
    "Unlock basket 'BASKET123' to make changes"
    "Allow modifications to the locked basket"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "basket_id": {
                "type": "string",
                "description": "Identifier of the basket to unlock",
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


class BasketUnLockRQHandler:
    """Handler for the BasketUnLockRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_unlock_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the basket unlocking request.
        
        Args:
            arguments: Tool arguments containing basket ID to unlock
            
        Returns:
            Dictionary containing the unlocked basket details
            
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
                "Unlocking basket",
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
                
                # Make the basket unlock request
                response = await client.post("/BasketUnLockRQ", request_payload)
            
            # Extract basket details from response
            basket_detail = response.get("BasketDetail", {})
            
            # Log successful operation
            self.logger.info(
                "Basket unlocked successfully",
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
                "unlocked": basket_detail.get("BasketStatus") == "open"
            }
            
            return format_response(
                response_data,
                success=True,
                message="Basket unlocked successfully and ready for modifications"
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
handler = BasketUnLockRQHandler()


async def call_basket_unlock_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketUnLockRQ endpoint.
    
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
            
            response_text = f"""🔓 **Basket Unlocked Successfully**

✅ **Basket Information:**
- **Basket ID**: {data['basket_id']}
- **Status**: {basket_detail.get('BasketStatus', 'Unknown')}
- **Budget ID**: {basket_detail.get('BudgetId', 'Not assigned')}
- **Order ID**: {basket_detail.get('OrderId', 'Not assigned')}
- **Unlocked**: {'Yes' if data.get('unlocked') else 'No'}

💡 **Basket is Now Open for Modifications:**
The basket has been successfully unlocked and you can now:
- Add new products using `basket_add_product_rq`
- Remove products using `basket_del_product_rq`
- Update basket properties using `basket_properties_update_rq`
- View contents using `basket_summary_rq`

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **Next Steps:**
- Make any necessary modifications to the basket
- Use `basket_lock_rq` again when ready to proceed with confirmation
- Use `basket_confirm_rq` to complete the reservation when all changes are done

⚠️ **Important**: Remember to lock the basket again before final confirmation.

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Unlock Basket**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the basket ID exists and is accessible
- Check if the basket is actually locked
- Ensure the basket has not been confirmed or deleted
- Verify your authentication credentials
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while unlocking the basket:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
