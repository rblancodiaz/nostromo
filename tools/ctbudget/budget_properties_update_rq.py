"""
BudgetPropertiesUpdateRQ - Update Budget Properties Tool

This tool handles updating properties of a budget in the Neobookings system.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
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
BUDGET_PROPERTIES_UPDATE_RQ_TOOL = Tool(
    name="budget_properties_update_rq",
    description="""
    Update properties of a budget in the Neobookings system.
    
    This tool allows modification of budget properties such as sent date,
    copied date, and other status-related information.
    
    Parameters:
    - budget_id (required): Budget identifier to update
    - sent_date (optional): Date when budget was sent (YYYY-MM-DDThh:mm:ss format)
    - copied_date (optional): Date when budget was copied (YYYY-MM-DDThh:mm:ss format)
    - clear_sent_date (optional): Clear the sent date (default: false)
    - clear_copied_date (optional): Clear the copied date (default: false)
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Updated budget properties
    - Modification confirmation
    - Updated metadata
    
    Example usage:
    "Mark budget 'BDG123' as sent today"
    "Update budget BDG456 copied date to 2024-01-15"
    "Clear the sent date for budget BDG789"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "budget_id": {
                "type": "string",
                "description": "Budget identifier to update"
            },
            "sent_date": {
                "type": "string",
                "description": "Date when budget was sent (YYYY-MM-DDThh:mm:ss format)",
                "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
            },
            "copied_date": {
                "type": "string", 
                "description": "Date when budget was copied (YYYY-MM-DDThh:mm:ss format)",
                "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
            },
            "clear_sent_date": {
                "type": "boolean",
                "description": "Clear the sent date",
                "default": False
            },
            "clear_copied_date": {
                "type": "boolean",
                "description": "Clear the copied date", 
                "default": False
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["budget_id"],
        "additionalProperties": False
    }
)


class BudgetPropertiesUpdateRQHandler:
    """Handler for the BudgetPropertiesUpdateRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="budget_properties_update_rq")
    
    def _validate_datetime_format(self, date_string: str, field_name: str) -> None:
        """Validate datetime format."""
        try:
            datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            raise ValidationError(
                f"Invalid datetime format for {field_name}. Expected format: YYYY-MM-DDThh:mm:ss"
            )
    
    def _format_budget_properties(self, budget_details: Dict[str, Any]) -> Dict[str, Any]:
        """Format budget properties for readable output."""
        return {
            "budget_id": budget_details.get("BudgetId"),
            "origin": budget_details.get("Origin"),
            "hotel_id": budget_details.get("HotelId"),
            "rate_name": budget_details.get("RateName"),
            "board_name": budget_details.get("BoardName"),
            "creation_user": budget_details.get("CreationUser"),
            "arrival_date": budget_details.get("ArrivalDate"),
            "departure_date": budget_details.get("DepartureDate"),
            "status": budget_details.get("Status"),
            "is_sent": budget_details.get("IsSent"),
            "sent_date": budget_details.get("SentDate"),
            "is_copied": budget_details.get("IsCopied"),
            "copied_date": budget_details.get("CopiedDate"),
            "creation_date": budget_details.get("CreationDate"),
            "customer_details": budget_details.get("CustomerDetail", {}),
            "amounts_detail": budget_details.get("AmountsDetail", {})
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the budget properties update request.
        
        Args:
            arguments: Tool arguments containing budget update parameters
            
        Returns:
            Dictionary containing the update results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            budget_id = arguments.get("budget_id")
            sent_date = arguments.get("sent_date")
            copied_date = arguments.get("copied_date")
            clear_sent_date = arguments.get("clear_sent_date", False)
            clear_copied_date = arguments.get("clear_copied_date", False)
            language = arguments.get("language", "es")
            
            # Validate budget ID
            if not budget_id or not isinstance(budget_id, str) or not budget_id.strip():
                raise ValidationError("Budget ID is required and must be a non-empty string")
            
            budget_id = sanitize_string(budget_id.strip())
            
            # Validate datetime formats if provided
            if sent_date:
                self._validate_datetime_format(sent_date, "sent_date")
            
            if copied_date:
                self._validate_datetime_format(copied_date, "copied_date")
            
            # Check for conflicting parameters
            if sent_date and clear_sent_date:
                raise ValidationError("Cannot set sent_date and clear_sent_date at the same time")
            
            if copied_date and clear_copied_date:
                raise ValidationError("Cannot set copied_date and clear_copied_date at the same time")
            
            # Check that at least one operation is specified
            if not any([sent_date, copied_date, clear_sent_date, clear_copied_date]):
                raise ValidationError("At least one property update must be specified")
            
            self.logger.info(
                "Updating budget properties",
                budget_id=budget_id,
                sent_date=sent_date,
                copied_date=copied_date,
                clear_sent_date=clear_sent_date,
                clear_copied_date=clear_copied_date,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload["BudgetId"] = budget_id
            
            # Add optional date updates
            if sent_date:
                request_payload["SentDate"] = sent_date
            if copied_date:
                request_payload["CopiedDate"] = copied_date
            if clear_sent_date:
                request_payload["ClearSentDate"] = True
            if clear_copied_date:
                request_payload["ClearCopiedDate"] = True
            
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
                
                # Make the budget properties update request
                response = await client.post("/BudgetPropertiesUpdateRQ", request_payload)
            
            # Extract updated budget details from response
            updated_budget_details = response.get("BudgetDetails", {})
            formatted_budget = self._format_budget_properties(updated_budget_details)
            
            # Log successful operation
            self.logger.info(
                "Budget properties updated successfully",
                budget_id=budget_id,
                updated_fields={
                    "sent_date": sent_date or ("CLEARED" if clear_sent_date else None),
                    "copied_date": copied_date or ("CLEARED" if clear_copied_date else None)
                },
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "budget_id": budget_id,
                "updated_budget": formatted_budget,
                "applied_updates": {
                    "sent_date": sent_date,
                    "copied_date": copied_date,
                    "cleared_sent_date": clear_sent_date,
                    "cleared_copied_date": clear_copied_date
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "operation_summary": {
                    "operation": "update",
                    "resource_type": "budget_properties",
                    "budget_id": budget_id,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Budget properties updated successfully for budget {budget_id}"
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
handler = BudgetPropertiesUpdateRQHandler()


async def call_budget_properties_update_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BudgetPropertiesUpdateRQ endpoint.
    
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
            updated_budget = data["updated_budget"]
            applied_updates = data["applied_updates"]
            operation_summary = data["operation_summary"]
            
            response_text = f"""✏️ **Budget Properties Updated**

