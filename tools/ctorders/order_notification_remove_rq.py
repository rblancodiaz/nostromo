"""
OrderNotificationRemoveRQ - Order Notification Remove Tool

This tool removes notifications for one or more reservations in the Neobookings system.
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
ORDER_NOTIFICATION_REMOVE_RQ_TOOL = Tool(
    name="order_notification_remove_rq",
    description="""
    Remove notifications for one or more reservations in the Neobookings system.
    
    This tool allows removing pending notifications for existing reservations by providing
    the order IDs. It can target specific systems or users for notification removal.
    
    Parameters:
    - order_ids (required): List of order IDs to remove notifications
    - destination_system (optional): Specific system to remove notification from
    - destination_user (optional): Specific user to remove notification from
    - language (optional): Language for the request
    
    Returns:
    - Confirmation of notification removal
    - Details of processed orders
    - System and user notification removal status
    
    Example usage:
    "Remove notifications for order ORD123456"
    "Clear notifications for orders ORD123456 and ORD789012"
    "Remove notifications for order ORD555777 from specific system"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of order IDs to remove notifications",
                "items": {
                    "type": "string",
                    "description": "Order identifier (e.g., 'ORD123456')"
                },
                "minItems": 1,
                "maxItems": 100
            },
            "destination_system": {
                "type": "string",
                "description": "Specific system to remove notification from",
                "maxLength": 100
            },
            "destination_user": {
                "type": "string",
                "description": "Specific user to remove notification from",
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


class OrderNotificationRemoveRQHandler:
    """Handler for the OrderNotificationRemoveRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_notification_remove_rq")
    
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
        """Execute the order notification remove request.
        
        Args:
            arguments: Tool arguments containing removal details
            
        Returns:
            Dictionary containing the notification removal results
            
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
            
            # Validate optional destination fields
            sanitized_system = ""
            sanitized_user = ""
            
            if destination_system:
                sanitized_system = sanitize_string(destination_system, max_length=100)
            
            if destination_user:
                sanitized_user = sanitize_string(destination_user, max_length=100)
            
            self.logger.info(
                "Removing notifications for orders",
                order_count=len(validated_order_ids),
                destination_system=sanitized_system or "All systems",
                destination_user=sanitized_user or "All users",
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderId": validated_order_ids
            }
            
            # Add optional destination fields
            if sanitized_system:
                request_payload["DestinationSystem"] = sanitized_system
            if sanitized_user:
                request_payload["DestinationUser"] = sanitized_user
            
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
                
                # Make the notification removal request
                response = await client.post("/OrderNotificationRemoveRQ", request_payload)
            
            # Extract response data
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Notification removal completed successfully",
                processed_orders=len(validated_order_ids),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "processed_order_ids": validated_order_ids,
                "removal_scope": {
                    "destination_system": sanitized_system or "All systems",
                    "destination_user": sanitized_user or "All users",
                    "specific_targeting": bool(sanitized_system or sanitized_user)
                },
                "removal_summary": {
                    "total_orders": len(validated_order_ids),
                    "removal_type": "Targeted" if (sanitized_system or sanitized_user) else "Global"
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            success_message = f"Successfully removed notifications for {len(validated_order_ids)} order(s)"
            
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
handler = OrderNotificationRemoveRQHandler()


async def call_order_notification_remove_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderNotificationRemoveRQ endpoint.
    
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
            summary = data["removal_summary"]
            scope = data["removal_scope"]
            
            response_text = f"""✅ **Order Notifications Removed Successfully**

🗑️ **Removal Summary:**
- **Total Orders Processed**: {summary['total_orders']}
- **Removal Type**: {summary['removal_type']}
- **Target System**: {scope['destination_system']}
- **Target User**: {scope['destination_user']}

📋 **Processed Orders:**
"""
            
            # List processed orders
            for order_id in data["processed_order_ids"]:
                response_text += f"- **{order_id}**: ✅ Notifications Removed\n"
            
            response_text += f"""
🎯 **Removal Scope:**
- **Specific Targeting**: {'Yes' if scope['specific_targeting'] else 'No (Global removal)'}
- **Affected Systems**: {scope['destination_system']}
- **Affected Users**: {scope['destination_user']}

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Important Notes:**
- **Global Removal**: When no specific system/user is targeted, notifications are removed from all systems
- **Targeted Removal**: When system/user is specified, only those specific notifications are removed
- **Irreversible Action**: Removed notifications cannot be restored
- **Queue Cleanup**: This helps clean up notification queues and reduce system load
- **Audit Trail**: Removal actions are logged for system auditing

⚠️ **Considerations:**
- Removed notifications will no longer appear in pending lists
- Staff may miss important updates if notifications are removed prematurely
- Consider the impact on workflow before removing notifications
- Use targeted removal when possible to avoid affecting other systems
"""
            
        else:
            response_text = f"""❌ **Order Notification Removal Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check if notifications exist for the specified orders
- Ensure authentication credentials are valid
- Verify system permissions for notification management
- Check if destination system/user names are correct
- Ensure orders are in a valid state for notification removal
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while removing notifications:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
