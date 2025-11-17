"""
OrderDetailsRQ - Order Details Retrieval Tool

This tool retrieves comprehensive details of confirmed reservations in the Neobookings system.
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
    sanitize_string
)

# Tool definition
ORDER_DETAILS_RQ_TOOL = Tool(
    name="order_details_rq",
    description="""
    Retrieve comprehensive details of confirmed reservations.
    
    This tool fetches complete information about reservations including customer details,
    accommodation information, pricing breakdown, payment details, and booking status.
    It supports both order IDs and origin order IDs for flexible querying.
    
    Parameters:
    - order_ids (optional): List of internal order IDs to retrieve
    - order_ids_origin (optional): List of origin order IDs to retrieve
    - language (optional): Language for the request
    
    Returns:
    - Complete order details including customer, hotel, and payment information
    - Booking status and dates
    - Pricing breakdown and payment details
    - Guest information and special requests
    - Cancellation policies and penalties
    
    Example usage:
    "Get details for order ORD123456"
    "Show information for reservations ORD123456 and ORD789012"
    "Retrieve details for origin order ORIG789"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of internal order IDs to retrieve details for",
                "items": {
                    "type": "string",
                    "description": "Order identifier (e.g., 'ORD123456')"
                },
                "maxItems": 100
            },
            "order_ids_origin": {
                "type": "array",
                "description": "List of origin order IDs to retrieve details for",
                "items": {
                    "type": "string",
                    "description": "Origin order identifier (e.g., 'ORIG789')"
                },
                "maxItems": 100
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


class OrderDetailsRQHandler:
    """Handler for the OrderDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_details_rq")
    
    def _validate_order_ids(self, order_ids: List[str], field_name: str) -> List[str]:
        """Validate and sanitize order IDs."""
        if not order_ids:
            return []
        
        validated_ids = []
        for i, order_id in enumerate(order_ids):
            if not isinstance(order_id, str) or not order_id.strip():
                raise ValidationError(f"{field_name} {i+1}: must be a non-empty string")
            
            sanitized_id = sanitize_string(order_id.strip())
            if not sanitized_id:
                raise ValidationError(f"{field_name} {i+1}: invalid format after sanitization")
            
            validated_ids.append(sanitized_id)
        
        return validated_ids
    
    def _format_amounts_detail(self, amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Format amounts detail information for readable output."""
        if not amounts:
            return {}
        
        return {
            "currency": amounts.get("Currency"),
            "final_amount": amounts.get("AmountFinal"),
            "total_amount": amounts.get("AmountTotal"),
            "base_amount": amounts.get("AmountBase"),
            "taxes_amount": amounts.get("AmountTaxes"),
            "tourist_tax_amount": amounts.get("AmountTouristTax"),
            "before_amount": amounts.get("AmountBefore"),
            "inventory_amount": amounts.get("AmountBeforeInventory"),
            "max_amount": amounts.get("AmountBeforeMax"),
            "offers_amount": amounts.get("AmountOffers"),
            "discounts_amount": amounts.get("AmountDiscounts"),
            "extras_hidden_amount": amounts.get("AmountExtrasHidden"),
            "extras_amount": amounts.get("AmountExtras"),
            "deposit_amount": amounts.get("AmountDeposit"),
            "paid_amount": amounts.get("AmountPaid"),
            "loyalty_amount": amounts.get("AmountLoyalty")
        }
    
    def _format_customer_detail(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        """Format customer detail information."""
        if not customer:
            return {}
        
        return {
            "title": customer.get("Title"),
            "firstname": customer.get("Firstname"),
            "surname": customer.get("Surname"),
            "date_of_birthday": customer.get("DateOfBirthday"),
            "address": customer.get("Address"),
            "zip": customer.get("Zip"),
            "city": customer.get("City"),
            "country": customer.get("Country"),
            "state": customer.get("State"),
            "phone": customer.get("Phone"),
            "email": customer.get("Email"),
            "passport": customer.get("Passaport")
        }
    
    def _format_order_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Format order status information."""
        if not status:
            return {}
        
        return {
            "creation_date": status.get("CreationDate"),
            "last_update": status.get("LastUpdate"),
            "order_state": status.get("OrderState"),
            "payment_state": status.get("PaymentState"),
            "payment_method": status.get("PaymentMethod"),
            "no_show": status.get("NoShow", False),
            "payment_type": status.get("PaymentType"),
            "when_pay": status.get("WhenPay")
        }
    
    def _format_hotel_room_summary(self, rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format hotel room summary information."""
        formatted_rooms = []
        
        for room in rooms:
            formatted_room = {
                "availability_id": room.get("HotelRoomAvailabilityId"),
                "arrival_date": room.get("ArrivalDate"),
                "departure_date": room.get("DepartureDate"),
                "room_rph": room.get("HotelRoomRPH"),
                "package_id": room.get("PackageId"),
                "hotel_basic_detail": {},
                "amounts": {}
            }
            
            # Format hotel room basic detail
            hotel_detail = room.get("HotelRoomBasicDetail", {})
            if hotel_detail:
                formatted_room["hotel_basic_detail"] = {
                    "hotel_id": hotel_detail.get("HotelId"),
                    "hotel_hash": hotel_detail.get("HotelHash"),
                    "hotel_name": hotel_detail.get("HotelName"),
                    "room_id": hotel_detail.get("HotelRoomId"),
                    "room_name": hotel_detail.get("HotelRoomName"),
                    "room_description": hotel_detail.get("HotelRoomDescription"),
                    "room_area": hotel_detail.get("HotelRoomArea"),
                    "hidden": hotel_detail.get("Hidden", False),
                    "order": hotel_detail.get("Order"),
                    "upgrade_class": hotel_detail.get("UpgradeClass"),
                    "upgrade_allowed": hotel_detail.get("UpgradeAllowed")
                }
            
            # Format amounts
            amounts = room.get("AmountsDetail", {})
            if amounts:
                formatted_room["amounts"] = self._format_amounts_detail(amounts)
            
            formatted_rooms.append(formatted_room)
        
        return formatted_rooms
    
    def _format_payment_details(self, payments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format payment details information."""
        formatted_payments = []
        
        for payment in payments:
            formatted_payment = {
                "id": payment.get("Id"),
                "method": payment.get("Method"),
                "creation_date": payment.get("CreationDate"),
                "description": payment.get("Description"),
                "removed": payment.get("Removed", False),
                "amount_detail": {}
            }
            
            # Format amounts
            amounts = payment.get("AmountDetail", {})
            if amounts:
                formatted_payment["amount_detail"] = self._format_amounts_detail(amounts)
            
            formatted_payments.append(formatted_payment)
        
        return formatted_payments
    
    def _format_order_details(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format complete order details information."""
        formatted_orders = []
        
        for order in orders:
            formatted_order = {
                "order_id": order.get("OrderId"),
                "order_id_origin": order.get("OrderIdOrigin"),
                "basket_id": order.get("BasketId"),
                "order_rph": order.get("OrderRPH"),
                "origin": order.get("Origin"),
                "origin_ads": order.get("OriginAds"),
                "origin_context": order.get("OriginContext"),
                "order_language": order.get("OrderLanguage"),
                "advertising_authorization": order.get("AdvertisingAuthorization", False),
                "with_data_authorization": order.get("WithDataAuthorization", False),
                "loyalty_authorization": order.get("LoyaltyAuthorization", False),
                "has_products": order.get("HasProducts", False),
                "domain": order.get("Domain")
            }
            
            # Format order status
            status = order.get("OrderStatusDetail", {})
            if status:
                formatted_order["order_status"] = self._format_order_status(status)
            
            # Format amounts
            amounts = order.get("OrderAmountsDetail", {})
            if amounts:
                formatted_order["amounts"] = self._format_amounts_detail(amounts)
            
            # Format customer details
            customer = order.get("CustomerDetail", {})
            if customer:
                formatted_order["customer"] = self._format_customer_detail(customer)
            
            # Format hotel room summaries
            rooms = order.get("HotelRoomSummaryDetail", [])
            if rooms:
                formatted_order["hotel_rooms"] = self._format_hotel_room_summary(rooms)
            
            # Format payment details
            payments = order.get("OrderPaymentDetail", [])
            if payments:
                formatted_order["payments"] = self._format_payment_details(payments)
            
            # Add other details
            if order.get("HotelGuestSummaryDetail"):
                formatted_order["guests_count"] = len(order["HotelGuestSummaryDetail"])
            if order.get("HotelBoardSummaryDetail"):
                formatted_order["boards_count"] = len(order["HotelBoardSummaryDetail"])
            if order.get("HotelRateSummaryDetail"):
                formatted_order["rates_count"] = len(order["HotelRateSummaryDetail"])
            if order.get("HotelOfferSummaryDetail"):
                formatted_order["offers_count"] = len(order["HotelOfferSummaryDetail"])
            if order.get("HotelExtraSummaryDetail"):
                formatted_order["extras_count"] = len(order["HotelExtraSummaryDetail"])
            
            formatted_orders.append(formatted_order)
        
        return formatted_orders
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order details retrieval request.
        
        Args:
            arguments: Tool arguments containing order identifiers
            
        Returns:
            Dictionary containing the order details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            order_ids = arguments.get("order_ids", [])
            order_ids_origin = arguments.get("order_ids_origin", [])
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_order_ids = self._validate_order_ids(order_ids, "Order ID")
            validated_order_ids_origin = self._validate_order_ids(order_ids_origin, "Origin Order ID")
            
            if not validated_order_ids and not validated_order_ids_origin:
                raise ValidationError("At least one order ID or origin order ID is required")
            
            self.logger.info(
                "Retrieving order details",
                order_ids_count=len(validated_order_ids),
                origin_ids_count=len(validated_order_ids_origin),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"]
            }
            
            if validated_order_ids:
                request_payload["OrderId"] = validated_order_ids
            if validated_order_ids_origin:
                request_payload["OrderIdOrigin"] = validated_order_ids_origin
            
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
                
                # Make the order details request
                response = await client.post("/OrderDetailsRQ", request_payload)
            
            # Extract order details from response
            order_details = response.get("OrderDetails", [])
            api_response = response.get("Response", {})
            
            # Format order details
            formatted_orders = self._format_order_details(order_details)
            
            # Log successful operation
            self.logger.info(
                "Order details retrieved successfully",
                requested_orders=len(validated_order_ids),
                requested_origin_orders=len(validated_order_ids_origin),
                orders_found=len(formatted_orders),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "requested_order_ids": validated_order_ids,
                "requested_origin_order_ids": validated_order_ids_origin,
                "order_details": formatted_orders,
                "summary": {
                    "total_requested": len(validated_order_ids) + len(validated_order_ids_origin),
                    "orders_found": len(formatted_orders),
                    "orders_missing": (len(validated_order_ids) + len(validated_order_ids_origin)) - len(formatted_orders)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {len(formatted_orders)} order(s)"
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
handler = OrderDetailsRQHandler()


async def call_order_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderDetailsRQ endpoint.
    
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
            summary = data["summary"]
            order_details = data["order_details"]
            
            response_text = f"""📋 **Order Details Retrieval**

📊 **Summary:**
- **Total Orders Requested**: {summary['total_requested']}
- **Orders Found**: {summary['orders_found']}
- **Orders Missing**: {summary['orders_missing']}

"""
            
            if order_details:
                response_text += f"""📑 **Order Details ({len(order_details)} found):**
{'='*80}
"""
                
                for i, order in enumerate(order_details, 1):
                    response_text += f"""
📑 **Order #{i} - {order['order_id']}**
{'-'*60}

🏷️ **Basic Information:**
- **Order ID**: {order['order_id']}
- **Origin Order ID**: {order.get('order_id_origin', 'N/A')}
- **Basket ID**: {order.get('basket_id', 'N/A')}
- **Order RPH**: {order.get('order_rph', 'N/A')}
- **Origin**: {order.get('origin', 'N/A')}
- **Language**: {order.get('order_language', 'N/A')}
- **Domain**: {order.get('domain', 'N/A')}
"""
                    
                    # Order status
                    status = order.get('order_status', {})
                    if status:
                        response_text += f"""
📊 **Order Status:**
- **Creation Date**: {status.get('creation_date', 'N/A')}
- **Last Update**: {status.get('last_update', 'N/A')}
- **Order State**: {status.get('order_state', 'N/A')}
- **Payment State**: {status.get('payment_state', 'N/A')}
- **Payment Method**: {status.get('payment_method', 'N/A')}
- **Payment Type**: {status.get('payment_type', 'N/A')}
- **No Show**: {'Yes' if status.get('no_show') else 'No'}
"""
                    
                    # Customer information
                    customer = order.get('customer', {})
                    if customer:
                        response_text += f"""
👤 **Customer Information:**
- **Name**: {customer.get('firstname', '')} {customer.get('surname', '')}
- **Email**: {customer.get('email', 'N/A')}
- **Phone**: {customer.get('phone', 'N/A')}
- **Address**: {customer.get('address', 'N/A')}
- **City**: {customer.get('city', 'N/A')}, {customer.get('country', 'N/A')}
- **Passport**: {customer.get('passport', 'N/A')}
"""
                    
                    # Amounts information
                    amounts = order.get('amounts', {})
                    if amounts and amounts.get('final_amount'):
                        response_text += f"""
💰 **Pricing Information:**
- **Final Amount**: {amounts.get('final_amount', 'N/A')} {amounts.get('currency', '')}
- **Base Amount**: {amounts.get('base_amount', 'N/A')} {amounts.get('currency', '')}
- **Taxes**: {amounts.get('taxes_amount', 'N/A')} {amounts.get('currency', '')}
- **Tourist Tax**: {amounts.get('tourist_tax_amount', 'N/A')} {amounts.get('currency', '')}
"""
                        if amounts.get('offers_amount') and amounts['offers_amount'] > 0:
                            response_text += f"- **Offers Discount**: -{amounts['offers_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('discounts_amount') and amounts['discounts_amount'] > 0:
                            response_text += f"- **Additional Discounts**: -{amounts['discounts_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('paid_amount'):
                            response_text += f"- **Amount Paid**: {amounts['paid_amount']} {amounts.get('currency', '')}\n"
                    
                    # Hotel rooms information
                    hotel_rooms = order.get('hotel_rooms', [])
                    if hotel_rooms:
                        response_text += f"""
🏨 **Hotel Accommodation ({len(hotel_rooms)} room(s)):**
"""
                        for j, room in enumerate(hotel_rooms, 1):
                            hotel_detail = room.get('hotel_basic_detail', {})
                            response_text += f"""
  **Room #{j}:**
  - **Hotel**: {hotel_detail.get('hotel_name', 'N/A')} (ID: {hotel_detail.get('hotel_id', 'N/A')})
  - **Room**: {hotel_detail.get('room_name', 'N/A')} (ID: {hotel_detail.get('room_id', 'N/A')})
  - **Check-in**: {room.get('arrival_date', 'N/A')}
  - **Check-out**: {room.get('departure_date', 'N/A')}
"""
                            if hotel_detail.get('room_description'):
                                response_text += f"  - **Description**: {hotel_detail['room_description']}\n"
                            if hotel_detail.get('room_area'):
                                response_text += f"  - **Area**: {hotel_detail['room_area']} m²\n"
                    
                    # Payment details
                    payments = order.get('payments', [])
                    if payments:
                        response_text += f"""
💳 **Payment Details ({len(payments)} payment(s)):**
"""
                        for j, payment in enumerate(payments, 1):
                            payment_amount = payment.get('amount_detail', {})
                            response_text += f"""
  **Payment #{j}:**
  - **Method**: {payment.get('method', 'N/A')}
  - **Date**: {payment.get('creation_date', 'N/A')}
  - **Amount**: {payment_amount.get('final_amount', 'N/A')} {payment_amount.get('currency', '')}
  - **Description**: {payment.get('description', 'N/A')}
  - **Status**: {'Removed' if payment.get('removed') else 'Active'}
"""
                    
                    # Additional counts
                    additional_info = []
                    if order.get('guests_count'):
                        additional_info.append(f"Guests: {order['guests_count']}")
                    if order.get('boards_count'):
                        additional_info.append(f"Boards: {order['boards_count']}")
                    if order.get('rates_count'):
                        additional_info.append(f"Rates: {order['rates_count']}")
                    if order.get('offers_count'):
                        additional_info.append(f"Offers: {order['offers_count']}")
                    if order.get('extras_count'):
                        additional_info.append(f"Extras: {order['extras_count']}")
                    
                    if additional_info:
                        response_text += f"""
📊 **Additional Components:**
- {' | '.join(additional_info)}
"""
                    
                    # Authorization information
                    auth_info = []
                    if order.get('advertising_authorization'):
                        auth_info.append("Advertising")
                    if order.get('loyalty_authorization'):
                        auth_info.append("Loyalty")
                    if order.get('with_data_authorization'):
                        auth_info.append("Data Usage")
                    
                    if auth_info:
                        response_text += f"""
✅ **Authorizations:**
- {' | '.join(auth_info)}
"""
                    
                    response_text += "\n"
            else:
                response_text += """❌ **No Order Details Found**

None of the requested orders were found or have details available.

**Possible reasons:**
- Order IDs do not exist
- Orders are not confirmed
- Insufficient permissions
- Orders are in a different system
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use order details for customer service inquiries
- Review payment status for financial operations
- Check accommodation details for service delivery
- Verify customer information for communications
- Use for cancellation and modification operations
"""
                
        else:
            response_text = f"""❌ **Order Details Retrieval Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check that orders are confirmed and accessible
- Ensure proper authentication credentials
- Verify user permissions for order access
- Check if orders belong to the correct system
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving order details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
