"""
BudgetSearchRQ - Search Budgets Tool

This tool handles searching for budgets in the Neobookings system with various filters and sorting options.
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
BUDGET_SEARCH_RQ_TOOL = Tool(
    name="budget_search_rq",
    description="""
    Search for budgets in the Neobookings system with various filters and sorting options.
    
    This tool provides comprehensive budget search functionality with multiple filtering
    criteria and pagination support.
    
    Parameters:
    - budget_ids (optional): List of specific budget IDs to search for
    - hotel_ids (optional): List of hotel IDs to filter by
    - date_from (optional): Start date for filtering (YYYY-MM-DD format)
    - date_to (optional): End date for filtering (YYYY-MM-DD format)
    - date_by (optional): Date field to filter by (creationdate, lastupdate)
    - filter_by (optional): Additional filters (customer info, status, etc.)
    - page (optional): Page number for pagination (default: 1)
    - num_results (optional): Number of results per page (default: 10, max: 100)
    - order_by (required): Field to order by (id, hotelid, name, price, creationdate, etc.)
    - order_type (required): Sort order (asc, desc)
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - List of budgets matching search criteria
    - Pagination information
    - Search metadata
    
    Example usage:
    "Search for budgets created today"
    "Find budgets for hotel 'HTL123' ordered by creation date"
    "Search budgets with customer name containing 'Garcia'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "budget_ids": {
                "type": "array",
                "description": "List of specific budget IDs to search for",
                "items": {
                    "type": "string",
                    "description": "Budget identifier"
                },
                "maxItems": 50
            },
            "hotel_ids": {
                "type": "array", 
                "description": "List of hotel IDs to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 20
            },
            "date_from": {
                "type": "string",
                "description": "Start date for filtering (YYYY-MM-DD format)",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "date_to": {
                "type": "string",
                "description": "End date for filtering (YYYY-MM-DD format)", 
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "date_by": {
                "type": "string",
                "description": "Date field to filter by",
                "enum": ["creationdate", "lastupdate"],
                "default": "creationdate"
            },
            "filter_by": {
                "type": "object",
                "description": "Additional filters for budget search",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Filter by customer name"
                    },
                    "surname": {
                        "type": "string", 
                        "description": "Filter by customer surname"
                    },
                    "country": {
                        "type": "string",
                        "description": "Filter by customer country"
                    },
                    "document": {
                        "type": "string",
                        "description": "Filter by customer document/passport"
                    },
                    "address": {
                        "type": "string",
                        "description": "Filter by customer address"
                    },
                    "client": {
                        "type": "object",
                        "description": "Client contact information filter",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "Customer email filter"
                            },
                            "phone": {
                                "type": "object",
                                "description": "Phone number filter",
                                "properties": {
                                    "prefix": {
                                        "type": "string",
                                        "description": "Phone prefix"
                                    },
                                    "number": {
                                        "type": "string",
                                        "description": "Phone number"
                                    }
                                },
                                "required": ["prefix", "number"],
                                "additionalProperties": False
                            }
                        },
                        "additionalProperties": False
                    },
                    "user": {
                        "type": "string",
                        "description": "Filter by user who created the budget"
                    },
                    "status": {
                        "type": "array",
                        "description": "Filter by budget status",
                        "items": {
                            "type": "string",
                            "enum": ["deleted", "expired", "booked", "pending"]
                        }
                    }
                },
                "additionalProperties": False
            },
            "page": {
                "type": "integer",
                "description": "Page number for pagination",
                "minimum": 1,
                "default": 1
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results per page",
                "minimum": 1,
                "maximum": 100,
                "default": 10
            },
            "order_by": {
                "type": "string",
                "description": "Field to order results by",
                "enum": ["id", "hotelid", "name", "price", "creationdate", "lastupdate", "arrivaldate", "departuredate", "status", "user"]
            },
            "order_type": {
                "type": "string",
                "description": "Sort order for results",
                "enum": ["asc", "desc"]
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["order_by", "order_type"],
        "additionalProperties": False
    }
)


