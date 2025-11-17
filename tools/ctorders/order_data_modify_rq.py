"""
OrderDataModifyRQ - Order Data Modification Tool

This tool modifies various data fields of existing confirmed reservations.
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
    sanitize_string,
    parse_date
)

# Tool definition
ORDER_DATA_MODIFY_RQ_TOOL = Tool(
    name="order_data_modify_rq",
    description="""
    Modify various data fields of existing confirmed reservations.
    
    This tool allows updating reservation details including customer information,
    payment methods, special requests, language preferences, and billing data.
    It also supports gift data modifications and external system references.
    
    Parameters:
    - order_ids (required): List of order IDs to modify
    - avoid_send_client_email (optional): Prevent sending email to client
    - avoid_send_establishment_email (optional): Prevent sending email to establishment
    - payment_method (optional): New payment method details
    - language (optional): New language for the reservation
    - special_requests (optional): Updated special requests or comments
    - info_client (optional): Additional client information
    - info_hotel (optional): Additional hotel information
    - gift_data (optional): Gift-related information
    - billing_data (optional): Billing information updates
    - customer_data (optional): Customer data modifications
    - guest_data (optional): Guest data modifications
    - external_system (optional): External system reference
    - request_language (optional): Language for the request
    
    Returns:
    - Confirmation of successful modifications
    - Details of what was updated
    
    Example usage:
    "Update payment method for order ORD123456 to credit card"
    "Change special requests for reservation ORD789012"
    "Update customer information for order ORD555777"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of order IDs to modify",
                "items": {
                    "type": "string",
                    "description": "Order identifier (e.g., 'ORD123456')"
                },
                "minItems": 1,
                "maxItems": 50
            },
            "avoid_send_client_email": {
                "type": "boolean",
                "description": "If true, prevents sending modification email to the client",
                "default": False
            },
            "avoid_send_establishment_email": {
                "type": "boolean",
                "description": "If true, prevents sending modification email to the establishment",
                "default": False
            },
            "payment_method": {
                "type": "object",
                "description": "New payment method details",
                "properties": {
                    "credit_card": {
                        "type": "boolean",
                        "description": "Use credit card payment method"
                    },
                    "card_details": {
                        "type": "object",
                        "description": "Credit card details",
                        "properties": {
                            "holder_name": {
                                "type": "string",
                                "description": "Card holder name",
                                "maxLength": 100
                            },
                            "number": {
                                "type": "string",
                                "description": "Card number",
                                "maxLength": 20
                            },
                            "code": {
                                "type": "string",
                                "description": "Security code (CVV)",
                                "maxLength": 4
                            },
                            "expire_month": {
                                "type": "integer",
                                "description": "Expiration month (1-12)",
                                "minimum": 1,
                                "maximum": 12
                            },
                            "expire_year": {
                                "type": "integer",
                                "description": "Expiration year",
                                "minimum": 2024,
                                "maximum": 2040
                            }
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            },
            "reservation_language": {
                "type": "string",
                "description": "New language for the reservation",
                "enum": ["es", "en", "fr", "de", "it", "pt"]
            },
            "special_requests": {
                "type": "string",
                "description": "Updated special requests or comments",
                "maxLength": 1000
            },
            "info_client": {
                "type": "string",
                "description": "Additional client information",
                "maxLength": 1000
            },
            "info_hotel": {
                "type": "string",
                "description": "Additional hotel information",
                "maxLength": 1000
            },
            "gift_data": {
                "type": "object",
                "description": "Gift-related information",
                "properties": {
                    "firstname": {
                        "type": "string",
                        "description": "Gift recipient first name",
                        "maxLength": 100
                    },
                    "surname": {
                        "type": "string",
                        "description": "Gift recipient surname",
                        "maxLength": 100
                    },
                    "email": {
                        "type": "string",
                        "description": "Gift recipient email",
                        "format": "email",
                        "maxLength": 255
                    },
                    "message": {
                        "type": "string",
                        "description": "Gift message",
                        "maxLength": 500
                    },
                    "anonymous": {
                        "type": "boolean",
                        "description": "Whether the gift is anonymous"
                    },
                    "notification_date": {
                        "type": "string",
                        "description": "Gift notification date (YYYY-MM-DD)",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                    },
                    "delete_gift": {
                        "type": "boolean",
                        "description": "Remove gift data (default: false)"
                    }
                },
                "additionalProperties": False
            },
            "billing_data": {
                "type": "object",
                "description": "Billing information updates",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Billing name",
                        "maxLength": 200
                    },
                    "cif": {
                        "type": "string",
                        "description": "Tax identification number",
                        "maxLength": 50
                    },
                    "address": {
                        "type": "string",
                        "description": "Billing address",
                        "maxLength": 300
                    },
                    "zip": {
                        "type": "string",
                        "description": "Postal code",
                        "maxLength": 20
                    },
                    "city": {
                        "type": "string",
                        "description": "City",
                        "maxLength": 100
                    },
                    "country": {
                        "type": "string",
                        "description": "Country code",
                        "maxLength": 10
                    },
                    "delete_billing": {
                        "type": "boolean",
                        "description": "Remove billing data (default: false)"
                    }
                },
                "additionalProperties": False
            },
            "customer_data": {
                "type": "object",
                "description": "Customer data modifications",
                "properties": {
                    "firstname": {
                        "type": "string",
                        "description": "Customer first name",
                        "maxLength": 100
                    },
                    "surname": {
                        "type": "string",
                        "description": "Customer surname",
                        "maxLength": 100
                    },
                    "date_of_birthday": {
                        "type": "string",
                        "description": "Date of birth (YYYY-MM-DD)",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                    },
                    "passport": {
                        "type": "string",
                        "description": "Passport number",
                        "maxLength": 50
                    },
                    "address": {
                        "type": "string",
                        "description": "Address",
                        "maxLength": 300
                    },
                    "city": {
                        "type": "string",
                        "description": "City",
                        "maxLength": 100
                    },
                    "zip": {
                        "type": "string",
                        "description": "Postal code",
                        "maxLength": 20
                    },
                    "country": {
                        "type": "string",
                        "description": "Country code",
                        "maxLength": 10
                    },
                    "state": {
                        "type": "string",
                        "description": "State or province",
                        "maxLength": 100
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number",
                        "maxLength": 50
                    },
                    "fax": {
                        "type": "string",
                        "description": "Fax number",
                        "maxLength": 50
                    },
                    "mobile": {
                        "type": "string",
                        "description": "Mobile phone number",
                        "maxLength": 50
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address",
                        "format": "email",
                        "maxLength": 255
                    },
                    "arrival_time": {
                        "type": "string",
                        "description": "Arrival time",
                        "maxLength": 10
                    }
                },
                "additionalProperties": False
            },
            "guest_data": {
                "type": "array",
                "description": "Guest data modifications",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Guest ID (required if no RPH provided)",
                            "maxLength": 50
                        },
                        "hotel_guest_rph": {
                            "type": "integer",
                            "description": "Guest RPH",
                            "minimum": 1
                        },
                        "reference_rph_value": {
                            "type": "integer",
                            "description": "Room RPH of the guest",
                            "minimum": 1
                        },
                        "firstname": {
                            "type": "string",
                            "description": "Guest first name",
                            "maxLength": 100
                        },
                        "surname": {
                            "type": "string",
                            "description": "Guest surname",
                            "maxLength": 100
                        },
                        "passport": {
                            "type": "string",
                            "description": "Guest passport number",
                            "maxLength": 50
                        },
                        "email": {
                            "type": "string",
                            "description": "Guest email",
                            "format": "email",
                            "maxLength": 255
                        },
                        "date_of_birthday": {
                            "type": "string",
                            "description": "Guest date of birth (YYYY-MM-DD)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        }
                    },
                    "additionalProperties": False
                },
                "maxItems": 50
            },
            "external_system": {
                "type": "object",
                "description": "External system reference",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "External system code",
                        "maxLength": 50
                    },
                    "locator": {
                        "type": "string",
                        "description": "External system locator",
                        "maxLength": 100
                    }
                },
                "additionalProperties": False
            },
            "request_language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["order_ids"],
        "additionalProperties": False
    }
)


