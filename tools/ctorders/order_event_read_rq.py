"""
OrderEventReadRQ - Order Event Reading Tool

This tool retrieves event history for confirmed reservations.
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
ORDER_EVENT_READ_RQ_TOOL = Tool(
    name="order_event_read_rq",
    description="""
    Retrieve event history for confirmed reservations.
    
    This tool fetches the complete event history for one or more reservations,
    showing all events that have occurred including confirmations, payments,
    cancellations, modifications, and other operational events with timestamps.
    
    Parameters:
    - order_ids (required): List of order IDs to retrieve event history for
    - language (optional): Language for the request
    
    Returns:
    - Complete event history for each order
    - Event types, dates, and descriptions
    - Chronological event timeline
    
    Example usage:
    "Get event history for order ORD123456"
    "Show all events for reservations ORD123456 and ORD789012"
    "Retrieve event timeline for order ORD555777"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of order IDs to retrieve event history for",
                "items": {
                    "type": "string",
                    "description": "Order identifier (e.g., 'ORD123456')"
                },
                "minItems": 1,
                "maxItems": 100
            },
            "language": {
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


class OrderEventReadRQHandler:
    """Handler for the OrderEventReadRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_event_read_rq")
    
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
    
    def _categorize_event(self, event_type: str) -> str:
        """Categorize event type for better organization."""
        if event_type == "CONFIRM":
            return "Confirmation"
        elif event_type.startswith("SEND_EMAIL"):
            return "Email"
        elif event_type.startswith("TOKENIZE"):
            return "Tokenization"
        elif event_type.startswith("PAYMENT"):
            return "Payment"
        elif event_type.startswith("BOOKINGCOM"):
            return "Booking.com"
        elif "CANCEL" in event_type:
            return "Cancellation"
        elif event_type.startswith("VERIFYTOKEN"):
            return "Verification"
        elif "MODIFY" in event_type or "UPGRADE" in event_type:
            return "Modification"
        else:
            return "Other"
    
    def _format_reservation_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format reservation event information."""
        formatted_events = []
        
        for event in events:
            formatted_event = {
                "order_id": event.get("OrderId"),
                "event_type": event.get("EventType"),
                "event_type_description": self._get_event_type_description(event.get("EventType", "")),
                "event_category": self._categorize_event(event.get("EventType", "")),
                "event_date": event.get("EventDate"),
                "event_info": event.get("EventInfo", "")
            }
            
            formatted_events.append(formatted_event)
        
        return formatted_events
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order event reading request.
        
        Args:
            arguments: Tool arguments containing order IDs
            
        Returns:
            Dictionary containing the event history
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            order_ids = arguments.get("order_ids", [])
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_order_ids = self._validate_order_ids(order_ids)
            
            self.logger.info(
                "Retrieving order event history",
                order_count=len(validated_order_ids),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderId": validated_order_ids
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
                
                # Make the order event read request
                response = await client.post("/OrderEventReadRQ", request_payload)
            
            # Extract event information from response
            reservation_events = response.get("ReservationEvent", [])
            api_response = response.get("Response", {})
            
            # Format event information
            formatted_events = self._format_reservation_events(reservation_events)
            
            # Group events by order ID
            events_by_order = {}
            for event in formatted_events:
                order_id = event["order_id"]
                if order_id not in events_by_order:
                    events_by_order[order_id] = []
                events_by_order[order_id].append(event)
            
            # Sort events by date within each order
            for order_id in events_by_order:
                events_by_order[order_id].sort(key=lambda x: x["event_date"] or "")
            
            # Log successful operation
            self.logger.info(
                "Order event history retrieved successfully",
                requested_orders=len(validated_order_ids),
                total_events=len(formatted_events),
                orders_with_events=len(events_by_order),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "requested_order_ids": validated_order_ids,
                "events_by_order": events_by_order,
                "all_events": formatted_events,
                "summary": {
                    "total_requested": len(validated_order_ids),
                    "orders_with_events": len(events_by_order),
                    "orders_without_events": len(validated_order_ids) - len(events_by_order),
                    "total_events": len(formatted_events)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved {len(formatted_events)} event(s) for {len(events_by_order)} order(s)"
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
handler = OrderEventReadRQHandler()


async def call_order_event_read_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderEventReadRQ endpoint.
    
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
            events_by_order = data["events_by_order"]
            
            response_text = f"""📋 **Order Event History**

📊 **Summary:**
- **Total Orders Requested**: {summary['total_requested']}
- **Orders with Events**: {summary['orders_with_events']}
- **Orders without Events**: {summary['orders_without_events']}
- **Total Events Found**: {summary['total_events']}

"""
            
            if events_by_order:
                response_text += f"""📚 **Event History by Order ({len(events_by_order)} orders):**
{'='*80}
"""
                
                for order_id, events in events_by_order.items():
                    response_text += f"""
📑 **Order: {order_id}**
{'-'*60}
**Events Found**: {len(events)}

"""
                    
                    # Group events by category for better organization
                    events_by_category = {}
                    for event in events:
                        category = event["event_category"]
                        if category not in events_by_category:
                            events_by_category[category] = []
                        events_by_category[category].append(event)
                    
                    # Display events by category
                    for category, cat_events in events_by_category.items():
                        response_text += f"""📂 **{category} Events ({len(cat_events)}):**
"""
                        
                        for i, event in enumerate(cat_events, 1):
                            status_icon = "✅" if any(word in event["event_type"] for word in ["OK", "CONFIRM"]) else "❌" if any(word in event["event_type"] for word in ["INVALID", "DENIED", "KO"]) else "ℹ️"
                            
                            response_text += f"""
  {status_icon} **Event #{i}:**
  - **Type**: {event['event_type']}
  - **Description**: {event['event_type_description']}
  - **Date**: {event['event_date']}
"""
                            
                            if event.get('event_info'):
                                response_text += f"  - **Details**: {event['event_info']}\n"
                        
                        response_text += "\n"
                    
                    response_text += "\n"
            else:
                response_text += """❌ **No Events Found**

None of the requested orders have recorded events.

**Possible reasons:**
- Orders are newly created without events yet
- Orders do not exist in the system
- Events have not been logged for these orders
- Insufficient permissions to view events
"""
            
            # Show orders without events
            if summary['orders_without_events'] > 0:
                orders_with_events = set(events_by_order.keys())
                orders_without_events = [oid for oid in data['requested_order_ids'] if oid not in orders_with_events]
                
                response_text += f"""
ℹ️ **Orders Without Events ({len(orders_without_events)}):**
"""
                for order_id in orders_without_events:
                    response_text += f"- {order_id}\n"
            
            # Event statistics
            if data["all_events"]:
                event_types = {}
                for event in data["all_events"]:
                    event_type = event["event_type"]
                    event_types[event_type] = event_types.get(event_type, 0) + 1
                
                response_text += f"""
📊 **Event Type Statistics:**
"""
                for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
                    response_text += f"- **{event_type}**: {count} occurrence(s)\n"
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use event history for troubleshooting order issues
- Monitor payment and confirmation events for status verification
- Review cancellation events for refund processing
- Check email events to confirm communications
- Use for audit trails and compliance reporting
- Event timeline helps understand order lifecycle
"""
                
        else:
            response_text = f"""❌ **Order Event History Retrieval Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check that orders are confirmed and accessible
- Ensure proper authentication credentials
- Verify user permissions for event access
- Check if orders have recorded events
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving order event history:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