class BudgetSearchRQHandler:
    """Handler for the BudgetSearchRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="budget_search_rq")
    
    def _validate_date_format(self, date_string: str, field_name: str) -> None:
        """Validate date format."""
        try:
            from datetime import datetime
            datetime.strptime(date_string, "%Y-%m-%d")
        except ValueError:
            raise ValidationError(
                f"Invalid date format for {field_name}. Expected format: YYYY-MM-DD"
            )
    
    def _format_budget_basic_detail(self, budget: Dict[str, Any]) -> Dict[str, Any]:
        """Format budget basic details for readable output."""
        formatted = {
            "budget_id": budget.get("BudgetId"),
            "origin": budget.get("Origin"),
            "hotel_id": budget.get("HotelId"),
            "rate_name": budget.get("RateName"),
            "board_name": budget.get("BoardName"),
            "creation_user": budget.get("CreationUser"),
            "arrival_date": budget.get("ArrivalDate"),
            "departure_date": budget.get("DepartureDate"),
            "status": budget.get("Status"),
            "is_sent": budget.get("IsSent"),
            "sent_date": budget.get("SentDate"),
            "is_copied": budget.get("IsCopied"),
            "copied_date": budget.get("CopiedDate"),
            "creation_date": budget.get("CreationDate")
        }
        
        # Format customer details
        customer = budget.get("CustomerDetail", {})
        if customer:
            formatted["customer"] = {
                "name": customer.get("Name"),
                "surname": customer.get("Surname"),
                "email": customer.get("Email"),
                "phone": customer.get("Phone"),
                "country": customer.get("Country"),
                "city": customer.get("City")
            }
        
        # Format amounts
        amounts = budget.get("AmountsDetail", {})
        if amounts:
            formatted["amounts"] = {
                "currency": amounts.get("Currency"),
                "final": amounts.get("AmountFinal"),
                "total": amounts.get("AmountTotal"),
                "base": amounts.get("AmountBase")
            }
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the budget search request.
        
        Args:
            arguments: Tool arguments containing search parameters
            
        Returns:
            Dictionary containing the search results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            budget_ids = arguments.get("budget_ids", [])
            hotel_ids = arguments.get("hotel_ids", [])
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            date_by = arguments.get("date_by", "creationdate")
            filter_by = arguments.get("filter_by", {})
            page = arguments.get("page", 1)
            num_results = arguments.get("num_results", 10)
            order_by = arguments.get("order_by")
            order_type = arguments.get("order_type")
            language = arguments.get("language", "es")
            
            # Validate required parameters
            if not order_by:
                raise ValidationError("order_by is required")
            if not order_type:
                raise ValidationError("order_type is required")
            
            # Validate date formats if provided
            if date_from:
                self._validate_date_format(date_from, "date_from")
            if date_to:
                self._validate_date_format(date_to, "date_to")
            
            # Validate date range
            if date_from and date_to:
                from datetime import datetime
                from_date = datetime.strptime(date_from, "%Y-%m-%d")
                to_date = datetime.strptime(date_to, "%Y-%m-%d")
                if from_date > to_date:
                    raise ValidationError("date_from cannot be later than date_to")
            
            # Sanitize string arrays
            sanitized_budget_ids = []
            for budget_id in budget_ids:
                if isinstance(budget_id, str) and budget_id.strip():
                    sanitized_budget_ids.append(sanitize_string(budget_id.strip()))
            
            sanitized_hotel_ids = []
            for hotel_id in hotel_ids:
                if isinstance(hotel_id, str) and hotel_id.strip():
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            self.logger.info(
                "Searching budgets",
                budget_ids_count=len(sanitized_budget_ids),
                hotel_ids_count=len(sanitized_hotel_ids),
                date_from=date_from,
                date_to=date_to,
                page=page,
                num_results=num_results,
                order_by=order_by,
                order_type=order_type,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload["OrderBy"] = order_by
            request_payload["OrderType"] = order_type
            
            # Add optional filters
            if sanitized_budget_ids:
                request_payload["BudgetId"] = sanitized_budget_ids
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            
            if date_from:
                request_payload["DateFrom"] = date_from
            
            if date_to:
                request_payload["DateTo"] = date_to
            
            if date_by != "creationdate":
                request_payload["DateBy"] = date_by
            
            if page != 1:
                request_payload["Page"] = page
            
            if num_results != 10:
                request_payload["NumResults"] = num_results
            
            # Add filter_by object if provided
            if filter_by:
                formatted_filter = {}
                
                # Simple string filters
                string_filters = ["name", "surname", "country", "document", "address", "user"]
                for field in string_filters:
                    if field in filter_by and filter_by[field]:
                        # Capitalize first letter for API
                        api_field = field.capitalize()
                        formatted_filter[api_field] = sanitize_string(filter_by[field])
                
                # Status array filter
                if filter_by.get("status"):
                    formatted_filter["Status"] = filter_by["status"]
                
                # Client filter object
                if filter_by.get("client"):
                    client_filter = {}
                    client = filter_by["client"]
                    
                    if client.get("email"):
                        client_filter["Email"] = sanitize_string(client["email"])
                    
                    if client.get("phone"):
                        phone = client["phone"]
                        if phone.get("prefix") and phone.get("number"):
                            client_filter["Phone"] = {
                                "Prefix": sanitize_string(phone["prefix"]),
                                "Number": sanitize_string(phone["number"])
                            }
                    
                    if client_filter:
                        formatted_filter["Client"] = client_filter
                
                if formatted_filter:
                    request_payload["FilterBy"] = formatted_filter
            
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
                
                # Make the budget search request
                response = await client.post("/BudgetSearchRQ", request_payload)
            
            # Extract search results from response
            budget_basic_details = response.get("BudgetBasicDetail", [])
            current_page = response.get("CurrentPage", page)
            total_pages = response.get("TotalPages", 0)
            total_records = response.get("TotalRecords", 0)
            
            # Format budget details
            formatted_budgets = []
            for budget in budget_basic_details:
                formatted_budgets.append(self._format_budget_basic_detail(budget))
            
            # Log successful operation
            self.logger.info(
                "Budget search completed successfully",
                found_budgets=len(formatted_budgets),
                total_records=total_records,
                current_page=current_page,
                total_pages=total_pages,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "budgets": formatted_budgets,
                "pagination": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "total_records": total_records,
                    "page_size": num_results,
                    "has_next_page": current_page < total_pages,
                    "has_previous_page": current_page > 1
                },
                "search_criteria": {
                    "budget_ids": sanitized_budget_ids,
                    "hotel_ids": sanitized_hotel_ids,
                    "date_from": date_from,
                    "date_to": date_to,
                    "date_by": date_by,
                    "filter_by": filter_by,
                    "order_by": order_by,
                    "order_type": order_type
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "search_summary": {
                    "results_found": len(formatted_budgets),
                    "total_available": total_records,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(formatted_budgets)} budget(s) on page {current_page} of {total_pages}"
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
handler = BudgetSearchRQHandler()


async def call_budget_search_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BudgetSearchRQ endpoint.
    
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
            pagination = data["pagination"]
            search_criteria = data["search_criteria"]
            search_summary = data["search_summary"]
            
            response_text = f"""🔍 **Budget Search Results**

