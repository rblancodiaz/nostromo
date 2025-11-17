"""
BasketLockRQ - Lock Shopping Basket Tool

This tool handles locking a shopping basket in the Neobookings system to prevent
modifications before confirmation.
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
BASKET_LOCK_RQ_TOOL = Tool(
    name="basket_lock_rq",
    description="""
    Lock a shopping basket in the Neobookings system to prevent modifications.
    
    This tool locks a basket to ensure its contents cannot be modified while
    the confirmation process is in progress. This is typically done before
    collecting customer data and finalizing the reservation.
    
    Parameters:
    - basket_id (required): Identifier of the basket to lock
    - call_center_properties (optional): Call center specific properties
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Locked basket details
    - Room confirmation info and requirements
    - Payment and guest data requirements
    
    Example usage:
    "Lock basket 'BASKET123' before confirmation"
    "Secure the basket to proceed with booking"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "basket_id": {
                "type": "string",
                "description": "Identifier of the basket to lock",
                "minLength": 1
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
        "required": ["basket_id"],
        "additionalProperties": False
    }
)


class BasketLockRQHandler:
    """Handler for the BasketLockRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_lock_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the basket locking request.
        
        Args:
            arguments: Tool arguments containing basket ID and lock settings
            
        Returns:
            Dictionary containing the locked basket details and confirmation requirements
            
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
                "Locking basket",
                basket_id=basket_id,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                **request_data,
                "BasketId": basket_id
            }
            
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
                
                # Make the basket lock request
                response = await client.post("/BasketLockRQ", request_payload)
            
            # Extract basket details and confirmation info from response
            basket_detail = response.get("BasketDetail", {})
            hotel_room_confirm_info = response.get("HotelRoomConfirmInfo", [])
            
            # Log successful operation
            self.logger.info(
                "Basket locked successfully",
                basket_id=basket_id,
                basket_status=basket_detail.get("BasketStatus"),
                rooms_to_confirm=len(hotel_room_confirm_info),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Parse confirmation requirements
            confirmation_requirements = []
            for room_info in hotel_room_confirm_info:
                room_rph = room_info.get("HotelRoomRPH")
                req_info = {
                    "room_rph": room_rph,
                    "customer_required": room_info.get("CustomerRequiredInfo", {}),
                    "billing_required": room_info.get("BillingRequiredInfo", {}),
                    "guest_required": room_info.get("GuestRequiredInfo", []),
                    "payment_options": room_info.get("PaymentOptionsInfo", {}),
                    "payment_confirm": room_info.get("PaymentConfirmInfo", {}),
                    "payment_method": room_info.get("PaymentMethodInfo", {}),
                    "payment_plan": room_info.get("PaymentPlanInfo", {})
                }
                confirmation_requirements.append(req_info)
            
            # Prepare response data
            response_data = {
                "basket_id": basket_id,
                "basket_detail": basket_detail,
                "confirmation_requirements": confirmation_requirements,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "locked": basket_detail.get("BasketStatus") == "locked"
            }
            
            return format_response(
                response_data,
                success=True,
                message="Basket locked successfully and ready for confirmation"
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
handler = BasketLockRQHandler()


async def call_basket_lock_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketLockRQ endpoint.
    
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
            requirements = data["confirmation_requirements"]
            
            response_text = f"""🔒 **Basket Locked Successfully**

✅ **Basket Information:**
- **Basket ID**: {data['basket_id']}
- **Status**: {basket_detail.get('BasketStatus', 'Unknown')}
- **Budget ID**: {basket_detail.get('BudgetId', 'Not assigned')}
- **Order ID**: {basket_detail.get('OrderId', 'Not assigned')}
- **Locked**: {'Yes' if data.get('locked') else 'No'}

📋 **Confirmation Requirements** ({len(requirements)} rooms):
"""
            
            # Add confirmation requirements for each room
            for i, req in enumerate(requirements, 1):
                response_text += f"\n**Room {i} (RPH: {req['room_rph']}):**\n"
                
                # Customer requirements
                customer_req = req["customer_required"]
                required_fields = [k for k, v in customer_req.items() if v]
                if required_fields:
                    response_text += f"- **Customer Data Required**: {', '.join(required_fields)}\n"
                
                # Guest requirements
                guest_req = req["guest_required"]
                if guest_req:
                    response_text += f"- **Guest Data Required**: {len(guest_req)} guests\n"
                
                # Payment options
                payment_options = req["payment_options"]
                if payment_options.get("Card", {}).get("Accept"):
                    response_text += f"- **Payment Methods**: Credit Card accepted\n"
                if payment_options.get("Pos", {}).get("Accept"):
                    response_text += f"- **Payment Methods**: POS accepted\n"
                if payment_options.get("Transfer", {}).get("Accept"):
                    response_text += f"- **Payment Methods**: Transfer accepted\n"
                if payment_options.get("Paypal", {}).get("Accept"):
                    response_text += f"- **Payment Methods**: PayPal accepted\n"
                
                # Payment method requirements
                payment_method = req["payment_method"]
                if payment_method.get("Deposit"):
                    response_text += f"- **Payment Type**: Deposit payment available\n"
                if payment_method.get("Complete"):
                    response_text += f"- **Payment Type**: Full payment available\n"
                if payment_method.get("Establishment"):
                    response_text += f"- **Payment Type**: Pay at hotel available\n"
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **Next Steps:**
- Collect all required customer and guest information
- Prepare payment method details
- Use `basket_confirm_rq` with complete confirmation data
- Use `basket_unlock_rq` if you need to modify the basket

⚠️ **Important**: The basket is now locked and cannot be modified until unlocked or confirmed.

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Lock Basket**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the basket ID exists and is accessible
- Check if the basket is already locked
- Ensure the basket contains valid products
- Verify the basket is not already confirmed
- Check your authentication credentials
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while locking the basket:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
