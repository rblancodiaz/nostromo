"""
OrderEventSearchRQ - Order Event Search Tool

This tool searches for orders that have specific events within date ranges.
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
ORDER_EVENT_SEARCH_RQ_TOOL = Tool(
    name="order_event_search_rq",
    description="""
    Search for orders that have specific events within date ranges.
    
    This tool allows searching for reservations based on event occurrences,
    filtering by hotel, event types, and date ranges. It's useful for finding
    orders that experienced specific events like payments, cancellations, or confirmations.
    
    Parameters:
    - hotel_ids (required): List of hotel IDs to search within
    - event_types (required): List of event types to search for
    - date_from (optional): Start date for event search
    - date_to (optional): End date for event search
    - date_type (optional): Type of date filter to apply
    - language (optional): Language for the request
    
    Returns:
    - List of order IDs that match the search criteria
    - Event occurrence summary
    - Search parameters and results
    
    Example usage:
    "Find orders with payment events in the last month for hotel H123"
    "Search for cancelled reservations in hotels H123 and H456"
    "Get orders with confirmation events between 2024-01-01 and 2024-01-31"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel IDs to search within",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier (e.g., 'H123')"
                },
                "minItems": 1,
                "maxItems": 100
            },
            "event_types": {
                "type": "array",
                "description": "List of event types to search for",
                "items": {
                    "type": "string",
                    "enum": [
                        "CONFIRM",
                        "SEND_EMAIL_USER",
                        "SEND_EMAIL_HOTEL",
                        "SEND_EMAIL_USER_INVALID_CARD",
                        "TOKENIZE_AUTO_OK",
                        "TOKENIZE_AUTO_INVALID",
                        "TOKENIZE_MANUAL_OK",
                        "TOKENIZE_MANUAL_INVALID",
                        "PAYMENT_AUTO_OK",
                        "PAYMENT_AUTO_INVALID",
                        "PAYMENT_MANUAL_OK",
                        "PAYMENT_MANUAL_INVALID",
                        "PAYMENT_PAYBYLINK_CREATE",
                        "PAYMENT_REFUND_OK",
                        "PAYMENT_REFUND_INVALID",
                        "BOOKINGCOM_AUTO_CANCEL_OK",
                        "BOOKINGCOM_AUTO_CANCEL_DENIED",
                        "BOOKINGCOM_MARK_CARD_INVALID_OK",
                        "BOOKINGCOM_MARK_CARD_INVALID_DENIED",
                        "BOOKING_MODIFY_CREDITCARD",
                        "BOOKING_UPGRADE",
                        "AUTO_CANCEL_TPV",
                        "AUTO_CANCEL_CARD",
                        "AUTO_CANCEL_PAYPAL",
                        "AUTO_CANCEL_FINANCED",
                        "AUTO_CANCEL_TRANSFER",
                        "AUTO_CANCEL_NOSHOW",
                        "CANCEL_MANUAL",
                        "AUTO_CANCEL_VERIFYTOKEN",
                        "VERIFYTOKEN_OK",
                        "VERIFYTOKEN_KO"
                    ]
                },
                "minItems": 1,
                "maxItems": 20
            },
            "date_from": {
                "type": "string",
                "description": "Start date for event search (YYYY-MM-DD)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "date_to": {
                "type": "string",
                "description": "End date for event search (YYYY-MM-DD)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "date_type": {
                "type": "string",
                "description": "Type of date filter to apply",
                "enum": ["dateEvent", "dateArrival", "dateDeparture", "dateCreation"],
                "default": "dateEvent"
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["hotel_ids", "event_types"],
        "additionalProperties": False
    }
)