✅ **Search Summary:**
- **Results Found**: {search_summary['results_found']} budget(s)
- **Total Available**: {search_summary['total_available']} budget(s)
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Language**: {search_summary['language'].upper()}

📋 **Search Criteria:**
- **Order By**: {search_criteria['order_by'].title()}
- **Order Type**: {search_criteria['order_type'].upper()}"""
            
            # Add filter information
            if search_criteria["budget_ids"]:
                response_text += f"\n- **Budget IDs**: {', '.join(search_criteria['budget_ids'])}"
            if search_criteria["hotel_ids"]:
                response_text += f"\n- **Hotel IDs**: {', '.join(search_criteria['hotel_ids'])}"
            if search_criteria["date_from"] or search_criteria["date_to"]:
                date_range = f"{search_criteria['date_from'] or 'Start'} to {search_criteria['date_to'] or 'End'}"
                response_text += f"\n- **Date Range ({search_criteria['date_by']})**: {date_range}"
            
            # Add filter_by information
            filter_by = search_criteria.get("filter_by", {})
            if filter_by:
                filter_items = []
                for key, value in filter_by.items():
                    if key == "client" and isinstance(value, dict):
                        if value.get("email"):
                            filter_items.append(f"Email: {value['email']}")
                        if value.get("phone"):
                            phone = value["phone"]
                            filter_items.append(f"Phone: {phone.get('prefix', '')}{phone.get('number', '')}")
                    elif key == "status" and isinstance(value, list):
                        filter_items.append(f"Status: {', '.join(value)}")
                    elif isinstance(value, str):
                        filter_items.append(f"{key.title()}: {value}")
                
                if filter_items:
                    response_text += f"\n- **Filters**: {'; '.join(filter_items)}"
            
            response_text += "\n\n"
            
            # Display budget results
            if data["budgets"]:
                for i, budget in enumerate(data["budgets"], 1):
                    response_text += f"""{'='*60}
