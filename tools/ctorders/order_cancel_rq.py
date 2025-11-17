"""
OrderCancelRQ - Order Cancellation Tool

This tool cancels one or more confirmed reservations in the Neobookings system.
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
ORDER_CANCEL_RQ_TOOL = Tool(
    name="order_cancel_rq",
    description="""
    Cancel one or more confirmed reservations in the Neobookings system.
    
    This tool allows cancelling existing reservations by providing the order IDs
    and a cancellation reason. The tool can cancel multiple orders in a single request
    and provides control over email notifications to clients and establishments.
    
    Parameters:
    - order_ids (required): List of order IDs to cancel
    - reason (required): Reason for cancellation
    - avoid_send_client_email (optional): Prevent sending email to client
    - avoid_send_establishment_email (optional): Prevent sending email to establishment
    - language (optional): Language for the request
    
    Returns:
    - List of successfully cancelled order IDs
    - Cancellation confirmation details
    - Email notification status
    
    Example usage:
    "Cancel reservation ORD123456 due to customer request"
    "Cancel orders ORD123456 and ORD789012 because of overbooking"
    "Cancel reservation ORD555777 without sending emails"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of order IDs to cancel",
                "items": {
                    "type": "string",
                    "description": "Order identifier (e.g., 'ORD123456')"
                },
                "minItems": 1,
                "maxItems": 100
            },
            "reason": {
                "type": "string",
                "description": "Reason for the cancellation",
                "minLength": 1,
                "maxLength": 500
            },
            "avoid_send_client_email": {
                "type": "boolean",
                "description": "If true, prevents sending cancellation email to the client",
                "default": False
            },
            "avoid_send_establishment_email": {
                "type": "boolean",
                "description": "If true, prevents sending cancellation email to the establishment",
                "default": False
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["order_ids", "reason"],
        "additionalProperties": False
    }
)


class OrderCancelRQHandler:
    """Handler for the OrderCancelRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_cancel_rq")
    
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
        """Execute the order cancellation request.
        
        Args:
            arguments: Tool arguments containing cancellation details
            
        Returns:
            Dictionary containing the cancellation results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            order_ids = arguments.get("order_ids", [])
            reason = arguments.get("reason", "").strip()
            avoid_send_client_email = arguments.get("avoid_send_client_email", False)
            avoid_send_establishment_email = arguments.get("avoid_send_establishment_email", False)
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_order_ids = self._validate_order_ids(order_ids)
            
            if not reason:
                raise ValidationError("Cancellation reason is required")
            if len(reason) > 500:
                raise ValidationError("Cancellation reason must not exceed 500 characters")
            
            sanitized_reason = sanitize_string(reason)
            if not sanitized_reason:
                raise ValidationError("Invalid cancellation reason after sanitization")
            
            self.logger.info(
                "Initiating order cancellation",
                order_count=len(validated_order_ids),
                reason_length=len(sanitized_reason),
                avoid_client_email=avoid_send_client_email,
                avoid_establishment_email=avoid_send_establishment_email,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderId": validated_order_ids,
                "Reason": sanitized_reason
            }
            
            # Add optional email settings
            if avoid_send_client_email:
                request_payload["AvoidSendClientEmail"] = True
            if avoid_send_establishment_email:
                request_payload["AvoidSendEstablishmentEmail"] = True
            
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
                
                # Make the order cancellation request
                response = await client.post("/OrderCancelRQ", request_payload)
            
            # Extract cancellation results from response
            cancelled_orders = response.get("OrdersCancelled", [])
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Order cancellation completed successfully",
                requested_orders=len(validated_order_ids),
                cancelled_orders=len(cancelled_orders),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "requested_order_ids": validated_order_ids,
                "cancelled_order_ids": cancelled_orders,
                "cancellation_reason": sanitized_reason,
                "email_settings": {
                    "client_email_avoided": avoid_send_client_email,
                    "establishment_email_avoided": avoid_send_establishment_email
                },
                "cancellation_summary": {
                    "total_requested": len(validated_order_ids),
                    "total_cancelled": len(cancelled_orders),
                    "success_rate": len(cancelled_orders) / len(validated_order_ids) * 100 if validated_order_ids else 0
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            # Determine success status
            all_cancelled = len(cancelled_orders) == len(validated_order_ids)
            success_message = f"Successfully cancelled {len(cancelled_orders)} of {len(validated_order_ids)} order(s)"
            
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
handler = OrderCancelRQHandler()


async def call_order_cancel_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderCancelRQ endpoint.
    
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
            summary = data["cancellation_summary"]
            email_settings = data["email_settings"]
            
            response_text = f"""✅ **Order Cancellation Completed**

📋 **Cancellation Summary:**
- **Total Orders Requested**: {summary['total_requested']}
- **Successfully Cancelled**: {summary['total_cancelled']}
- **Success Rate**: {summary['success_rate']:.1f}%
- **Cancellation Reason**: {data['cancellation_reason']}

🔗 **Processed Orders:**
"""
            
            # List requested orders
            for order_id in data["requested_order_ids"]:
                status = "✅ CANCELLED" if order_id in data["cancelled_order_ids"] else "❌ NOT CANCELLED"
                response_text += f"- **{order_id}**: {status}\n"
            
            response_text += f"""
📧 **Email Notification Settings:**
- **Client Email**: {'Avoided' if email_settings['client_email_avoided'] else 'Sent'}
- **Establishment Email**: {'Avoided' if email_settings['establishment_email_avoided'] else 'Sent'}

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Important Notes:**
- Cancelled orders cannot be reactivated
- Cancellation policies may apply based on timing
- Email notifications inform relevant parties
- Refund processing may be initiated separately
- Contact support for any cancellation issues
"""
            
            if summary['total_cancelled'] < summary['total_requested']:
                failed_orders = [oid for oid in data["requested_order_ids"] if oid not in data["cancelled_order_ids"]]
                response_text += f"""
⚠️ **Partially Successful Cancellation:**
The following orders could not be cancelled:
{chr(10).join(f"- {order_id}" for order_id in failed_orders)}

**Possible reasons:**
- Order already cancelled
- Order not found
- Cancellation deadline passed
- System restrictions
- Invalid order status
"""
                
        else:
            response_text = f"""❌ **Order Cancellation Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check order status (only confirmed orders can be cancelled)
- Ensure cancellation reason is provided
- Verify authentication credentials
- Check if cancellation deadline has passed
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while cancelling orders:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