class OrderEventSearchRQHandler:
    """Handler for the OrderEventSearchRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_event_search_rq")
    
    def _validate_hotel_ids(self, hotel_ids: List[str]) -> List[str]:
        """Validate and sanitize hotel IDs."""
        if not hotel_ids:
            raise ValidationError("At least one hotel ID is required")
        
        validated_ids = []
        for i, hotel_id in enumerate(hotel_ids):
            if not isinstance(hotel_id, str) or not hotel_id.strip():
                raise ValidationError(f"Hotel ID {i+1}: must be a non-empty string")
            
            sanitized_id = sanitize_string(hotel_id.strip())
            if not sanitized_id:
                raise ValidationError(f"Hotel ID {i+1}: invalid format after sanitization")
            
            validated_ids.append(sanitized_id)
        
        return validated_ids
    
    def _validate_event_types(self, event_types: List[str]) -> List[str]:
        """Validate event types."""
        if not event_types:
            raise ValidationError("At least one event type is required")
        
        valid_event_types = {
            "CONFIRM", "SEND_EMAIL_USER", "SEND_EMAIL_HOTEL", "SEND_EMAIL_USER_INVALID_CARD",
            "TOKENIZE_AUTO_OK", "TOKENIZE_AUTO_INVALID", "TOKENIZE_MANUAL_OK", "TOKENIZE_MANUAL_INVALID",
            "PAYMENT_AUTO_OK", "PAYMENT_AUTO_INVALID", "PAYMENT_MANUAL_OK", "PAYMENT_MANUAL_INVALID",
            "PAYMENT_PAYBYLINK_CREATE", "PAYMENT_REFUND_OK", "PAYMENT_REFUND_INVALID",
            "BOOKINGCOM_AUTO_CANCEL_OK", "BOOKINGCOM_AUTO_CANCEL_DENIED", "BOOKINGCOM_MARK_CARD_INVALID_OK",
            "BOOKINGCOM_MARK_CARD_INVALID_DENIED", "BOOKING_MODIFY_CREDITCARD", "BOOKING_UPGRADE",
            "AUTO_CANCEL_TPV", "AUTO_CANCEL_CARD", "AUTO_CANCEL_PAYPAL", "AUTO_CANCEL_FINANCED",
            "AUTO_CANCEL_TRANSFER", "AUTO_CANCEL_NOSHOW", "CANCEL_MANUAL", "AUTO_CANCEL_VERIFYTOKEN",
            "VERIFYTOKEN_OK", "VERIFYTOKEN_KO"
        }
        
        validated_types = []
        for i, event_type in enumerate(event_types):
            if not isinstance(event_type, str) or not event_type.strip():
                raise ValidationError(f"Event type {i+1}: must be a non-empty string")
            
            cleaned_type = event_type.strip().upper()
            if cleaned_type not in valid_event_types:
                raise ValidationError(f"Event type {i+1}: '{event_type}' is not a valid event type")
            
            validated_types.append(cleaned_type)
        
        return list(set(validated_types))  # Remove duplicates
    
    def _get_event_type_description(self, event_type: str) -> str:
        """Get human-readable description for event type."""
        descriptions = {
            "CONFIRM": "Reservation confirmed",
            "SEND_EMAIL_USER": "Email sent to user",
            "SEND_EMAIL_HOTEL": "Email sent to hotel",
            "SEND_EMAIL_USER_INVALID_CARD": "Invalid card email sent to user",
            "TOKENIZE_AUTO_OK": "Automatic tokenization successful",
            "TOKENIZE_AUTO_INVALID": "Automatic tokenization failed",
            "TOKENIZE_MANUAL_OK": "Manual tokenization successful",
            "TOKENIZE_MANUAL_INVALID": "Manual tokenization failed",
            "PAYMENT_AUTO_OK": "Automatic payment successful",
            "PAYMENT_AUTO_INVALID": "Automatic payment failed",
            "PAYMENT_MANUAL_OK": "Manual payment successful",
            "PAYMENT_MANUAL_INVALID": "Manual payment failed",
            "PAYMENT_PAYBYLINK_CREATE": "Pay-by-link created",
            "PAYMENT_REFUND_OK": "Refund processed successfully",
            "PAYMENT_REFUND_INVALID": "Refund processing failed",
            "BOOKINGCOM_AUTO_CANCEL_OK": "Booking.com auto-cancellation successful",
            "BOOKINGCOM_AUTO_CANCEL_DENIED": "Booking.com auto-cancellation denied",
            "BOOKINGCOM_MARK_CARD_INVALID_OK": "Card marked invalid on Booking.com",
            "BOOKINGCOM_MARK_CARD_INVALID_DENIED": "Card invalid marking denied on Booking.com",
            "BOOKING_MODIFY_CREDITCARD": "Credit card modified",
            "BOOKING_UPGRADE": "Booking upgraded",
            "AUTO_CANCEL_TPV": "Automatic cancellation due to TPV issue",
            "AUTO_CANCEL_CARD": "Automatic cancellation due to card issue",
            "AUTO_CANCEL_PAYPAL": "Automatic cancellation due to PayPal issue",
            "AUTO_CANCEL_FINANCED": "Automatic cancellation due to financing issue",
            "AUTO_CANCEL_TRANSFER": "Automatic cancellation due to transfer issue",
            "AUTO_CANCEL_NOSHOW": "Automatic cancellation due to no-show",
            "CANCEL_MANUAL": "Manual cancellation",
            "AUTO_CANCEL_VERIFYTOKEN": "Automatic cancellation due to token verification",
            "VERIFYTOKEN_OK": "Token verification successful",
            "VERIFYTOKEN_KO": "Token verification failed"
        }
        
        return descriptions.get(event_type, event_type)
    
    def _get_date_type_description(self, date_type: str) -> str:
        """Get human-readable description for date type."""
        descriptions = {
            "dateEvent": "Event occurrence date",
            "dateArrival": "Reservation arrival date",
            "dateDeparture": "Reservation departure date",
            "dateCreation": "Reservation creation date"
        }
        
        return descriptions.get(date_type, date_type)
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order event search request.
        
        Args:
            arguments: Tool arguments containing search criteria
            
        Returns:
            Dictionary containing the search results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids", [])
            event_types = arguments.get("event_types", [])
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            date_type = arguments.get("date_type", "dateEvent")
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_hotel_ids = self._validate_hotel_ids(hotel_ids)
            validated_event_types = self._validate_event_types(event_types)
            
            # Validate dates if provided
            if date_from:
                parse_date(date_from)  # Validates format
            if date_to:
                parse_date(date_to)  # Validates format
            
            if date_from and date_to and date_from > date_to:
                raise ValidationError("Date from must be before date to")
            
            self.logger.info(
                "Searching for orders with events",
                hotel_count=len(validated_hotel_ids),
                event_type_count=len(validated_event_types),
                date_from=date_from,
                date_to=date_to,
                date_type=date_type,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "HotelId": validated_hotel_ids,
                "EventType": validated_event_types
            }
            
            # Add optional date filters
            if date_from:
                request_payload["DateFrom"] = date_from
            if date_to:
                request_payload["DateTo"] = date_to
            if date_type != "dateEvent":
                request_payload["DateType"] = date_type
            
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
                
                # Make the order event search request
                response = await client.post("/OrderEventSearchRQ", request_payload)
            
            # Extract search results from response
            reservation_ids = response.get("ReservationIds", [])
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Order event search completed successfully",
                hotels_searched=len(validated_hotel_ids),
                event_types_searched=len(validated_event_types),
                orders_found=len(reservation_ids),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "hotel_ids": validated_hotel_ids,
                    "event_types": validated_event_types,
                    "event_type_descriptions": [self._get_event_type_description(et) for et in validated_event_types],
                    "date_from": date_from,
                    "date_to": date_to,
                    "date_type": date_type,
                    "date_type_description": self._get_date_type_description(date_type)
                },
                "found_order_ids": reservation_ids,
                "search_summary": {
                    "hotels_searched": len(validated_hotel_ids),
                    "event_types_searched": len(validated_event_types),
                    "orders_found": len(reservation_ids),
                    "date_range_used": bool(date_from or date_to)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(reservation_ids)} order(s) with specified events"
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
handler = OrderEventSearchRQHandler()


async def call_order_event_search_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderEventSearchRQ endpoint.
    
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
            criteria = data["search_criteria"]
            summary = data["search_summary"]
            found_orders = data["found_order_ids"]
            
            response_text = f"""🔍 **Order Event Search Results**