📊 **Budget #{i}: {budget.get('budget_id', 'Unknown ID')}**
{'='*60}

🏨 **Basic Information:**
- **Budget ID**: {budget.get('budget_id', 'N/A')}
- **Hotel ID**: {budget.get('hotel_id', 'N/A')}
- **Origin**: {budget.get('origin', 'N/A')}
- **Status**: {budget.get('status', 'N/A')}
- **Rate**: {budget.get('rate_name', 'N/A')}
- **Board**: {budget.get('board_name', 'N/A')}

📅 **Dates:**
- **Created**: {budget.get('creation_date', 'N/A')}
- **Arrival**: {budget.get('arrival_date', 'N/A')}
- **Departure**: {budget.get('departure_date', 'N/A')}
- **Sent**: {'Yes' if budget.get('is_sent') else 'No'} ({budget.get('sent_date', 'N/A')})
- **Copied**: {'Yes' if budget.get('is_copied') else 'No'} ({budget.get('copied_date', 'N/A')})
"""
                    
                    # Add customer information
                    customer = budget.get('customer', {})
                    if customer and any(customer.values()):
                        response_text += f"""👤 **Customer:**
- **Name**: {customer.get('name', '')} {customer.get('surname', '')}
- **Email**: {customer.get('email', 'N/A')}
- **Phone**: {customer.get('phone', 'N/A')}
- **Country**: {customer.get('country', 'N/A')}
- **City**: {customer.get('city', 'N/A')}
"""
                    
                    # Add amounts information
                    amounts = budget.get('amounts', {})
                    if amounts and any(amounts.values()):
                        response_text += f"""💰 **Amounts:**
- **Currency**: {amounts.get('currency', 'N/A')}
- **Final**: {amounts.get('final', 'N/A')}
- **Total**: {amounts.get('total', 'N/A')}
- **Base**: {amounts.get('base', 'N/A')}
"""
                    
                    response_text += "\n"
            else:
                response_text += "📭 **No budgets found matching the search criteria.**\n\n"
            
            # Add pagination info
            if pagination["total_pages"] > 1:
                response_text += f"""📄 **Pagination:**
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Page Size**: {pagination['page_size']}
- **Total Records**: {pagination['total_records']}
- **Has Next Page**: {'Yes' if pagination['has_next_page'] else 'No'}
- **Has Previous Page**: {'Yes' if pagination['has_previous_page'] else 'No'}

"""
            
            response_text += f"""🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms"""
            
        else:
            response_text = f"""❌ **Budget Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the search parameters are valid
- Check date formats (YYYY-MM-DD)
- Ensure budget or hotel IDs exist if specified
- Verify filter criteria are correct
- Check your authentication credentials
- Ensure order_by and order_type are specified
- Contact support if the issue persists"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching budgets:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again."""
        return [TextContent(type="text", text=error_text)]
