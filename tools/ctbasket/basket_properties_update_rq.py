"""
BasketPropertiesUpdateRQ - Update Basket Properties Tool

This tool handles updating properties of a shopping basket in the Neobookings system,
such as rewards settings and promotional codes.
"""

import json
from typing import Dict, Any, Optional
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
BASKET_PROPERTIES_UPDATE_RQ_TOOL = Tool(
    name="basket_properties_update_rq",
    description="""
    Update properties of a shopping basket in the Neobookings system.
    
    This tool allows updating various basket properties such as:
    - Rewards/loyalty program settings
    - Promotional codes application
    - Other basket-level configuration options
    
    Parameters:
    - basket_id (required): Identifier of the basket to update
    - rewards_update (optional): Rewards/loyalty program update settings
    - promo_code_update (optional): Promotional code update settings
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Updated basket status
    - Applied changes confirmation
    - Updated pricing if applicable
    
    Example usage:
    "Enable rewards for basket 'BASKET123'"
    "Apply promo code 'SUMMER2024' to my basket"
    "Remove promotional code from basket"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "basket_id": {
                "type": "string",
                "description": "Identifier of the basket to update",
                "minLength": 1
            },
            "rewards_update": {
                "type": "object",
                "description": "Rewards/loyalty program update settings",
                "properties": {
                    "enable": {
                        "type": "boolean",
                        "description": "Enable or disable rewards for this basket"
                    }
                },
                "additionalProperties": False
            },
            "promo_code_update": {
                "type": "object",
                "description": "Promotional code update settings",
                "properties": {
                    "use_promo_code": {
                        "type": "boolean",
                        "description": "Whether to add or remove promotional code"
                    },
                    "promo_code": {
                        "type": "string",
                        "description": "Promotional code to apply (required when use_promo_code is true)",
                        "minLength": 1
                    }
                },
                "required": ["use_promo_code"],
                "additionalProperties": False
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


class BasketPropertiesUpdateRQHandler:
    """Handler for the BasketPropertiesUpdateRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_properties_update_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the basket properties update request.
        
        Args:
            arguments: Tool arguments containing basket ID and property updates
            
        Returns:
            Dictionary containing the update confirmation
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            basket_id = sanitize_string(arguments["basket_id"])
            language = arguments.get("language", "es")
            
            # Validate that at least one update type is provided
            has_updates = any([
                arguments.get("rewards_update"),
                arguments.get("promo_code_update")
            ])
            
            if not has_updates:
                raise ValidationError(
                    "At least one property update must be specified",
                    error_code="NO_UPDATES_SPECIFIED"
                )
            
            # Validate promo code requirements
            promo_update = arguments.get("promo_code_update")
            if promo_update and promo_update.get("use_promo_code") and not promo_update.get("promo_code"):
                raise ValidationError(
                    "Promo code is required when use_promo_code is true",
                    error_code="PROMO_CODE_REQUIRED"
                )
            
            self.logger.info(
                "Updating basket properties",
                basket_id=basket_id,
                language=language,
                has_rewards_update=bool(arguments.get("rewards_update")),
                has_promo_update=bool(arguments.get("promo_code_update"))
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                **request_data,
                "BasketId": basket_id
            }
            
            # Add rewards update if provided
            if arguments.get("rewards_update"):
                rewards_update = arguments["rewards_update"]
                # Create RewardsUpdate object (structure may be empty based on API spec)
                request_payload["Rewards"] = {}
                
                # Log rewards configuration
                self.logger.info(
                    "Rewards update configured",
                    enabled=rewards_update.get("enable")
                )
            
            # Add promo code update if provided
            if arguments.get("promo_code_update"):
                promo_update = arguments["promo_code_update"]
                promo_code_obj = {
                    "UsePromoCode": promo_update["use_promo_code"]
                }
                
                if promo_update.get("promo_code"):
                    promo_code_obj["PromoCode"] = promo_update["promo_code"]
                    
                request_payload["PromoCode"] = promo_code_obj
                
                # Log promo code configuration
                self.logger.info(
                    "Promo code update configured",
                    use_promo_code=promo_update["use_promo_code"],
                    promo_code=promo_update.get("promo_code", "N/A")
                )
            
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
                
                # Make the basket properties update request
                response = await client.post("/BasketPropertiesUpdateRQ", request_payload)
            
            # Log successful operation
            self.logger.info(
                "Basket properties updated successfully",
                basket_id=basket_id,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "basket_id": basket_id,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "updates_applied": {
                    "rewards": bool(arguments.get("rewards_update")),
                    "promo_code": bool(arguments.get("promo_code_update"))
                },
                "promo_code_info": arguments.get("promo_code_update", {})
            }
            
            return format_response(
                response_data,
                success=True,
                message="Basket properties updated successfully"
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
handler = BasketPropertiesUpdateRQHandler()


async def call_basket_properties_update_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketPropertiesUpdateRQ endpoint.
    
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
            updates_applied = data["updates_applied"]
            promo_info = data["promo_code_info"]
            
            response_text = f"""⚙️ **Basket Properties Updated Successfully**

✅ **Update Summary:**
- **Basket ID**: {data['basket_id']}
"""
            
            # Add details for applied updates
            if updates_applied["rewards"]:
                response_text += "- **Rewards**: Configuration updated\n"
            
            if updates_applied["promo_code"]:
                if promo_info.get("use_promo_code"):
                    promo_code = promo_info.get("promo_code", "N/A")
                    response_text += f"- **Promotional Code**: Applied '{promo_code}'\n"
                else:
                    response_text += "- **Promotional Code**: Removed from basket\n"
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **Next Steps:**
- Use `basket_summary_rq` to view updated basket with new pricing
- The changes will be reflected in the final reservation
- Continue with basket management or proceed to confirmation

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Update Basket Properties**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the basket ID exists and is accessible
- Check that the promotional code is valid (if applying one)
- Ensure the basket is not locked or confirmed
- Verify the rewards program is available for this basket
- Check your authentication credentials
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while updating basket properties:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
