"""
OrderNotificationReadRQ - Order Notification Read Tool

This tool reads the notification status of one or more reservations in the Neobookings system.
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
ORDER_NOTIFICATION_READ_RQ_TOOL = Tool(
    name="order_notification_read_rq",
    description="""
    Read the notification status of one or more reservations in the Neobookings system.
    
    This tool allows checking the notification status of existing reservations by providing
    the order IDs. It returns information about whether reservations have been notified
    and to which systems/users.
    
    Parameters:
    - order_ids (required): List of order IDs to check notification status
    - language (optional): Language for the request
    
    Returns:
    - Notification status for each order
    - System and user notification details
    - Notification dates and timestamps
    
    Example usage:
    "Check notification status for order ORD123456"
    "Get notification details for orders ORD123456 and ORD789012"
    "Show notification status for reservation ORD555777"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of order IDs to check notification status",
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


class OrderNotificationReadRQHandler:
    """Handler for the OrderNotificationReadRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_notification_read_rq")
    
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
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order notification read request.
        
        Args:
            arguments: Tool arguments containing order IDs
            
        Returns:
            Dictionary containing the notification status results
            
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
                "Reading notification status for orders",
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
                
                # Make the notification read request
                response = await client.post("/OrderNotificationReadRQ", request_payload)
            
            # Extract notification data from response
            notifications = response.get("Notification", [])
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Notification status read completed successfully",
                requested_orders=len(validated_order_ids),
                notifications_found=len(notifications),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Process notification data
            processed_notifications = []
            for notification in notifications:
                processed_notification = {
                    "reservation_id": notification.get("ReservationId"),
                    "status": notification.get("Status"),
                    "date": notification.get("Date"),
                    "notified": notification.get("Notified", False),
                    "system": notification.get("System"),
                    "user": notification.get("User", {})
                }
                processed_notifications.append(processed_notification)
            
            # Create summary statistics
            total_notified = sum(1 for n in processed_notifications if n["notified"])
            total_pending = len(processed_notifications) - total_notified
            
            # Prepare response data
            response_data = {
                "requested_order_ids": validated_order_ids,
                "notifications": processed_notifications,
                "summary": {
                    "total_orders": len(validated_order_ids),
                    "notifications_found": len(processed_notifications),
                    "notified_count": total_notified,
                    "pending_count": total_pending,
                    "notification_rate": (total_notified / len(processed_notifications) * 100) if processed_notifications else 0
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            success_message = f"Retrieved notification status for {len(processed_notifications)} orders"
            
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
handler = OrderNotificationReadRQHandler()


async def call_order_notification_read_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderNotificationReadRQ endpoint.
    
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
            notifications = data["notifications"]
            
            response_text = f"""✅ **Order Notification Status Retrieved**

📊 **Summary:**
- **Total Orders Checked**: {summary['total_orders']}
- **Notifications Found**: {summary['notifications_found']}
- **Notified Orders**: {summary['notified_count']}
- **Pending Notifications**: {summary['pending_count']}
- **Notification Rate**: {summary['notification_rate']:.1f}%

📋 **Notification Details:**
"""
            
            # List notification status for each order
            for notification in notifications:
                status_icon = "✅" if notification["notified"] else "⏳"
                user_info = notification.get("user", {})
                user_details = ""
                if user_info:
                    user_details = f" (User: {user_info.get('Username', 'N/A')}, System: {user_info.get('System', 'N/A')})"
                
                response_text += f"""
**{notification['reservation_id']}** {status_icon}
- **Status**: {notification['status']}
- **Notified**: {'Yes' if notification['notified'] else 'No'}
- **Date**: {notification['date'] or 'N/A'}
- **System**: {notification['system'] or 'N/A'}{user_details}
"""
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Status Legend:**
- ✅ **Notified**: Notification has been sent successfully
- ⏳ **Pending**: Notification is pending or not sent
- **System**: Platform/channel that processed the notification
- **User**: User account that handled the notification

📝 **Notes:**
- Notification status helps track communication flow
- Pending notifications may require manual intervention
- Different systems may have different notification statuses
- Contact support if notification issues persist
"""
            
        else:
            response_text = f"""❌ **Order Notification Status Read Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check if orders have been confirmed
- Ensure authentication credentials are valid
- Verify API connectivity
- Review system permissions for notification access
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while reading notification status:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