📋 **Search Criteria:**
- **Hotels Searched**: {summary['hotels_searched']} hotel(s)
- **Event Types**: {summary['event_types_searched']} type(s)
- **Date Filter**: {criteria['date_type_description']}
- **Date Range**: {criteria['date_from'] or 'Not specified'} to {criteria['date_to'] or 'Not specified'}

🏨 **Hotels:**
"""
            
            for hotel_id in criteria["hotel_ids"]:
                response_text += f"- {hotel_id}\n"
            
            response_text += f"""
📅 **Event Types Searched:**
"""
            
            for i, (event_type, description) in enumerate(zip(criteria["event_types"], criteria["event_type_descriptions"])):
                response_text += f"- **{event_type}**: {description}\n"
            
            response_text += f"""

📊 **Search Results:**
- **Orders Found**: {summary['orders_found']}

"""
            
            if found_orders:
                response_text += f"""✅ **Found Orders ({len(found_orders)}):**
{'='*60}
"""
                
                # Display orders in groups for better readability
                orders_per_line = 5
                for i in range(0, len(found_orders), orders_per_line):
                    order_group = found_orders[i:i+orders_per_line]
                    response_text += f"📑 {' | '.join(order_group)}\n"
                
                response_text += f"""

💡 **Next Steps:**
- Use OrderDetailsRQ to get full details for these orders
- Use OrderEventReadRQ to see the complete event history
- Filter results further with different date ranges
- Analyze patterns in the found events
"""
            else:
                response_text += """❌ **No Orders Found**

