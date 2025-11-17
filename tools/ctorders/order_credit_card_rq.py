"""
OrderCreditCardRQ - Order Credit Card Information Tool

This tool retrieves credit card information associated with confirmed reservations.
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
ORDER_CREDIT_CARD_RQ_TOOL = Tool(
    name="order_credit_card_rq",
    description="""
    Retrieve credit card information associated with confirmed reservations.
    
    This tool retrieves masked credit card details for one or more orders,
    including card type, masked number, expiration date, and holder information.
    This is useful for verification and payment management purposes.
    
    Parameters:
    - order_ids (required): List of order IDs to retrieve credit card information for
    - language (optional): Language for the request
    
    Returns:
    - Credit card information for each order
    - Card type, masked number, and expiration details
    - Card holder information
    
    Example usage:
    "Get credit card information for order ORD123456"
    "Retrieve payment details for orders ORD123456 and ORD789012"
    "Show card information for reservation ORD555777"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "description": "List of order IDs to retrieve credit card information for",
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


class OrderCreditCardRQHandler:
    """Handler for the OrderCreditCardRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_credit_card_rq")
    
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
    
    def _format_credit_card_info(self, card_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format credit card information for display."""
        formatted_cards = []
        
        for card in card_info:
            formatted_card = {
                "order_id": card.get("OrderId"),
                "card_type": card.get("CreditCardType"),
                "card_number": card.get("CreditCardNumber"),  # Already masked by API
                "expiration_month": card.get("ExpirateDateMonth"),
                "expiration_year": card.get("ExpirateDateYear"),
                "card_code": card.get("CreditCardCode"),  # Usually masked
                "card_holder": card.get("CreditCardHolder")
            }
            
            # Format card type for display
            card_type_map = {
                "visa": "Visa",
                "mastercard": "MasterCard",
                "americanexpress": "American Express",
                "dinersclub": "Diners Club",
                "discover": "Discover",
                "jcb": "JCB",
                "unknown": "Unknown"
            }
            
            formatted_card["card_type_display"] = card_type_map.get(
                formatted_card["card_type"], 
                formatted_card["card_type"]
            )
            
            # Format expiration date
            if formatted_card["expiration_month"] and formatted_card["expiration_year"]:
                formatted_card["expiration_display"] = f"{formatted_card['expiration_month']:02d}/{formatted_card['expiration_year']}"
            else:
                formatted_card["expiration_display"] = "N/A"
            
            formatted_cards.append(formatted_card)
        
        return formatted_cards
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order credit card information request.
        
        Args:
            arguments: Tool arguments containing order IDs
            
        Returns:
            Dictionary containing the credit card information
            
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
                "Retrieving credit card information",
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
                
                # Make the order credit card request
                response = await client.post("/OrderCreditCardRQ", request_payload)
            
            # Extract credit card information from response
            credit_cards = response.get("OrderCreditCard", [])
            api_response = response.get("Response", {})
            
            # Format credit card information
            formatted_cards = self._format_credit_card_info(credit_cards)
            
            # Log successful operation
            self.logger.info(
                "Credit card information retrieved successfully",
                requested_orders=len(validated_order_ids),
                cards_found=len(formatted_cards),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "requested_order_ids": validated_order_ids,
                "credit_cards": formatted_cards,
                "summary": {
                    "total_requested": len(validated_order_ids),
                    "cards_found": len(formatted_cards),
                    "cards_missing": len(validated_order_ids) - len(formatted_cards)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved credit card information for {len(formatted_cards)} of {len(validated_order_ids)} order(s)"
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
handler = OrderCreditCardRQHandler()


async def call_order_credit_card_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderCreditCardRQ endpoint.
    
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
            credit_cards = data["credit_cards"]
            
            response_text = f"""💳 **Order Credit Card Information**

📋 **Summary:**
- **Total Orders Requested**: {summary['total_requested']}
- **Cards Found**: {summary['cards_found']}
- **Orders Without Card Info**: {summary['cards_missing']}

"""
            
            if credit_cards:
                response_text += f"""💳 **Credit Card Details ({len(credit_cards)} found):**
{'='*80}
"""
                
                for i, card in enumerate(credit_cards, 1):
                    response_text += f"""
💳 **Card #{i} - Order {card['order_id']}**
{'-'*60}

🏦 **Card Information:**
- **Card Type**: {card['card_type_display']}
- **Card Number**: {card['card_number'] if card['card_number'] else 'N/A'}
- **Expiration**: {card['expiration_display']}
- **Card Holder**: {card['card_holder'] if card['card_holder'] else 'N/A'}
"""
                    
                    if card.get('card_code'):
                        response_text += f"- **Security Code**: {card['card_code']}\n"
                    
                    response_text += "\n"
            else:
                response_text += """❌ **No Credit Card Information Found**

None of the requested orders have associated credit card information.

**Possible reasons:**
- Orders were paid by other methods (cash, transfer, etc.)
- Credit card information was not stored
- Orders are in pending status
- Payment not yet processed
"""
            
            # Show orders without card information
            if summary['cards_missing'] > 0:
                orders_with_cards = {card['order_id'] for card in credit_cards}
                orders_without_cards = [oid for oid in data['requested_order_ids'] if oid not in orders_with_cards]
                
                response_text += f"""
ℹ️ **Orders Without Card Information ({len(orders_without_cards)}):**
"""
                for order_id in orders_without_cards:
                    response_text += f"- {order_id}\n"
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

🔒 **Security Notes:**
- Card numbers are masked for security
- Full details only accessible to authorized personnel
- Information used for verification purposes only
- Contact payment department for sensitive operations

💡 **Usage Tips:**
- Use for payment verification and troubleshooting
- Check card expiration dates for renewal needs
- Verify card holder names for billing accuracy
- Contact support for payment processing issues
"""
                
        else:
            response_text = f"""❌ **Credit Card Information Retrieval Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order IDs are correct and exist
- Check that orders have confirmed status
- Ensure orders were paid by credit card
- Verify authentication credentials
- Check user permissions for payment data access
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving credit card information:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