class OrderDataModifyRQHandler:
    """Handler for the OrderDataModifyRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_data_modify_rq")
    
    def _validate_order_ids(self, order_ids: List[str]) -> List[str]:
        """Validate and sanitize order IDs."""
        if not order_ids:
            raise ValidationError("At least one order ID is required")
        
        validated_ids = []
        for i, order_id in enumerate(order_ids):
            if not isinstance(order_id, str) or not order_id.strip():
                raise ValidationError(f"Order ID {i+1}: must be a non-empty string")
            
            sanitized_id = sanitize_string(order_id.strip())
            if not sanitized_id:
                raise ValidationError(f"Order ID {i+1}: invalid format after sanitization")
            
            validated_ids.append(sanitized_id)
        
        return validated_ids
    
    def _format_payment_method(self, payment_method: Dict[str, Any]) -> Dict[str, Any]:
        """Format payment method data for API request."""
        formatted = {}
        
        if payment_method.get("credit_card"):
            formatted["CreditCard"] = True
            
            card_details = payment_method.get("card_details", {})
            if card_details:
                card_info = {}
                
                if card_details.get("holder_name"):
                    card_info["HolderName"] = sanitize_string(card_details["holder_name"])
                if card_details.get("number"):
                    card_info["Number"] = sanitize_string(card_details["number"])
                if card_details.get("code"):
                    card_info["Code"] = sanitize_string(card_details["code"])
                if card_details.get("expire_month"):
                    card_info["ExpireDateMonth"] = card_details["expire_month"]
                if card_details.get("expire_year"):
                    card_info["ExpireDateYear"] = card_details["expire_year"]
                
                if card_info:
                    formatted["Card"] = card_info
        
        return formatted
    
    def _format_gift_data(self, gift_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format gift data for API request."""
        formatted = {}
        
        if gift_data.get("firstname"):
            formatted["Firstname"] = sanitize_string(gift_data["firstname"])
        if gift_data.get("surname"):
            formatted["Surname"] = sanitize_string(gift_data["surname"])
        if gift_data.get("email"):
            formatted["Email"] = sanitize_string(gift_data["email"])
        if gift_data.get("message"):
            formatted["Message"] = sanitize_string(gift_data["message"])
        if "anonymous" in gift_data:
            formatted["Anonymous"] = gift_data["anonymous"]
        if gift_data.get("notification_date"):
            formatted["GiftNotificationDate"] = parse_date(gift_data["notification_date"])
        if gift_data.get("delete_gift"):
            formatted["DeleteGift"] = True
        
        return formatted
    
    def _format_billing_data(self, billing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format billing data for API request."""
        formatted = {}
        
        if billing_data.get("name"):
            formatted["Name"] = sanitize_string(billing_data["name"])
        if billing_data.get("cif"):
            formatted["Cif"] = sanitize_string(billing_data["cif"])
        if billing_data.get("address"):
            formatted["Address"] = sanitize_string(billing_data["address"])
        if billing_data.get("zip"):
            formatted["Zip"] = sanitize_string(billing_data["zip"])
        if billing_data.get("city"):
            formatted["City"] = sanitize_string(billing_data["city"])
        if billing_data.get("country"):
            formatted["Country"] = sanitize_string(billing_data["country"])
        if billing_data.get("delete_billing"):
            formatted["DeleteBilling"] = True
        
        return formatted
    
    def _format_customer_data(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format customer data for API request."""
        formatted = {}
        
        if customer_data.get("firstname"):
            formatted["Firstname"] = sanitize_string(customer_data["firstname"])
        if customer_data.get("surname"):
            formatted["Surname"] = sanitize_string(customer_data["surname"])
        if customer_data.get("date_of_birthday"):
            formatted["DateOfBirthday"] = parse_date(customer_data["date_of_birthday"])
        if customer_data.get("passport"):
            formatted["Passport"] = sanitize_string(customer_data["passport"])
        if customer_data.get("address"):
            formatted["Address"] = sanitize_string(customer_data["address"])
        if customer_data.get("city"):
            formatted["City"] = sanitize_string(customer_data["city"])
        if customer_data.get("zip"):
            formatted["Zip"] = sanitize_string(customer_data["zip"])
        if customer_data.get("country"):
            formatted["Country"] = sanitize_string(customer_data["country"])
        if customer_data.get("state"):
            formatted["State"] = sanitize_string(customer_data["state"])
        if customer_data.get("phone"):
            formatted["Phone"] = sanitize_string(customer_data["phone"])
        if customer_data.get("fax"):
            formatted["Fax"] = sanitize_string(customer_data["fax"])
        if customer_data.get("mobile"):
            formatted["Mobile"] = sanitize_string(customer_data["mobile"])
        if customer_data.get("email"):
            formatted["Email"] = sanitize_string(customer_data["email"])
        if customer_data.get("arrival_time"):
            formatted["ArrivalTime"] = sanitize_string(customer_data["arrival_time"])
        
        return formatted
    
    def _format_guest_data(self, guest_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format guest data for API request."""
        formatted_guests = []
        
        for guest in guest_data:
            formatted_guest = {}
            
            if guest.get("id"):
                formatted_guest["Id"] = sanitize_string(guest["id"])
            if guest.get("hotel_guest_rph"):
                formatted_guest["HotelGuestRPH"] = guest["hotel_guest_rph"]
            if guest.get("reference_rph_value"):
                formatted_guest["ReferenceRPHValue"] = guest["reference_rph_value"]
            if guest.get("firstname"):
                formatted_guest["Firstname"] = sanitize_string(guest["firstname"])
            if guest.get("surname"):
                formatted_guest["Surname"] = sanitize_string(guest["surname"])
            if guest.get("passport"):
                formatted_guest["Passport"] = sanitize_string(guest["passport"])
            if guest.get("email"):
                formatted_guest["Email"] = sanitize_string(guest["email"])
            if guest.get("date_of_birthday"):
                formatted_guest["DateOfBirthday"] = parse_date(guest["date_of_birthday"])
            
            if formatted_guest:
                formatted_guests.append(formatted_guest)
        
        return formatted_guests
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order data modification request.
        
        Args:
            arguments: Tool arguments containing modification details
            
        Returns:
            Dictionary containing the modification results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            order_ids = arguments.get("order_ids", [])
            avoid_send_client_email = arguments.get("avoid_send_client_email", False)
            avoid_send_establishment_email = arguments.get("avoid_send_establishment_email", False)
            payment_method = arguments.get("payment_method")
            reservation_language = arguments.get("reservation_language")
            special_requests = arguments.get("special_requests")
            info_client = arguments.get("info_client")
            info_hotel = arguments.get("info_hotel")
            gift_data = arguments.get("gift_data")
            billing_data = arguments.get("billing_data")
            customer_data = arguments.get("customer_data")
            guest_data = arguments.get("guest_data", [])
            external_system = arguments.get("external_system")
            request_language = arguments.get("request_language", "es")
            
            # Validate inputs
            validated_order_ids = self._validate_order_ids(order_ids)
            
            self.logger.info(
                "Initiating order data modification",
                order_count=len(validated_order_ids),
                has_payment_method=bool(payment_method),
                has_gift_data=bool(gift_data),
                has_billing_data=bool(billing_data),
                has_customer_data=bool(customer_data),
                guest_count=len(guest_data),
                language=request_language
            )
            
            # Create request payload
            request_data = create_standard_request(request_language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderId": validated_order_ids
            }
            
            # Add optional email settings
            if avoid_send_client_email:
                request_payload["AvoidSendClientEmail"] = True
            if avoid_send_establishment_email:
                request_payload["AvoidSendEstablishmentEmail"] = True
            
            # Add modification fields
            if payment_method:
                formatted_payment = self._format_payment_method(payment_method)
                if formatted_payment:
                    request_payload["PaymentMethod"] = formatted_payment
            
            if reservation_language:
                request_payload["Language"] = reservation_language
            
            if special_requests:
                request_payload["SpecialRequests"] = sanitize_string(special_requests)
            
            if info_client:
                request_payload["InfoClient"] = sanitize_string(info_client)
            
            if info_hotel:
                request_payload["InfoHotel"] = sanitize_string(info_hotel)
            
            if gift_data:
                formatted_gift = self._format_gift_data(gift_data)
                if formatted_gift:
                    request_payload["GiftData"] = formatted_gift
            
            if billing_data:
                formatted_billing = self._format_billing_data(billing_data)
                if formatted_billing:
                    request_payload["BillingData"] = formatted_billing
            
            if customer_data:
                formatted_customer = self._format_customer_data(customer_data)
                if formatted_customer:
                    request_payload["DataModifyCustomer"] = formatted_customer
            
            if guest_data:
                formatted_guests = self._format_guest_data(guest_data)
                if formatted_guests:
                    request_payload["DataModifyGuests"] = formatted_guests
            
            if external_system:
                formatted_external = {}
                if external_system.get("code"):
                    formatted_external["Code"] = sanitize_string(external_system["code"])
                if external_system.get("locator"):
                    formatted_external["Locator"] = sanitize_string(external_system["locator"])
                if formatted_external:
                    request_payload["ExternalSystem"] = formatted_external
            
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
                
                # Make the order data modification request
                response = await client.post("/OrderDataModifyRQ", request_payload)
            
            # Extract results from response
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Order data modification completed successfully",
                order_count=len(validated_order_ids),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Determine what was modified
            modifications = []
            if payment_method:
                modifications.append("Payment method")
            if reservation_language:
                modifications.append("Reservation language")
            if special_requests:
                modifications.append("Special requests")
            if info_client:
                modifications.append("Client information")
            if info_hotel:
                modifications.append("Hotel information")
            if gift_data:
                modifications.append("Gift data")
            if billing_data:
                modifications.append("Billing data")
            if customer_data:
                modifications.append("Customer data")
            if guest_data:
                modifications.append("Guest data")
            if external_system:
                modifications.append("External system reference")
            
            # Prepare response data
            response_data = {
                "modified_order_ids": validated_order_ids,
                "modifications_applied": modifications,
                "email_settings": {
                    "client_email_avoided": avoid_send_client_email,
                    "establishment_email_avoided": avoid_send_establishment_email
                },
                "modification_summary": {
                    "total_orders": len(validated_order_ids),
                    "modification_count": len(modifications),
                    "modifications": modifications
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Successfully modified {len(modifications)} field(s) for {len(validated_order_ids)} order(s)"
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
handler = OrderDataModifyRQHandler()


async def call_order_data_modify_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderDataModifyRQ endpoint.
    
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
            summary = data["modification_summary"]
            email_settings = data["email_settings"]
            
            response_text = f"""✅ **Order Data Modification Completed**

📋 **Modification Summary:**
- **Orders Modified**: {summary['total_orders']}
- **Fields Updated**: {summary['modification_count']}
- **Modifications Applied**: {', '.join(summary['modifications']) if summary['modifications'] else 'None'}

🔗 **Modified Orders:**
"""
            
            for order_id in data["modified_order_ids"]:
                response_text += f"- **{order_id}**: ✅ UPDATED\n"
            
            response_text += f"""
📧 **Email Notification Settings:**
- **Client Email**: {'Avoided' if email_settings['client_email_avoided'] else 'Sent'}
- **Establishment Email**: {'Avoided' if email_settings['establishment_email_avoided'] else 'Sent'}

📝 **Details of Modifications:**
"""
            
            for modification in summary['modifications']:
                response_text += f"- ✅ {modification}\n"
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Important Notes:**
- Changes are immediately effective
- Email notifications inform relevant parties
- Some modifications may require additional validation
- Payment method changes may need reprocessing
- Guest data updates apply to all related services
- Billing changes affect invoicing and documentation
"""
                
        else:
            response_text = f"""❌ **Order Data Modification Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check that orders are in modifiable status
- Validate all data formats and requirements
- Ensure required fields are provided
- Check payment method details if updating
- Verify guest and customer data formats
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while modifying order data:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