✅ **Operation Summary:**
- **Operation**: {operation_summary['operation'].title()}
- **Resource**: {operation_summary['resource_type'].replace('_', ' ').title()}
- **Budget ID**: {operation_summary['budget_id']}
- **Language**: {operation_summary['language'].upper()}

🔄 **Applied Updates:**
"""
            
            # Show applied updates
            if applied_updates["sent_date"]:
                response_text += f"  ✓ **Sent Date**: Set to `{applied_updates['sent_date']}`\n"
            if applied_updates["copied_date"]:
                response_text += f"  ✓ **Copied Date**: Set to `{applied_updates['copied_date']}`\n"
            if applied_updates["cleared_sent_date"]:
                response_text += f"  ✓ **Sent Date**: Cleared\n"
            if applied_updates["cleared_copied_date"]:
                response_text += f"  ✓ **Copied Date**: Cleared\n"
            
            response_text += f"""
📊 **Updated Budget Information:**
- **Budget ID**: {updated_budget.get('budget_id', 'N/A')}
- **Origin**: {updated_budget.get('origin', 'N/A')}
- **Hotel ID**: {updated_budget.get('hotel_id', 'N/A')}
- **Status**: {updated_budget.get('status', 'N/A')}
- **Rate Name**: {updated_budget.get('rate_name', 'N/A')}
- **Board Name**: {updated_budget.get('board_name', 'N/A')}

📅 **Current Dates:**
- **Creation**: {updated_budget.get('creation_date', 'N/A')}
- **Arrival**: {updated_budget.get('arrival_date', 'N/A')}
- **Departure**: {updated_budget.get('departure_date', 'N/A')}

📧 **Status Information:**
- **Is Sent**: {'Yes' if updated_budget.get('is_sent') else 'No'}
- **Sent Date**: {updated_budget.get('sent_date', 'Not set')}
- **Is Copied**: {'Yes' if updated_budget.get('is_copied') else 'No'}
- **Copied Date**: {updated_budget.get('copied_date', 'Not set')}
"""
            
            # Add customer information if available
            customer = updated_budget.get('customer_details', {})
            if customer and any(customer.values()):
                response_text += f"""
👤 **Customer Information:**
- **Name**: {customer.get('Name', '')} {customer.get('Surname', '')}
- **Email**: {customer.get('Email', 'N/A')}
- **Phone**: {customer.get('Phone', 'N/A')}
"""
            
            # Add amounts information if available
            amounts = updated_budget.get('amounts_detail', {})
            if amounts and any(amounts.values()):
                response_text += f"""
💰 **Amount Details:**
- **Currency**: {amounts.get('Currency', 'N/A')}
- **Final Amount**: {amounts.get('AmountFinal', 'N/A')}
- **Total Amount**: {amounts.get('AmountTotal', 'N/A')}
"""
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Budget Properties Update Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the budget ID exists and is accessible
- Check the datetime format (YYYY-MM-DDThh:mm:ss)
- Ensure you have permission to modify this budget
- Verify your authentication credentials
- Check for conflicting update parameters
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while updating budget properties:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