No orders were found matching the specified event criteria.

**Possible reasons:**
- Events of the specified types have not occurred
- Date range is too restrictive
- Hotels have no activity in the specified period
- Events occurred outside the search parameters

**Suggestions:**
- Expand the date range
- Try different event types
- Check if hotels have any activity
- Verify hotel IDs are correct
- Use broader event type categories
"""
            
            # Event type categories for reference
            response_text += f"""

📚 **Event Type Categories:**
- **Confirmation**: CONFIRM
- **Email**: SEND_EMAIL_USER, SEND_EMAIL_HOTEL
- **Payment**: PAYMENT_AUTO_OK, PAYMENT_MANUAL_OK, PAYMENT_REFUND_OK
- **Cancellation**: CANCEL_MANUAL, AUTO_CANCEL_*
- **Tokenization**: TOKENIZE_AUTO_OK, TOKENIZE_MANUAL_OK
- **Verification**: VERIFYTOKEN_OK, VERIFYTOKEN_KO
- **Booking.com**: BOOKINGCOM_AUTO_CANCEL_*, BOOKINGCOM_MARK_CARD_*

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use for operational reporting and analytics
- Identify patterns in payment failures or cancellations
- Monitor hotel-specific event trends
- Find orders for follow-up actions
- Generate compliance and audit reports
"""
                
        else:
            response_text = f"""❌ **Order Event Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify hotel IDs are correct and exist
- Check that event types are valid
- Ensure date format is correct (YYYY-MM-DD)
- Verify date range is logical (from <= to)
- Check authentication credentials
- Ensure sufficient permissions for event access
- Review API response for specific error codes
- Contact support if the issue persists

📝 **Valid Event Types:**
CONFIRM, PAYMENT_AUTO_OK, PAYMENT_MANUAL_OK, CANCEL_MANUAL,
TOKENIZE_AUTO_OK, VERIFYTOKEN_OK, SEND_EMAIL_USER, etc.
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching for order events:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
