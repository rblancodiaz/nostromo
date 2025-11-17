"""
OrderNotificationRQ - Order Notification Creation Tool

This tool creates notifications for reservations to specific systems or users.
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
ORDER_NOTIFICATION_RQ_TOOL = Tool(
    name="order_notification_rq",
    description="""
    Create notifications for reservations to specific systems or users.
    
    This tool creates notifications about reservations that need to be sent to
    specific destination systems or users. It's used for alerting stakeholders
    about new bookings, changes, or other important events.
    
    Parameters:
    - order_ids (required): List of order IDs to create notifications for
    - destination_system (optional): Specific system to notify
    - destination_user (optional): Specific user to notify
    - language (optional): Language for the request
    
    Returns:
    - Confirmation of notification creation
    - Destination details
    - Notification status
    
    Example usage:
    "Create notification for order ORD123456"
    "Notify user admin about reservation ORD789012"
    "Send notification to system PMS for order ORD555777"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of order IDs to create notifications for",
                "items": {
                    "type": "string",
                    "description": "Order identifier (e.g., 'ORD123456')"
                },
                "minItems": 1,
                "maxItems": 100
            },
            "destination_system": {
                "type": "string",
                "description": "Specific system to notify",
                "maxLength": 100
            },
            "destination_user": {
                "type": "string",
                "description": "Specific user to notify",
                "maxLength": 100
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


class OrderNotificationRQHandler:
    """Handler for the OrderNotificationRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_notification_rq")
    
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
        """Execute the order notification creation request.
        
        Args:
            arguments: Tool arguments containing notification details
            
        Returns:
            Dictionary containing the notification results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            order_ids = arguments.get("order_ids", [])
            destination_system = arguments.get("destination_system", "").strip()
            destination_user = arguments.get("destination_user", "").strip()
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_order_ids = self._validate_order_ids(order_ids)
            
            sanitized_destination_system = ""
            if destination_system:
                sanitized_destination_system = sanitize_string(destination_system)
                if len(sanitized_destination_system) > 100:
                    raise ValidationError("Destination system must not exceed 100 characters")
            
            sanitized_destination_user = ""
            if destination_user:
                sanitized_destination_user = sanitize_string(destination_user)
                if len(sanitized_destination_user) > 100:
                    raise ValidationError("Destination user must not exceed 100 characters")
            
            self.logger.info(
                "Creating order notifications",
                order_count=len(validated_order_ids),
                has_destination_system=bool(sanitized_destination_system),
                has_destination_user=bool(sanitized_destination_user),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderId": validated_order_ids
            }
            
            # Add optional destination parameters
            if sanitized_destination_system:
                request_payload["DestinationSystem"] = sanitized_destination_system
            if sanitized_destination_user:
                request_payload["DestinationUser"] = sanitized_destination_user
            
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
                
                # Make the order notification request
                response = await client.post("/OrderNotificationRQ", request_payload)
            
            # Extract results from response
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Order notifications created successfully",
                order_count=len(validated_order_ids),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "notified_order_ids": validated_order_ids,
                "destination_system": sanitized_destination_system,
                "destination_user": sanitized_destination_user,
                "notification_summary": {
                    "total_orders": len(validated_order_ids),
                    "has_specific_system": bool(sanitized_destination_system),
                    "has_specific_user": bool(sanitized_destination_user),
                    "notification_type": "broadcast" if not (sanitized_destination_system or sanitized_destination_user) else "targeted"
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Successfully created notifications for {len(validated_order_ids)} order(s)"
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
handler = OrderNotificationRQHandler()


async def call_order_notification_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderNotificationRQ endpoint.
    
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
            summary = data["notification_summary"]
            
            response_text = f"""📢 **Order Notification Creation Successful**

📋 **Notification Summary:**
- **Orders Notified**: {summary['total_orders']}
- **Notification Type**: {summary['notification_type'].title()}
- **Target System**: {data['destination_system'] if data['destination_system'] else 'All systems'}
- **Target User**: {data['destination_user'] if data['destination_user'] else 'All users'}

🔗 **Notified Orders:**
"""
            
            for order_id in data["notified_order_ids"]:
                response_text += f"- **{order_id}**: ✅ NOTIFIED\n"
            
            response_text += f"""
🎯 **Notification Details:**
"""
            
            if data['destination_system']:
                response_text += f"- **Destination System**: {data['destination_system']}\n"
            else:
                response_text += "- **Destination System**: All connected systems\n"
            
            if data['destination_user']:
                response_text += f"- **Destination User**: {data['destination_user']}\n"
            else:
                response_text += "- **Destination User**: All authorized users\n"
            
            if summary['notification_type'] == 'broadcast':
                response_text += """
📡 **Broadcast Notification:**
- Notification sent to all connected systems and users
- Default notification behavior
- Maximum reach and visibility
"""
            else:
                response_text += """
🎯 **Targeted Notification:**
- Notification sent to specific destination
- Focused communication
- Reduces notification noise
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Notification Usage:**
- Alerts stakeholders about new reservations
- Notifies systems about booking changes
- Triggers automated workflows
- Facilitates real-time communication
- Supports operational coordination

📊 **Best Practices:**
- Use targeted notifications for specific workflows
- Use broadcast notifications for general alerts
- Monitor notification delivery and response
- Avoid excessive notifications to prevent fatigue
- Ensure proper notification routing and handling
"""
                
        else:
            response_text = f"""❌ **Order Notification Creation Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check that orders are confirmed and accessible
- Ensure destination system/user names are valid
- Verify authentication credentials
- Check notification system availability
- Ensure proper permissions for notification creation
- Review API response for specific error codes
- Contact support if the issue persists

📝 **Common Issues:**
- Invalid destination system or user names
- Orders not in notifiable state
- Network connectivity issues
- Notification service unavailable
- Insufficient permissions for target destination
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while creating order notifications:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
