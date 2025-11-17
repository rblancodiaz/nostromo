"""
OrderPutRQ - Order Put Tool

This tool creates or updates order information in the Neobookings system.
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
ORDER_PUT_RQ_TOOL = Tool(
    name="order_put_rq",
    description="""
    Create or update order information in the Neobookings system.
    
    This tool allows creating new orders or updating existing ones with comprehensive
    order details including customer information, room details, payments, and status.
    
    Parameters:
    - order_id (required): Order identifier
    - origin (required): Origin of the order
    - provider (required): Provider mapping
    - order_status (required): Order status details
    - customer_data (optional): Customer information
    - room_data (optional): Hotel room details
    - billing_data (optional): Billing information
    - payment_data (optional): Payment information
    - amounts_data (optional): Amount details
    - language (optional): Language for the request
    
    Returns:
    - Created or updated order ID
    - Confirmation of order processing
    - Detailed order information
    
    Example usage:
    "Create order ORD123456 from booking.com with confirmed status"
    "Update order ORD789012 with new customer information"
    "Put order ORD555777 with complete booking details"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Order identifier",
                "minLength": 1,
                "maxLength": 50
            },
            "origin": {
                "type": "string",
                "description": "Origin of the order",
                "minLength": 1,
                "maxLength": 100
            },
            "provider": {
                "type": "string",
                "description": "Provider mapping/client mapping",
                "minLength": 1,
                "maxLength": 100
            },
            "order_status": {
                "type": "object",
                "description": "Order status details",
                "properties": {
                    "order_state": {
                        "type": "string",
                        "enum": ["confirm", "cancel", "invalid"]
                    },
                    "payment_state": {
                        "type": "string",
                        "enum": ["entire", "partial", "pending"]
                    },
                    "payment_method": {
                        "type": "string",
                        "enum": [
                            "tpv", "tpvmanual", "card", "credit", "transference",
                            "moneyorder", "paypal", "cash", "financed", "otb", "other", "nil"
                        ]
                    },
                    "no_show": {
                        "type": "boolean",
                        "default": False
                    },
                    "payment_type": {
                        "type": "string",
                        "enum": ["full", "deposit"]
                    },
                    "when_pay": {
                        "type": "string",
                        "enum": ["now", "establishment", "scheduled"]
                    }
                },
                "required": ["order_state"]
            },
            "customer_data": {
                "type": "object",
                "description": "Customer information",
                "properties": {
                    "title": {"type": "string", "maxLength": 10},
                    "firstname": {"type": "string", "maxLength": 100},
                    "surname": {"type": "string", "maxLength": 100},
                    "date_of_birthday": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "address": {"type": "string", "maxLength": 200},
                    "zip": {"type": "string", "maxLength": 20},
                    "city": {"type": "string", "maxLength": 100},
                    "country": {"type": "string", "maxLength": 2},
                    "phone": {"type": "string", "maxLength": 20},
                    "email": {"type": "string", "maxLength": 100},
                    "passport": {"type": "string", "maxLength": 50},
                    "state": {"type": "string", "maxLength": 100}
                }
            },
            "amounts_data": {
                "type": "object",
                "description": "Amount details",
                "properties": {
                    "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                    "amount_final": {"type": "number", "minimum": 0},
                    "amount_total": {"type": "number", "minimum": 0},
                    "amount_base": {"type": "number", "minimum": 0},
                    "amount_taxes": {"type": "number", "minimum": 0},
                    "amount_tourist_tax": {"type": "number", "minimum": 0}
                }
            },
            "room_data": {
                "type": "array",
                "description": "Hotel room details",
                "items": {
                    "type": "object",
                    "properties": {
                        "arrival_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "departure_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "hotel_room_detail": {
                            "type": "object",
                            "properties": {
                                "hotel_id": {"type": "string"},
                                "hotel_room_id": {"type": "string"},
                                "hotel_room_name": {"type": "string"},
                                "hotel_room_description": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "billing_data": {
                "type": "object",
                "description": "Billing information",
                "properties": {
                    "name": {"type": "string", "maxLength": 200},
                    "cif": {"type": "string", "maxLength": 50},
                    "address": {"type": "string", "maxLength": 200},
                    "zip": {"type": "string", "maxLength": 20},
                    "city": {"type": "string", "maxLength": 100},
                    "country": {"type": "string", "maxLength": 2}
                }
            },
            "petitions": {
                "type": "string",
                "description": "Customer petitions/special requests",
                "maxLength": 1000
            },
            "first_payment": {
                "type": "number",
                "description": "First payment amount",
                "minimum": 0
            },
            "second_payment": {
                "type": "number",
                "description": "Second payment amount",
                "minimum": 0
            },
            "issue_costs": {
                "type": "number",
                "description": "Issue costs",
                "minimum": 0
            },
            "info_hotel": {
                "type": "string",
                "description": "Hotel information",
                "maxLength": 1000
            },
            "info_client": {
                "type": "string",
                "description": "Client information",
                "maxLength": 1000
            },
            "ignore_send_mail": {
                "type": "boolean",
                "description": "Ignore sending email",
                "default": False
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["order_id", "origin", "provider", "order_status"],
        "additionalProperties": False
    }
)


class OrderPutRQHandler:
    """Handler for the OrderPutRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_put_rq")
    
    def _validate_order_data(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize order data."""
        # Validate required fields
        order_id = sanitize_string(arguments.get("order_id", "").strip(), max_length=50)
        if not order_id:
            raise ValidationError("Order ID is required")
        
        origin = sanitize_string(arguments.get("origin", "").strip(), max_length=100)
        if not origin:
            raise ValidationError("Origin is required")
        
        provider = sanitize_string(arguments.get("provider", "").strip(), max_length=100)
        if not provider:
            raise ValidationError("Provider is required")
        
        # Validate order status
        order_status = arguments.get("order_status", {})
        if not order_status.get("order_state"):
            raise ValidationError("Order state is required")
        
        return {
            "order_id": order_id,
            "origin": origin,
            "provider": provider,
            "order_status": order_status
        }
    
    def _build_customer_detail(self, customer_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build customer detail structure."""
        if not customer_data:
            return None
        
        detail = {}
        
        # Map fields according to API specification
        field_mapping = {
            "title": "Title",
            "firstname": "Firstname",
            "surname": "Surname",
            "date_of_birthday": "DateOfBirthday",
            "address": "Address",
            "zip": "Zip",
            "city": "City",
            "country": "Country",
            "phone": "Phone",
            "email": "Email",
            "passport": "Passaport",  # Note: API uses "Passaport" (typo in API)
            "state": "State"
        }
        
        for key, api_key in field_mapping.items():
            if key in customer_data and customer_data[key]:
                if key in ["firstname", "surname", "address", "city", "email"]:
                    detail[api_key] = sanitize_string(customer_data[key])
                else:
                    detail[api_key] = customer_data[key]
        
        return detail if detail else None
    
    def _build_amounts_detail(self, amounts_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build amounts detail structure."""
        if not amounts_data:
            return None
        
        detail = {}
        
        # Map fields according to API specification
        field_mapping = {
            "currency": "Currency",
            "amount_final": "AmountFinal",
            "amount_total": "AmountTotal",
            "amount_base": "AmountBase",
            "amount_taxes": "AmountTaxes",
            "amount_tourist_tax": "AmountTouristTax"
        }
        
        for key, api_key in field_mapping.items():
            if key in amounts_data and amounts_data[key] is not None:
                detail[api_key] = amounts_data[key]
        
        return detail if detail else None
    
    def _build_billing_detail(self, billing_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build billing detail structure."""
        if not billing_data:
            return None
        
        detail = {}
        
        # Map fields according to API specification
        field_mapping = {
            "name": "Name",
            "cif": "Cif",
            "address": "Address",
            "zip": "Zip",
            "city": "City",
            "country": "Country"
        }
        
        for key, api_key in field_mapping.items():
            if key in billing_data and billing_data[key]:
                if key in ["name", "address", "city"]:
                    detail[api_key] = sanitize_string(billing_data[key])
                else:
                    detail[api_key] = billing_data[key]
        
        return detail if detail else None
    
    def _build_room_details(self, room_data: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """Build room details structure."""
        if not room_data:
            return None
        
        room_details = []
        
        for room in room_data:
            room_detail = {}
            
            if "arrival_date" in room:
                room_detail["ArrivalDate"] = parse_date(room["arrival_date"])
            if "departure_date" in room:
                room_detail["DepartureDate"] = parse_date(room["departure_date"])
            
            if "hotel_room_detail" in room:
                hotel_room = room["hotel_room_detail"]
                room_detail["HotelRoomDetail"] = {
                    "HotelId": hotel_room.get("hotel_id"),
                    "HotelRoomId": hotel_room.get("hotel_room_id"),
                    "HotelRoomName": hotel_room.get("hotel_room_name"),
                    "HotelRoomDescription": hotel_room.get("hotel_room_description")
                }
            
            # Initialize required empty arrays according to API spec
            room_detail["OrderHotelBoardDetail"] = []
            room_detail["OrderHotelGuestDetail"] = []
            
            room_details.append(room_detail)
        
        return room_details if room_details else None
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order put request.
        
        Args:
            arguments: Tool arguments containing order details
            
        Returns:
            Dictionary containing the order creation/update results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate basic order data
            validated_data = self._validate_order_data(arguments)
            language = arguments.get("language", "es")
            
            self.logger.info(
                "Creating/updating order",
                order_id=validated_data["order_id"],
                origin=validated_data["origin"],
                provider=validated_data["provider"],
                order_state=validated_data["order_status"].get("order_state"),
                language=language
            )
            
            # Build order details
            order_detail = {
                "OrderId": validated_data["order_id"],
                "Origin": validated_data["origin"],
                "Provider": validated_data["provider"],
                "OrderStatusDetail": validated_data["order_status"]
            }
            
            # Add optional customer data
            customer_detail = self._build_customer_detail(arguments.get("customer_data"))
            if customer_detail:
                order_detail["OrderCustomerDetail"] = customer_detail
            
            # Add optional amounts data
            amounts_detail = self._build_amounts_detail(arguments.get("amounts_data"))
            if amounts_detail:
                order_detail["OrderAmountsDetail"] = amounts_detail
            
            # Add optional billing data
            billing_detail = self._build_billing_detail(arguments.get("billing_data"))
            if billing_detail:
                order_detail["OrderCustomerBillingDetail"] = billing_detail
            
            # Add optional room data
            room_details = self._build_room_details(arguments.get("room_data"))
            if room_details:
                order_detail["OrderHotelRoomDetail"] = room_details
            
            # Add optional fields
            optional_fields = {
                "petitions": "Petitions",
                "first_payment": "FirstPayment",
                "second_payment": "SecondPayment",
                "issue_costs": "IssueCosts",
                "info_hotel": "InfoHotel",
                "info_client": "InfoClient",
                "ignore_send_mail": "IgnoreSendMail"
            }
            
            for arg_key, api_key in optional_fields.items():
                if arg_key in arguments and arguments[arg_key] is not None:
                    if arg_key in ["petitions", "info_hotel", "info_client"]:
                        order_detail[api_key] = sanitize_string(str(arguments[arg_key]))
                    else:
                        order_detail[api_key] = arguments[arg_key]
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderPutDetails": [order_detail]
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
                
                # Make the order put request
                response = await client.post("/OrderPutRQ", request_payload)
            
            # Extract response data
            created_order_ids = response.get("OrderId", [])
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Order put completed successfully",
                order_id=validated_data["order_id"],
                created_orders=len(created_order_ids),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "input_order_id": validated_data["order_id"],
                "created_order_ids": created_order_ids,
                "order_details": order_detail,
                "operation_summary": {
                    "origin": validated_data["origin"],
                    "provider": validated_data["provider"],
                    "order_state": validated_data["order_status"].get("order_state"),
                    "has_customer_data": bool(customer_detail),
                    "has_amounts_data": bool(amounts_detail),
                    "has_billing_data": bool(billing_detail),
                    "has_room_data": bool(room_details)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            success_message = f"Successfully processed order {validated_data['order_id']}"
            if created_order_ids:
                success_message += f" - Created order IDs: {', '.join(created_order_ids)}"
            
            return format_response(
                response_data,
                success=True,
                message=success_message
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
handler = OrderPutRQHandler()


async def call_order_put_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderPutRQ endpoint.
    
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
            summary = data["operation_summary"]
            created_orders = data["created_order_ids"]
            
            response_text = f"""✅ **Order Processing Completed**

📋 **Order Summary:**
- **Input Order ID**: {data['input_order_id']}
- **Origin**: {summary['origin']}
- **Provider**: {summary['provider']}
- **Order State**: {summary['order_state']}

🆔 **Created/Updated Order IDs:**
"""
            
            if created_orders:
                for order_id in created_orders:
                    response_text += f"- **{order_id}**: ✅ Successfully processed\n"
            else:
                response_text += "- No order IDs returned (possible update operation)\n"
            
            response_text += f"""
📊 **Data Components Included:**
- **Customer Data**: {'✅ Yes' if summary['has_customer_data'] else '❌ No'}
- **Amounts Data**: {'✅ Yes' if summary['has_amounts_data'] else '❌ No'}
- **Billing Data**: {'✅ Yes' if summary['has_billing_data'] else '❌ No'}
- **Room Data**: {'✅ Yes' if summary['has_room_data'] else '❌ No'}

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Order Information:**
- **Operation Type**: {'Creation' if created_orders else 'Update'}
- **Processing Status**: Successfully processed
- **Data Integration**: All provided components have been integrated
- **System Tracking**: Order is now tracked in the system
- **Workflow Status**: Ready for further processing

📝 **Important Notes:**
- Order has been created/updated in the system
- All provided data components have been integrated
- Order status reflects the current state
- Additional operations (payments, modifications) can now be performed
- Check order details to verify all information was processed correctly

🔄 **Next Steps:**
- Order is ready for confirmation if needed
- Payment processing can be initiated
- Notifications can be sent to relevant parties
- Order modifications can be made if required
- Status tracking is now available
"""
            
        else:
            response_text = f"""❌ **Order Processing Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order ID format is correct
- Check origin and provider values are valid
- Ensure order status is properly formatted
- Validate customer data fields if provided
- Check date formats (YYYY-MM-DD)
- Verify currency codes are 3-letter ISO format
- Ensure amounts are positive numbers
- Check email format if provided
- Verify country codes are 2-letter ISO format
- Ensure authentication credentials are valid
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while processing order:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
