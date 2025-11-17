"""
OrderPaymentCreateRQ - Order Payment Create Tool

This tool creates payment records for reservations in the Neobookings system.
"""

import json
from typing import Dict, Any, List, Optional
from mcp.types import Tool
from mcp.types import TextContent, ImageContent, EmbeddedResource
import structlog
from datetime import datetime

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
ORDER_PAYMENT_CREATE_RQ_TOOL = Tool(
    name="order_payment_create_rq",
    description="""
    Create payment records for reservations in the Neobookings system.
    
    This tool allows creating payment entries for existing reservations, supporting
    various payment methods and providing detailed payment tracking capabilities.
    
    Parameters:
    - order_id (required): Order ID to create payment for
    - payment_method (required): Payment method used
    - amount (required): Payment amount
    - currency (required): Payment currency
    - description (required): Payment description
    - payment_date (optional): Date when payment was made
    - removed (optional): Whether payment is marked as removed
    - tpv_token (optional): TPV token information for card payments
    - language (optional): Language for the request
    
    Returns:
    - Created payment details
    - Payment confirmation
    - TPV token information if applicable
    
    Example usage:
    "Create payment of 150.00 EUR for order ORD123456 via credit card"
    "Add cash payment of 75.50 USD for reservation ORD789012"
    "Register TPV payment for order ORD555777 with token information"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Order identifier for payment creation",
                "minLength": 1,
                "maxLength": 50
            },
            "payment_method": {
                "type": "string",
                "description": "Payment method used",
                "enum": [
                    "tpv", "tpvmanual", "card", "credit", "transference",
                    "moneyorder", "paypal", "cash", "financed", "otb", "other", "nil"
                ]
            },
            "amount": {
                "type": "number",
                "description": "Payment amount",
                "minimum": 0,
                "maximum": 999999.99
            },
            "currency": {
                "type": "string",
                "description": "Payment currency (ISO 4217 code)",
                "pattern": "^[A-Z]{3}$",
                "maxLength": 3
            },
            "description": {
                "type": "string",
                "description": "Payment description",
                "minLength": 1,
                "maxLength": 500
            },
            "payment_date": {
                "type": "string",
                "description": "Date when payment was made (YYYY-MM-DDTHH:MM:SS format)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}$"
            },
            "removed": {
                "type": "boolean",
                "description": "Whether payment is marked as removed",
                "default": False
            },
            "tpv_token": {
                "type": "object",
                "description": "TPV token information for card payments",
                "properties": {
                    "tpv_system": {
                        "type": "string",
                        "enum": [
                            "paytpv", "addonpayments", "conexflow", "redsys",
                            "paylands", "stripe", "openpay", "placetopay",
                            "adyen", "payu", "wompi", "unknown"
                        ]
                    },
                    "payer_token": {
                        "type": "string",
                        "maxLength": 200
                    },
                    "operation_token": {
                        "type": "string",
                        "maxLength": 200
                    },
                    "operation_schema": {
                        "type": "string",
                        "maxLength": 200
                    },
                    "pan": {
                        "type": "string",
                        "maxLength": 20
                    }
                }
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["order_id", "payment_method", "amount", "currency", "description"],
        "additionalProperties": False
    }
)


class OrderPaymentCreateRQHandler:
    """Handler for the OrderPaymentCreateRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_payment_create_rq")
    
    def _validate_payment_data(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize payment data."""
        # Validate order ID
        order_id = arguments.get("order_id", "").strip()
        if not order_id:
            raise ValidationError("Order ID is required")
        
        sanitized_order_id = sanitize_string(order_id, max_length=50)
        
        # Validate payment method
        payment_method = arguments.get("payment_method")
        if not payment_method:
            raise ValidationError("Payment method is required")
        
        # Validate amount
        amount = arguments.get("amount")
        if amount is None or amount < 0:
            raise ValidationError("Amount must be a positive number")
        if amount > 999999.99:
            raise ValidationError("Amount exceeds maximum allowed value")
        
        # Validate currency
        currency = arguments.get("currency", "").strip().upper()
        if not currency or len(currency) != 3:
            raise ValidationError("Currency must be a valid 3-letter ISO code")
        
        # Validate description
        description = arguments.get("description", "").strip()
        if not description:
            raise ValidationError("Payment description is required")
        
        sanitized_description = sanitize_string(description, max_length=500)
        
        # Validate payment date
        payment_date = arguments.get("payment_date")
        if payment_date:
            try:
                datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationError("Invalid payment date format. Use YYYY-MM-DDTHH:MM:SS")
        else:
            payment_date = datetime.utcnow().isoformat() + "Z"
        
        return {
            "order_id": sanitized_order_id,
            "payment_method": payment_method,
            "amount": round(amount, 2),
            "currency": currency,
            "description": sanitized_description,
            "payment_date": payment_date,
            "removed": arguments.get("removed", False)
        }
    
    def _build_tpv_token(self, tpv_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build TPV token structure if provided."""
        if not tpv_data:
            return None
        
        token_data = {}
        
        # Validate TPV system
        tpv_system = tpv_data.get("tpv_system")
        if tpv_system:
            token_data["Tpv"] = tpv_system
        
        # Build NeoToken structure
        neo_token = {}
        if tpv_data.get("payer_token"):
            neo_token["PayerToken"] = sanitize_string(tpv_data["payer_token"], max_length=200)
        if tpv_data.get("operation_token"):
            neo_token["OperationToken"] = sanitize_string(tpv_data["operation_token"], max_length=200)
        if tpv_data.get("operation_schema"):
            neo_token["OperationSchema"] = sanitize_string(tpv_data["operation_schema"], max_length=200)
        if tpv_data.get("pan"):
            neo_token["Pan"] = sanitize_string(tpv_data["pan"], max_length=20)
        
        if neo_token:
            token_data["NeoToken"] = neo_token
        
        return token_data if token_data else None
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order payment creation request.
        
        Args:
            arguments: Tool arguments containing payment details
            
        Returns:
            Dictionary containing the payment creation results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            validated_data = self._validate_payment_data(arguments)
            tpv_token_data = self._build_tpv_token(arguments.get("tpv_token"))
            language = arguments.get("language", "es")
            
            self.logger.info(
                "Creating payment for order",
                order_id=validated_data["order_id"],
                payment_method=validated_data["payment_method"],
                amount=validated_data["amount"],
                currency=validated_data["currency"],
                has_tpv_token=bool(tpv_token_data),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderId": validated_data["order_id"],
                "Payment": {
                    "DateCreated": validated_data["payment_date"],
                    "Method": validated_data["payment_method"],
                    "Quantity": validated_data["amount"],
                    "Currency": validated_data["currency"],
                    "Description": validated_data["description"],
                    "Removed": validated_data["removed"]
                }
            }
            
            # Add TPV token if provided
            if tpv_token_data:
                request_payload["TokenTpv"] = tpv_token_data
            
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
                
                # Make the payment creation request
                response = await client.post("/OrderPaymentCreateRQ", request_payload)
            
            # Extract response data
            created_payment = response.get("Payment", {})
            created_token = response.get("TokenTpv", {})
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Payment creation completed successfully",
                order_id=validated_data["order_id"],
                payment_created=bool(created_payment),
                token_created=bool(created_token),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "order_id": validated_data["order_id"],
                "created_payment": created_payment,
                "created_token": created_token,
                "payment_summary": {
                    "method": validated_data["payment_method"],
                    "amount": validated_data["amount"],
                    "currency": validated_data["currency"],
                    "description": validated_data["description"],
                    "date": validated_data["payment_date"],
                    "removed": validated_data["removed"]
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            success_message = f"Successfully created payment for order {validated_data['order_id']}"
            
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
handler = OrderPaymentCreateRQHandler()


async def call_order_payment_create_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderPaymentCreateRQ endpoint.
    
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
            summary = data["payment_summary"]
            created_payment = data["created_payment"]
            created_token = data["created_token"]
            
            response_text = f"""✅ **Payment Created Successfully**

💳 **Payment Details:**
- **Order ID**: {data['order_id']}
- **Payment Method**: {summary['method']}
- **Amount**: {summary['amount']} {summary['currency']}
- **Description**: {summary['description']}
- **Date**: {summary['date']}
- **Status**: {'Removed' if summary['removed'] else 'Active'}

📋 **Created Payment Record:**
"""
            
            if created_payment:
                response_text += f"""
- **Date Created**: {created_payment.get('DateCreated', 'N/A')}
- **Method**: {created_payment.get('Method', 'N/A')}
- **Quantity**: {created_payment.get('Quantity', 'N/A')}
- **Currency**: {created_payment.get('Currency', 'N/A')}
- **Description**: {created_payment.get('Description', 'N/A')}
- **Removed**: {'Yes' if created_payment.get('Removed', False) else 'No'}
"""
            else:
                response_text += "- No detailed payment record returned\n"
            
            if created_token:
                response_text += f"""
🔐 **TPV Token Information:**
- **TPV System**: {created_token.get('Tpv', 'N/A')}
"""
                neo_token = created_token.get('NeoToken', {})
                if neo_token:
                    response_text += f"""- **Payer Token**: {neo_token.get('PayerToken', 'N/A')}
- **Operation Token**: {neo_token.get('OperationToken', 'N/A')}
- **Operation Schema**: {neo_token.get('OperationSchema', 'N/A')}
- **PAN**: {neo_token.get('Pan', 'N/A')}
"""
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Payment Information:**
- **Record Created**: Payment entry has been added to order
- **Tracking**: Payment can be tracked through order details
- **Method Types**: Supports various payment methods (card, cash, transfer, etc.)
- **Token Security**: TPV tokens provide secure payment processing
- **Audit Trail**: All payments are logged for accounting purposes

📝 **Next Steps:**
- Payment record is now associated with the order
- Order payment status may be updated automatically
- TPV tokens can be used for future payment operations
- Payment can be modified or reversed if needed
- Check order details to confirm payment integration
"""
            
        else:
            response_text = f"""❌ **Payment Creation Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify order ID exists and is valid
- Check payment method is supported
- Ensure amount is within valid range
- Verify currency code is correct (3-letter ISO)
- Check payment description is provided
- Validate TPV token format if provided
- Ensure authentication credentials are valid
- Check if order allows additional payments
- Review payment date format (YYYY-MM-DDTHH:MM:SS)
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while creating payment:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
