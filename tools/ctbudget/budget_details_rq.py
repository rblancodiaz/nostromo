"""
BudgetDetailsRQ - Get Budget Details Tool

This tool retrieves detailed information about one or more budgets in the Neobookings system.
"""

import json
from typing import Dict, Any, List
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
BUDGET_DETAILS_RQ_TOOL = Tool(
    name="budget_details_rq",
    description="""
    Retrieve detailed information about one or more budgets from the Neobookings system.
    
    This tool provides comprehensive budget information including customer details,
    basket contents, billing information, amounts, and status.
    
    Parameters:
    - budget_ids (required): List of budget identifiers to retrieve details for
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Complete budget details including customer and basket information
    - Amounts and pricing breakdown
    - Status and metadata
    - Creation and modification dates
    
    Example usage:
    "Get details for budget 'BDG123'"
    "Show me information about budgets 'BDG123' and 'BDG456'"
    "Retrieve budget details for BDG789"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "budget_ids": {
                "type": "array",
                "description": "List of budget identifiers to retrieve details for",
                "items": {
                    "type": "string",
                    "description": "Budget identifier"
                },
                "minItems": 1,
                "maxItems": 20
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["budget_ids"],
        "additionalProperties": False
    }
)


class BudgetDetailsRQHandler:
    """Handler for the BudgetDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="budget_details_rq")
    
    def _format_budget_details(self, budget_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format budget details for readable output."""
        formatted = {
            "id": budget_detail.get("Id"),
            "hotel_id": budget_detail.get("HotelId"),
            "creation_user": budget_detail.get("CreationUser"),
            "language": budget_detail.get("BudgetLang"),
            "status": budget_detail.get("Status"),
            "creation_date": budget_detail.get("CreationDate"),
            "last_update": budget_detail.get("LastUpdate"),
            "is_sent": budget_detail.get("IsSent", False),
            "sent_date": budget_detail.get("sentDate"),
            "is_copied": budget_detail.get("IsCopied", False),
            "copied_date": budget_detail.get("CopiedDate")
        }
        
        # Format customer details
        customer = budget_detail.get("CustomerDetail", {})
        if customer:
            formatted["customer"] = {
                "name": customer.get("Name"),
                "surname": customer.get("Surname"),
                "email": customer.get("Email"),
                "phone": customer.get("Phone"),
                "passport": customer.get("Passport"),
                "country": customer.get("Country"),
                "state": customer.get("State"),
                "city": customer.get("City"),
                "zip": customer.get("Zip"),
                "address": customer.get("Address"),
                "comments": customer.get("Comments"),
                "ads_authorization": customer.get("AdsAuthorization"),
                "loyalty_authorization": customer.get("LoyaltyAuthorization")
            }
        
        # Format basket details
        basket = budget_detail.get("BasketDetail", {})
        if basket:
            formatted["basket"] = {
                "origin": basket.get("Origin"),
                "rewards": basket.get("Rewards"),
                "allow_deposit": basket.get("AllowDeposit"),
                "allow_full_payment": basket.get("AllowFullPayment"),
                "allow_installments": basket.get("AllowInstallments"),
                "allow_establishment": basket.get("AllowEstablishment")
            }
            
            # Format amounts
            amounts = basket.get("AmountsDetail", {})
            if amounts:
                formatted["basket"]["amounts"] = {
                    "currency": amounts.get("Currency"),
                    "final": amounts.get("AmountFinal"),
                    "total": amounts.get("AmountTotal"),
                    "base": amounts.get("AmountBase"),
                    "taxes": amounts.get("AmountTaxes"),
                    "tourist_tax": amounts.get("AmountTouristTax"),
                    "before": amounts.get("AmountBefore"),
                    "offers": amounts.get("AmountOffers"),
                    "discounts": amounts.get("AmountDiscounts"),
                    "extras": amounts.get("AmountExtras"),
                    "deposit": amounts.get("AmountDeposit"),
                    "paid": amounts.get("AmountPaid"),
                    "loyalty": amounts.get("AmountLoyalty")
                }
        
        # Format billing details
        billing = budget_detail.get("BillingDetails", {})
        if billing:
            formatted["billing"] = {
                "name": billing.get("Name"),
                "cif": billing.get("Cif"),
                "address": billing.get("Address"),
                "zip": billing.get("Zip"),
                "city": billing.get("City"),
                "country": billing.get("Country")
            }
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the budget details request.
        
        Args:
            arguments: Tool arguments containing budget IDs
            
        Returns:
            Dictionary containing the budget details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            budget_ids = arguments.get("budget_ids", [])
            language = arguments.get("language", "es")
            
            # Validate budget IDs
            if not budget_ids:
                raise ValidationError("At least one budget ID is required")
            
            if not isinstance(budget_ids, list):
                raise ValidationError("budget_ids must be a list")
            
            # Sanitize budget IDs
            sanitized_budget_ids = []
            for budget_id in budget_ids:
                if not isinstance(budget_id, str) or not budget_id.strip():
                    raise ValidationError(f"Invalid budget ID: {budget_id}")
                sanitized_budget_ids.append(sanitize_string(budget_id.strip()))
            
            self.logger.info(
                "Retrieving budget details",
                budget_count=len(sanitized_budget_ids),
                budget_ids=sanitized_budget_ids,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload["BudgetId"] = sanitized_budget_ids
            
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
                
                # Make the budget details request
                response = await client.post("/BudgetDetailsRQ", request_payload)
            
            # Extract budget details from response
            budget_details_raw = response.get("BudgetDetails", [])
            
            # Format budget details
            formatted_budgets = []
            for budget_detail in budget_details_raw:
                formatted_budgets.append(self._format_budget_details(budget_detail))
            
            # Log successful operation
            self.logger.info(
                "Budget details retrieved successfully",
                budget_count=len(formatted_budgets),
                found_budgets=len(budget_details_raw),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "budget_details": formatted_budgets,
                "requested_budget_ids": sanitized_budget_ids,
                "found_count": len(formatted_budgets),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "query_summary": {
                    "requested_count": len(sanitized_budget_ids),
                    "found_count": len(formatted_budgets),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {len(formatted_budgets)} budget(s)"
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
handler = BudgetDetailsRQHandler()


async def call_budget_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BudgetDetailsRQ endpoint.
    
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
            query_summary = data["query_summary"]
            
            response_text = f"""📋 **Budget Details Retrieved**

✅ **Query Summary:**
- **Requested**: {query_summary['requested_count']} budget(s)
- **Found**: {query_summary['found_count']} budget(s)
- **Language**: {query_summary['language'].upper()}

"""
            
            # Display details for each budget
            for i, budget in enumerate(data["budget_details"], 1):
                response_text += f"""
{'='*50}
📊 **Budget #{i}: {budget.get('id', 'Unknown ID')}**
{'='*50}

🏨 **Basic Information:**
- **Budget ID**: {budget.get('id', 'N/A')}
- **Hotel ID**: {budget.get('hotel_id', 'N/A')}
- **Status**: {budget.get('status', 'N/A')}
- **Language**: {budget.get('language', 'N/A')}
- **Created By**: {budget.get('creation_user', 'N/A')}

📅 **Dates:**
- **Created**: {budget.get('creation_date', 'N/A')}
- **Last Updated**: {budget.get('last_update', 'N/A')}
- **Sent**: {'Yes' if budget.get('is_sent') else 'No'} ({budget.get('sent_date', 'N/A')})
- **Copied**: {'Yes' if budget.get('is_copied') else 'No'} ({budget.get('copied_date', 'N/A')})
"""
                
                # Customer information
                customer = budget.get('customer', {})
                if customer and any(customer.values()):
                    response_text += f"""
👤 **Customer Information:**
- **Name**: {customer.get('name', '')} {customer.get('surname', '')}
- **Email**: {customer.get('email', 'N/A')}
- **Phone**: {customer.get('phone', 'N/A')}
- **Country**: {customer.get('country', 'N/A')}
- **City**: {customer.get('city', 'N/A')}
- **Address**: {customer.get('address', 'N/A')}
"""
                    if customer.get('ads_authorization') is not None:
                        response_text += f"- **Ads Authorization**: {'Yes' if customer.get('ads_authorization') else 'No'}\n"
                    if customer.get('loyalty_authorization') is not None:
                        response_text += f"- **Loyalty Authorization**: {'Yes' if customer.get('loyalty_authorization') else 'No'}\n"
                
                # Basket information
                basket = budget.get('basket', {})
                if basket and any(v for k, v in basket.items() if k != 'amounts'):
                    response_text += f"""
🛒 **Basket Information:**
- **Origin**: {basket.get('origin', 'N/A')}
- **Rewards**: {'Yes' if basket.get('rewards') else 'No'}
- **Allow Deposit**: {'Yes' if basket.get('allow_deposit') else 'No'}
- **Allow Full Payment**: {'Yes' if basket.get('allow_full_payment') else 'No'}
- **Allow Installments**: {'Yes' if basket.get('allow_installments') else 'No'}
- **Allow Establishment Payment**: {'Yes' if basket.get('allow_establishment') else 'No'}
"""
                
                # Amounts information
                amounts = basket.get('amounts', {}) if basket else {}
                if amounts and any(amounts.values()):
                    response_text += f"""
💰 **Pricing Details:**
- **Currency**: {amounts.get('currency', 'N/A')}
- **Final Amount**: {amounts.get('final', 'N/A')}
- **Total Amount**: {amounts.get('total', 'N/A')}
- **Base Amount**: {amounts.get('base', 'N/A')}
- **Taxes**: {amounts.get('taxes', 'N/A')}
- **Tourist Tax**: {amounts.get('tourist_tax', 'N/A')}
- **Offers**: {amounts.get('offers', 'N/A')}
- **Discounts**: {amounts.get('discounts', 'N/A')}
- **Extras**: {amounts.get('extras', 'N/A')}
- **Deposit**: {amounts.get('deposit', 'N/A')}
"""
                
                # Billing information
                billing = budget.get('billing', {})
                if billing and any(billing.values()):
                    response_text += f"""
🧾 **Billing Information:**
- **Name**: {billing.get('name', 'N/A')}
- **CIF**: {billing.get('cif', 'N/A')}
- **Address**: {billing.get('address', 'N/A')}
- **City**: {billing.get('city', 'N/A')}
- **Country**: {billing.get('country', 'N/A')}
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Budget Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the budget IDs exist and are accessible
- Check your authentication credentials
- Ensure you have permission to view these budgets
- Verify the budget IDs format is correct
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving budget details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
