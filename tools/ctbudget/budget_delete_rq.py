"""
BudgetDeleteRQ - Delete Budget Tool

This tool handles the deletion of one or more budgets in the Neobookings system.
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
BUDGET_DELETE_RQ_TOOL = Tool(
    name="budget_delete_rq",
    description="""
    Delete one or more budgets from the Neobookings system.
    
    This tool allows deletion of existing budgets by their identifiers.
    Multiple budgets can be deleted in a single operation.
    
    Parameters:
    - budget_ids (required): List of budget identifiers to delete
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Confirmation of deletion operation
    - List of successfully deleted budget IDs
    - Deletion metadata
    
    Example usage:
    "Delete budget with ID 'BDG123'"
    "Remove budgets 'BDG123' and 'BDG456'"
    "Delete the budget BDG789 from the system"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "budget_ids": {
                "type": "array",
                "description": "List of budget identifiers to delete",
                "items": {
                    "type": "string",
                    "description": "Budget identifier"
                },
                "minItems": 1,
                "maxItems": 50
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


class BudgetDeleteRQHandler:
    """Handler for the BudgetDeleteRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="budget_delete_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the budget deletion request.
        
        Args:
            arguments: Tool arguments containing budget IDs to delete
            
        Returns:
            Dictionary containing the deletion results
            
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
                "Deleting budgets",
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
                
                # Make the budget deletion request
                response = await client.post("/BudgetDeleteRQ", request_payload)
            
            # Log successful operation
            self.logger.info(
                "Budgets deleted successfully",
                budget_count=len(sanitized_budget_ids),
                budget_ids=sanitized_budget_ids,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "deleted_budget_ids": sanitized_budget_ids,
                "deletion_count": len(sanitized_budget_ids),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "operation_summary": {
                    "operation": "delete",
                    "resource_type": "budget",
                    "affected_count": len(sanitized_budget_ids),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Successfully deleted {len(sanitized_budget_ids)} budget(s)"
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
handler = BudgetDeleteRQHandler()


async def call_budget_delete_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BudgetDeleteRQ endpoint.
    
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
            operation_summary = data["operation_summary"]
            
            response_text = f"""🗑️ **Budget Deletion Completed**

✅ **Operation Summary:**
- **Operation**: {operation_summary['operation'].title()}
- **Resource Type**: {operation_summary['resource_type'].title()}
- **Budgets Deleted**: {operation_summary['affected_count']}
- **Language**: {operation_summary['language'].upper()}

📋 **Deleted Budget IDs:**
"""
            
            # List deleted budget IDs
            for i, budget_id in enumerate(data["deleted_budget_ids"], 1):
                response_text += f"  {i}. `{budget_id}`\n"
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

⚠️ **Important Note:**
The deleted budgets cannot be recovered. Make sure this was the intended action.

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Budget Deletion Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the budget IDs exist and are valid
- Check that you have permission to delete these budgets
- Ensure the budget IDs are not currently in use
- Verify your authentication credentials
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while deleting the budget(s):

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
