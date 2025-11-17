"""
BasketCreateRQ - Create New Shopping Basket Tool

This tool handles the creation of a new shopping basket in the Neobookings system.
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
BASKET_CREATE_RQ_TOOL = Tool(
    name="basket_create_rq",
    description="""
    Create a new shopping basket in the Neobookings system.
    
    This tool initializes a new shopping basket that can be used to collect
    products (hotel rooms, packages, extras) before final confirmation.
    
    Parameters:
    - client_device (optional): Type of client device (desktop, mobile, tablet)
    - origin (optional): Origin of the reservation
    - tracking (optional): Tracking information for analytics
    - budget_id (optional): Budget identifier to create basket from
    - order_id (optional): Order identifier to create basket from
    - empty_basket (optional): Create empty basket from order ID
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - New basket ID and details
    - Basket status and configuration
    - Creation metadata
    
    Example usage:
    "Create a new shopping basket"
    "Initialize a basket for mobile device"
    "Create basket from budget ID 'BDG123'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "client_device": {
                "type": "string",
                "description": "Type of client device",
                "enum": ["desktop", "mobile", "tablet"]
            },
            "origin": {
                "type": "string",
                "description": "Origin of the reservation"
            },
            "tracking": {
                "type": "object",
                "description": "Tracking information for analytics",
                "properties": {
                    "origin": {
                        "type": "string",
                        "enum": ["googlehpa", "trivago", "trivagocpa", "tripadvisor"],
                        "description": "Tracking origin"
                    },
                    "code": {
                        "type": "string",
                        "description": "Tracking code"
                    },
                    "locale": {
                        "type": "string", 
                        "description": "Tracking locale"
                    }
                },
                "required": ["origin", "code"],
                "additionalProperties": False
            },
            "client_location": {
                "type": "object",
                "description": "Client location information",
                "properties": {
                    "country": {
                        "type": "string",
                        "description": "Country where the client is located"
                    },
                    "ip": {
                        "type": "string",
                        "description": "Client IP address"
                    }
                },
                "additionalProperties": False
            },
            "budget_id": {
                "type": "string",
                "description": "Budget identifier to create basket from"
            },
            "order_id": {
                "type": "string",
                "description": "Order identifier to create basket from"
            },
            "empty_basket": {
                "type": "boolean",
                "description": "Create empty basket from order ID",
                "default": False
            },
            "call_center_properties": {
                "type": "object",
                "description": "Call center specific properties",
                "properties": {
                    "ignore_release": {"type": "boolean"},
                    "ignore_min_stay": {"type": "boolean"},
                    "ignore_availability": {"type": "boolean"},
                    "override_price": {"type": "number"},
                    "override_deposit": {"type": "number"},
                    "override_discount": {"type": "number"},
                    "ignore_required_extra": {"type": "boolean"},
                    "ignore_required_fields": {"type": "boolean"},
                    "override_country": {"type": "string"},
                    "override_inbound_method": {
                        "type": "string",
                        "enum": ["inbound", "outbound", "email", "whatsapp", "walkin"]
                    }
                },
                "additionalProperties": False
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "additionalProperties": False
    }
)


