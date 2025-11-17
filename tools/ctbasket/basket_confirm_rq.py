"""
BasketConfirmRQ - Confirm Basket and Create Reservation Tool

This tool handles the final confirmation of a shopping basket and creates
a reservation in the Neobookings system.
"""

import json
from typing import Dict, Any, List, Optional
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
    validate_required_fields,
    sanitize_string
)

# Tool definition
BASKET_CONFIRM_RQ_TOOL = Tool(
    name="basket_confirm_rq",
    description="""
    Confirm a shopping basket and create a reservation in the Neobookings system.
    
    This tool processes the final confirmation of a basket, creating a definitive
    reservation with all customer data, payment information, and guest details.
    
    Parameters:
    - basket_id (required): Identifier of the basket to confirm
    - customer_language (optional): Customer's preferred language
    - order_id (optional): Order ID for modifications
    - room_upgrade (optional): Indicates if confirmation is an upgrade
    - avoid_send_client_email (optional): Avoid sending email to client
    - avoid_send_establishment_email (optional): Avoid sending email to hotel
    - hotel_room_confirm_data (optional): List of room confirmation data with guest details
    - gtm (optional): GTM tracking information
    - origin_ads (optional): Ads origin information
    - gift_data (optional): Gift/voucher information
    - metadata (optional): Additional metadata
    - external_system (optional): External system integration data
    - call_center_properties (optional): Call center specific properties
    - budget (optional): Budget indicator
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Order/Budget ID for the confirmed reservation
    - Confirmation details
    - Customer and booking information
    
    Example usage:
    "Confirm basket 'BASKET123' with customer data"
    "Complete the reservation for basket ID 'BSK456'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "basket_id": {
                "type": "string",
                "description": "Identifier of the basket to confirm",
                "minLength": 1
            },
            "customer_language": {
                "type": "string",
                "description": "Customer's preferred language code",
                "enum": ["es", "en", "fr", "de", "it", "pt"]
            },
            "order_id": {
                "type": "string",
                "description": "Order identifier for modification operations"
            },
            "room_upgrade": {
                "type": "boolean",
                "description": "Indicates if the confirmation is a room upgrade",
                "default": False
            },
            "avoid_send_client_email": {
                "type": "boolean", 
                "description": "Avoid sending confirmation email to client",
                "default": False
            },
            "avoid_send_establishment_email": {
                "type": "boolean",
                "description": "Avoid sending notification email to hotel", 
                "default": False
            },
            "hotel_room_confirm_data": {
                "type": "array",
                "description": "Room confirmation data with customer and guest information",
                "items": {
                    "type": "object",
                    "properties": {
                        "hotel_room_rph": {
                            "type": "number",
                            "description": "Room reference number"
                        },
                        "customer_data": {
                            "type": "object",
                            "description": "Customer/holder information",
                            "properties": {
                                "firstname": {"type": "string"},
                                "lastname": {"type": "string"},
                                "passport": {"type": "string"},
                                "email": {"type": "string", "format": "email"},
                                "address": {"type": "string"},
                                "city": {"type": "string"},
                                "postcode": {"type": "string"},
                                "country": {"type": "string"},
                                "state": {"type": "string"},
                                "phone": {"type": "string"},
                                "arrival_time": {"type": "string"},
                                "special_requests": {"type": "string"}
                            }
                        },
                        "billing_data": {
                            "type": "object",
                            "description": "Billing information",
                            "properties": {
                                "fiscal_name": {"type": "string"},
                                "fiscal_id": {"type": "string"},
                                "fiscal_address": {"type": "string"},
                                "postal_code": {"type": "string"},
                                "city": {"type": "string"},
                                "country": {"type": "string"}
                            }
                        },
                        "guest_data": {
                            "type": "array",
                            "description": "Guest information for the room",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "guest_rph": {"type": "number"},
                                    "firstname": {"type": "string"},
                                    "lastname": {"type": "string"},
                                    "birthdate": {"type": "string", "format": "date"},
                                    "passport": {"type": "string"},
                                    "email": {"type": "string", "format": "email"}
                                },
                                "required": ["guest_rph"]
                            }
                        },
                        "authorization_data": {
                            "type": "object",
                            "description": "Authorization preferences",
                            "properties": {
                                "rewards": {"type": "boolean"},
                                "offers": {"type": "boolean"}
                            }
                        },
                        "payment_method": {
                            "type": "object",
                            "description": "Payment method information",
                            "properties": {
                                "pos": {"type": "boolean"},
                                "transfer": {"type": "boolean"},
                                "paypal": {"type": "boolean"},
                                "financed": {"type": "boolean"},
                                "open_to_buy": {"type": "boolean"},
                                "credit_card": {"type": "boolean"},
                                "card": {
                                    "type": "object",
                                    "properties": {
                                        "holder_name": {"type": "string"},
                                        "number": {"type": "string"},
                                        "code": {"type": "string"},
                                        "expire_date_month": {"type": "number"},
                                        "expire_date_year": {"type": "number"}
                                    },
                                    "required": ["number", "expire_date_month", "expire_date_year"]
                                }
                            }
                        },
                        "payment_type": {
                            "type": "object",
                            "description": "Payment type configuration",
                            "properties": {
                                "deposit": {"type": "boolean"},
                                "establishment": {"type": "boolean"}
                            },
                            "required": ["deposit"]
                        },
                        "payment_plan": {
                            "type": "object",
                            "description": "Payment plan information",
                            "properties": {
                                "payment_plan_id": {"type": "string"}
                            },
                            "required": ["payment_plan_id"]
                        }
                    },
                    "required": ["hotel_room_rph", "guest_data"]
                }
            },
            "gtm": {
                "type": "string",
                "description": "Google Tag Manager information"
            },
            "origin_ads": {
                "type": "string",
                "description": "Advertisement origin information"
            },
            "gift_data": {
                "type": "object",
                "description": "Gift/voucher information",
                "properties": {
                    "firstname": {"type": "string"},
                    "surname": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                    "message": {"type": "string"},
                    "anonymous": {"type": "boolean"},
                    "gift_notification_date": {"type": "string", "format": "date-time"}
                }
            },
            "metadata": {
                "type": "string",
                "description": "Additional metadata for the reservation"
            },
            "budget": {
                "type": "boolean",
                "description": "Budget indicator", 
                "default": False
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


class BasketConfirmRQHandler:
    """Handler for the BasketConfirmRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_confirm_rq")
    
    def _format_customer_data(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format customer data for API request."""
        formatted = {}
        field_mapping = {
            "firstname": "Firstname",
            "lastname": "Lastname", 
            "passport": "Passport",
            "email": "Email",
            "address": "Address",
            "city": "City",
            "postcode": "Postcode",
            "country": "Country",
            "state": "State",
            "phone": "Phone",
            "arrival_time": "ArrivalTime",
            "special_requests": "SpecialRequests"
        }
        
        for key, value in customer_data.items():
            if key in field_mapping and value is not None:
                formatted[field_mapping[key]] = value
                
        return formatted
    
    def _format_billing_data(self, billing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format billing data for API request."""
        formatted = {}
        field_mapping = {
            "fiscal_name": "FiscalName",
            "fiscal_id": "FiscalId",
            "fiscal_address": "FiscalAddress", 
            "postal_code": "PostalCode",
            "city": "City",
            "country": "Country"
        }
        
        for key, value in billing_data.items():
            if key in field_mapping and value is not None:
                formatted[field_mapping[key]] = value
                
        return formatted
    
    def _format_guest_data(self, guest_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format guest data for API request."""
        formatted_guests = []
        
        for guest in guest_data:
            formatted_guest = {"GuestRPH": guest["guest_rph"]}
            
            field_mapping = {
                "firstname": "Firstname",
                "lastname": "Lastname",
                "birthdate": "Birthdate", 
                "passport": "Passport",
                "email": "Email"
            }
            
            for key, value in guest.items():
                if key in field_mapping and value is not None:
                    formatted_guest[field_mapping[key]] = value
                    
            formatted_guests.append(formatted_guest)
            
        return formatted_guests
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the basket confirmation request.
        
        Args:
            arguments: Tool arguments containing basket ID and confirmation details
            
        Returns:
            Dictionary containing the confirmation result
            
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
                "Confirming basket",
                basket_id=basket_id,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                **request_data,
                "BasketId": basket_id
            }
            
            # Add optional fields
            if arguments.get("customer_language"):
                request_payload["CustomerLanguage"] = arguments["customer_language"]
                
            if arguments.get("order_id"):
                request_payload["OrderId"] = arguments["order_id"]
                
            if arguments.get("room_upgrade"):
                request_payload["RoomUpgrade"] = arguments["room_upgrade"]
                
            if arguments.get("avoid_send_client_email"):
                request_payload["AvoidSendClientEmail"] = arguments["avoid_send_client_email"]
                
            if arguments.get("avoid_send_establishment_email"):
                request_payload["AvoidSendEstablishmentEmail"] = arguments["avoid_send_establishment_email"]
                
            # Format hotel room confirm data
            if arguments.get("hotel_room_confirm_data"):
                confirm_data = []
                for room_data in arguments["hotel_room_confirm_data"]:
                    formatted_room = {
                        "HotelRoomRPH": room_data["hotel_room_rph"],
                        "GuestData": self._format_guest_data(room_data["guest_data"])
                    }
                    
                    if room_data.get("customer_data"):
                        formatted_room["CustomerData"] = self._format_customer_data(room_data["customer_data"])
                        
                    if room_data.get("billing_data"):
                        formatted_room["BillingData"] = self._format_billing_data(room_data["billing_data"])
                        
                    if room_data.get("authorization_data"):
                        formatted_room["AuthorizationData"] = {
                            "Rewards": room_data["authorization_data"].get("rewards", False),
                            "Offers": room_data["authorization_data"].get("offers", False)
                        }
                        
                    if room_data.get("payment_method"):
                        payment_method = room_data["payment_method"]
                        formatted_payment = {}
                        
                        for key in ["pos", "transfer", "paypal", "financed", "open_to_buy", "credit_card"]:
                            if key in payment_method:
                                formatted_payment[key.replace("_", "").title()] = payment_method[key]
                                
                        if payment_method.get("card"):
                            card = payment_method["card"]
                            formatted_payment["Card"] = {
                                "Number": card["number"],
                                "ExpireDateMonth": card["expire_date_month"],
                                "ExpireDateYear": card["expire_date_year"]
                            }
                            if card.get("holder_name"):
                                formatted_payment["Card"]["HolderName"] = card["holder_name"]
                            if card.get("code"):
                                formatted_payment["Card"]["Code"] = card["code"]
                                
                        formatted_room["PaymentMethod"] = formatted_payment
                        
                    if room_data.get("payment_type"):
                        formatted_room["PaymentType"] = {
                            "Deposit": room_data["payment_type"]["deposit"]
                        }
                        if room_data["payment_type"].get("establishment"):
                            formatted_room["PaymentType"]["Establishment"] = room_data["payment_type"]["establishment"]
                            
                    if room_data.get("payment_plan"):
                        formatted_room["PaymentPlan"] = {
                            "PaymentPlanId": room_data["payment_plan"]["payment_plan_id"]
                        }
                        
                    confirm_data.append(formatted_room)
                    
                request_payload["HotelRoomConfirmData"] = confirm_data
            
            # Add other optional fields
            optional_fields = {
                "gtm": "GTM",
                "origin_ads": "OriginAds",
                "metadata": "MetaData",
                "budget": "Budget"
            }
            
            for arg_key, api_key in optional_fields.items():
                if arguments.get(arg_key) is not None:
                    request_payload[api_key] = arguments[arg_key]
            
            # Format gift data if provided
            if arguments.get("gift_data"):
                gift_data = arguments["gift_data"]
                formatted_gift = {}
                
                field_mapping = {
                    "firstname": "Firstname",
                    "surname": "Surname",
                    "email": "Email",
                    "message": "Message", 
                    "anonymous": "Anonymous",
                    "gift_notification_date": "GiftNotificationDate"
                }
                
                for key, value in gift_data.items():
                    if key in field_mapping and value is not None:
                        formatted_gift[field_mapping[key]] = value
                        
                request_payload["GiftData"] = formatted_gift
            
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
                
                # Make the basket confirmation request
                response = await client.post("/BasketConfirmRQ", request_payload)
            
            # Extract confirmation details from response
            order_id = response.get("OrderId")
            budget_id = response.get("BudgetId")
            requestor_id = response.get("RequestorId")
            
            # Log successful operation
            self.logger.info(
                "Basket confirmed successfully",
                basket_id=basket_id,
                order_id=order_id,
                budget_id=budget_id,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "basket_id": basket_id,
                "order_id": order_id,
                "budget_id": budget_id,
                "requestor_id": requestor_id,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "confirmation_type": "budget" if arguments.get("budget", False) else "reservation"
            }
            
            return format_response(
                response_data,
                success=True,
                message="Basket confirmed successfully and reservation created"
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
handler = BasketConfirmRQHandler()


async def call_basket_confirm_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketConfirmRQ endpoint.
    
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
            
            response_text = f"""🎉 **Basket Confirmed Successfully!**

✅ **Confirmation Details:**
- **Basket ID**: {data['basket_id']}
- **Type**: {data['confirmation_type'].title()}
"""
            
            if data.get("order_id"):
                response_text += f"- **Order ID**: {data['order_id']}\n"
            if data.get("budget_id"):
                response_text += f"- **Budget ID**: {data['budget_id']}\n"
            if data.get("requestor_id"):
                response_text += f"- **Requestor ID**: {data['requestor_id']}\n"
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **Next Steps:**
"""
            
            if data["confirmation_type"] == "reservation":
                response_text += """- Use `order_details_rq` to view complete reservation details
- Check your email for confirmation (if enabled)
- Hotel will receive notification (if enabled)
- Use the Order ID for future modifications or cancellations"""
            else:
                response_text += """- Use `budget_details_rq` to view budget details
- Budget can be sent to customer for review
- Budget can be converted to reservation later"""
            
            response_text += f"""

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Basket Confirmation Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the basket ID exists and is accessible
- Ensure the basket is locked before confirmation
- Check that all required guest data is provided
- Verify payment method information is complete
- Ensure the basket contains valid products
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while confirming the basket:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
