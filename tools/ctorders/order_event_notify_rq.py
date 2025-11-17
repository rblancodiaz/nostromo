"""
OrderEventNotifyRQ - Order Event Notification Tool

This tool notifies specific events that occurred for confirmed reservations.
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
ORDER_EVENT_NOTIFY_RQ_TOOL = Tool(
    name="order_event_notify_rq",
    description="""
    Notify specific events that occurred for confirmed reservations.
    
    This tool allows registering events that happened with reservations, such as
    confirmations, payments, cancellations, modifications, or other operational events.
    These events are tracked for auditing and operational monitoring purposes.
    
    Parameters:
    - order_id (required): Order ID for which the event occurred
    - event_type (required): Type of event that occurred
    - event_date (required): Date when the event occurred
    - event_info (optional): Additional information about the event
    - language (optional): Language for the request
    
    Returns:
    - Confirmation of event notification
    - Event registration details
    
    Example usage:
    "Notify payment confirmation for order ORD123456"
    "Register cancellation event for reservation ORD789012"
    "Log customer modification event for order ORD555777"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Order ID for which the event occurred",
                "minLength": 1,
                "maxLength": 100
            },
            "event_type": {
                "type": "string",
                "description": "Type of event that occurred",
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
            "event_date": {
                "type": "string",
                "description": "Date and time when the event occurred (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}(T\\d{2}:\\d{2}:\\d{2})?$"
            },
            "event_info": {
                "type": "string",
                "description": "Additional information or description about the event",
                "maxLength": 1000
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["order_id", "event_type", "event_date"],
        "additionalProperties": False
    }
)


class OrderEventNotifyRQHandler:
    """Handler for the OrderEventNotifyRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_event_notify_rq")
    
    def _format_event_date(self, event_date: str) -> str:
        """Format and validate event date."""
        try:
            # If only date is provided, add time component
            if len(event_date) == 10:  # YYYY-MM-DD format
                # Validate date format
                parse_date(event_date)
                return f"{event_date}T00:00:00"
            else:
                # Full datetime format, validate it
                if not event_date.endswith('Z') and '+' not in event_date:
                    # Add timezone if not present
                    return event_date
                return event_date
        except Exception:
            raise ValidationError(f"Invalid event date format: {event_date}")
    
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
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order event notification request.
        
        Args:
            arguments: Tool arguments containing event details
            
        Returns:
            Dictionary containing the notification results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            order_id = arguments.get("order_id", "").strip()
            event_type = arguments.get("event_type", "").strip()
            event_date = arguments.get("event_date", "").strip()
            event_info = arguments.get("event_info", "").strip()
            language = arguments.get("language", "es")
            
            # Validate inputs
            if not order_id:
                raise ValidationError("Order ID is required")
            if not event_type:
                raise ValidationError("Event type is required")
            if not event_date:
                raise ValidationError("Event date is required")
            
            sanitized_order_id = sanitize_string(order_id)
            if not sanitized_order_id:
                raise ValidationError("Invalid order ID format")
            
            formatted_event_date = self._format_event_date(event_date)
            
            sanitized_event_info = ""
            if event_info:
                sanitized_event_info = sanitize_string(event_info)
                if len(sanitized_event_info) > 1000:
                    raise ValidationError("Event info must not exceed 1000 characters")
            
            self.logger.info(
                "Notifying order event",
                order_id=sanitized_order_id,
                event_type=event_type,
                event_date=formatted_event_date,
                has_event_info=bool(sanitized_event_info),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderId": sanitized_order_id,
                "EventType": event_type,
                "EventDate": formatted_event_date
            }
            
            if sanitized_event_info:
                request_payload["EventInfo"] = sanitized_event_info
            
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
                
                # Make the order event notification request
                response = await client.post("/OrderEventNotifyRQ", request_payload)
            
            # Extract results from response
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Order event notification completed successfully",
                order_id=sanitized_order_id,
                event_type=event_type,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "order_id": sanitized_order_id,
                "event_type": event_type,
                "event_type_description": self._get_event_type_description(event_type),
                "event_date": formatted_event_date,
                "event_info": sanitized_event_info,
                "notification_status": "success",
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Successfully notified event '{event_type}' for order {sanitized_order_id}"
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
handler = OrderEventNotifyRQHandler()


async def call_order_event_notify_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderEventNotifyRQ endpoint.
    
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
            
            response_text = f"""✅ **Order Event Notification Successful**

📋 **Event Details:**
- **Order ID**: {data['order_id']}
- **Event Type**: {data['event_type']}
- **Event Description**: {data['event_type_description']}
- **Event Date**: {data['event_date']}
- **Notification Status**: {data['notification_status'].upper()}

"""
            
            if data.get('event_info'):
                response_text += f"""📝 **Additional Information:**
{data['event_info']}

"""
            
            response_text += f"""🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

📊 **Event Types Available:**
- **Confirmation Events**: CONFIRM
- **Email Events**: SEND_EMAIL_USER, SEND_EMAIL_HOTEL, SEND_EMAIL_USER_INVALID_CARD
- **Payment Events**: PAYMENT_AUTO_OK, PAYMENT_MANUAL_OK, PAYMENT_REFUND_OK, etc.
- **Tokenization Events**: TOKENIZE_AUTO_OK, TOKENIZE_MANUAL_OK, etc.
- **Cancellation Events**: CANCEL_MANUAL, AUTO_CANCEL_*, etc.
- **Booking.com Events**: BOOKINGCOM_AUTO_CANCEL_*, etc.
- **Verification Events**: VERIFYTOKEN_OK, VERIFYTOKEN_KO

💡 **Usage Notes:**
- Events are logged for audit and monitoring purposes
- Use appropriate event types for accurate tracking
- Include event_info for detailed context when needed
- Events help with operational analytics and troubleshooting
- Proper event logging improves customer service capabilities
"""
                
        else:
            response_text = f"""❌ **Order Event Notification Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order ID is correct and exists
- Check that event type is valid and supported
- Ensure event date format is correct (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- Verify event info length is within limits (max 1000 characters)
- Check authentication credentials
- Ensure order is in a state that allows event notification
- Review API response for specific error codes
- Contact support if the issue persists

📝 **Valid Event Types:**
CONFIRM, SEND_EMAIL_USER, SEND_EMAIL_HOTEL, TOKENIZE_AUTO_OK, 
PAYMENT_AUTO_OK, PAYMENT_MANUAL_OK, CANCEL_MANUAL, etc.
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while notifying order event:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