class BasketCreateRQHandler:
    """Handler for the BasketCreateRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_create_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the basket creation request.
        
        Args:
            arguments: Tool arguments containing basket creation parameters
            
        Returns:
            Dictionary containing the new basket details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            language = arguments.get("language", "es")
            
            self.logger.info(
                "Creating new basket",
                language=language,
                client_device=arguments.get("client_device"),
                origin=arguments.get("origin")
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            # Add optional client location
            if arguments.get("client_location"):
                client_location = arguments["client_location"]
                formatted_location = {}
                
                if client_location.get("country"):
                    formatted_location["Country"] = client_location["country"]
                if client_location.get("ip"):
                    formatted_location["Ip"] = client_location["ip"]
                    
                if formatted_location:
                    request_payload["ClientLocation"] = formatted_location
            
            # Add optional client device
            if arguments.get("client_device"):
                request_payload["ClientDevice"] = arguments["client_device"]
            
            # Add optional origin
            if arguments.get("origin"):
                request_payload["Origin"] = arguments["origin"]
            
            # Add optional tracking information
            if arguments.get("tracking"):
                tracking = arguments["tracking"]
                formatted_tracking = {
                    "Origin": tracking["origin"],
                    "Code": tracking["code"]
                }
                if tracking.get("locale"):
                    formatted_tracking["Locale"] = tracking["locale"]
                    
                request_payload["Tracking"] = formatted_tracking
            
            # Add optional budget or order ID
            if arguments.get("budget_id"):
                request_payload["BudgetId"] = arguments["budget_id"]
                
            if arguments.get("order_id"):
                request_payload["OrderId"] = arguments["order_id"]
                
            if arguments.get("empty_basket"):
                request_payload["EmptyBasket"] = arguments["empty_basket"]
            
            # Add optional call center properties
            if arguments.get("call_center_properties"):
                cc_props = arguments["call_center_properties"]
                formatted_props = {}
                
                field_mapping = {
                    "ignore_release": "IgnoreRelease",
                    "ignore_min_stay": "IgnoreMinStay", 
                    "ignore_availability": "IgnoreAvailability",
                    "override_price": "OverridePrice",
                    "override_deposit": "OverrideDeposit",
                    "override_discount": "OverrideDiscount",
                    "ignore_required_extra": "IgnoreRequiredExtra",
                    "ignore_required_fields": "IgnoreRequiredFields",
                    "override_country": "OverrideCountry",
                    "override_inbound_method": "OverrideInboundMethod"
                }
                
                for key, value in cc_props.items():
                    if key in field_mapping and value is not None:
                        formatted_props[field_mapping[key]] = value
                        
                if formatted_props:
                    request_payload["CallCenterProperties"] = formatted_props
            
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
                
                # Make the basket creation request
                response = await client.post("/BasketCreateRQ", request_payload)
            
            # Extract basket information from response
            basket_info = response.get("BasketInfo", {})
            
            # Log successful operation
            self.logger.info(
                "Basket created successfully",
                basket_id=basket_info.get("BasketId"),
                basket_status=basket_info.get("BasketStatus"),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "basket_info": basket_info,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "creation_context": {
                    "client_device": arguments.get("client_device"),
                    "origin": arguments.get("origin"),
                    "from_budget": bool(arguments.get("budget_id")),
                    "from_order": bool(arguments.get("order_id")),
                    "empty_basket": arguments.get("empty_basket", False)
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message="Shopping basket created successfully"
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
handler = BasketCreateRQHandler()


async def call_basket_create_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketCreateRQ endpoint.
    
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
            basket_info = data["basket_info"]
            creation_context = data["creation_context"]
            
            response_text = f"""🛒 **Shopping Basket Created Successfully**

✅ **Basket Information:**
- **Basket ID**: {basket_info.get('BasketId', 'Not assigned')}
- **Status**: {basket_info.get('BasketStatus', 'Unknown')}
- **Budget ID**: {basket_info.get('BudgetId', 'Not assigned')}
- **Order ID**: {basket_info.get('OrderId', 'Not assigned')}

📱 **Creation Context:**
- **Client Device**: {creation_context.get('client_device', 'Not specified')}
- **Origin**: {creation_context.get('origin', 'Not specified')}
- **Created from Budget**: {'Yes' if creation_context.get('from_budget') else 'No'}
- **Created from Order**: {'Yes' if creation_context.get('from_order') else 'No'}
- **Empty Basket**: {'Yes' if creation_context.get('empty_basket') else 'No'}
"""
            
            # Add rewards information if available
            if basket_info.get("Rewards") is not None:
                response_text += f"- **Rewards Enabled**: {'Yes' if basket_info.get('Rewards') else 'No'}\n"
            
            # Add call center properties if available
            if basket_info.get("CallCenterProperties"):
                response_text += "\n🏢 **Call Center Properties**: Configured\n"
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **Next Steps:**
- Use `basket_add_product_rq` to add hotel rooms, packages, or products
- Use `basket_summary_rq` to view basket contents  
- Use `basket_lock_rq` to lock the basket before confirmation
- Use `basket_confirm_rq` to complete the reservation

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Create Shopping Basket**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify your authentication credentials
- Check that the budget or order ID exists (if specified)
- Ensure the tracking information is valid
- Verify client location and device information
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while creating the basket:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
