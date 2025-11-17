"""
OrderSearchRQ - Order Search Tool

This tool searches for orders in the Neobookings system based on various criteria.
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
    sanitize_string,
    parse_date
)

# Tool definition
ORDER_SEARCH_RQ_TOOL = Tool(
    name="order_search_rq",
    description="""
    Search for orders in the Neobookings system based on various criteria.
    
    This tool allows searching for orders using multiple filters including hotel IDs,
    order IDs, date ranges, payment states, order states, and other criteria.
    Results can be sorted and paginated.
    
    Parameters:
    - hotel_ids (optional): List of hotel IDs to filter by
    - order_ids (optional): List of specific order IDs to search
    - date_from (optional): Start date for date range filter
    - date_to (optional): End date for date range filter
    - date_by (optional): Type of date filter to apply
    - order_by (required): Field to sort results by
    - order_type (required): Sort direction (asc/desc)
    - page (optional): Page number for pagination
    - num_results (optional): Number of results per page
    - filters (optional): Additional filters for order states, payment methods, etc.
    - language (optional): Language for the request
    
    Returns:
    - List of matching orders with basic details
    - Pagination information
    - Total record count
    
    Example usage:
    "Search for orders in hotel H123 from last week"
    "Find all confirmed orders from January 2024"
    "Search pending payment orders sorted by creation date"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel IDs to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 50
            },
            "order_ids": {
                "type": "array",
                "description": "List of specific order IDs to search",
                "items": {
                    "type": "string",
                    "description": "Order identifier"
                },
                "maxItems": 100
            },
            "date_from": {
                "type": "string",
                "description": "Start date for date range filter (YYYY-MM-DD)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "date_to": {
                "type": "string",
                "description": "End date for date range filter (YYYY-MM-DD)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "date_by": {
                "type": "string",
                "description": "Type of date filter to apply",
                "enum": ["creationdate", "lastupdate", "arrivaldate", "departuredate", "stay"],
                "default": "creationdate"
            },
            "order_by": {
                "type": "string",
                "description": "Field to sort results by",
                "enum": ["id", "name", "price", "creationdate", "lastupdate", "arrivaldate", "departuredate"],
                "default": "creationdate"
            },
            "order_type": {
                "type": "string",
                "description": "Sort direction",
                "enum": ["asc", "desc"],
                "default": "desc"
            },
            "page": {
                "type": "integer",
                "description": "Page number for pagination (1-based)",
                "minimum": 1,
                "maximum": 1000,
                "default": 1
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results per page",
                "minimum": 1,
                "maximum": 100,
                "default": 10
            },
            "filters": {
                "type": "object",
                "description": "Additional search filters",
                "properties": {
                    "order_states": {
                        "type": "array",
                        "description": "Order states to filter by",
                        "items": {
                            "type": "string",
                            "enum": ["confirm", "cancel", "invalid"]
                        }
                    },
                    "payment_states": {
                        "type": "array",
                        "description": "Payment states to filter by",
                        "items": {
                            "type": "string",
                            "enum": ["entire", "partial", "pending"]
                        }
                    },
                    "payment_methods": {
                        "type": "array",
                        "description": "Payment methods to filter by",
                        "items": {
                            "type": "string",
                            "enum": [
                                "tpv", "tpvmanual", "card", "credit", "transference",
                                "moneyorder", "paypal", "cash", "financed", "otb", "other", "nil"
                            ]
                        }
                    },
                    "reservation_modes": {
                        "type": "array",
                        "description": "Reservation modes to filter by",
                        "items": {
                            "type": "string",
                            "enum": ["room", "package", "product"]
                        }
                    },
                    "reviewed": {
                        "type": "boolean",
                        "description": "Filter by reviewed status"
                    },
                    "from_professional": {
                        "type": "boolean",
                        "description": "Filter professional reservations"
                    },
                    "notification_status": {
                        "type": "string",
                        "description": "Notification status filter",
                        "enum": ["ever", "never", "pending", "all"]
                    },
                    "channels": {
                        "type": "array",
                        "description": "Sales channels to filter by",
                        "items": {"type": "string"}
                    },
                    "customers": {
                        "type": "array",
                        "description": "Customer identifiers to filter by",
                        "items": {"type": "string"}
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
        "required": ["order_by", "order_type"],
        "additionalProperties": False
    }
)


class OrderSearchRQHandler:
    """Handler for the OrderSearchRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="order_search_rq")
    
    def _validate_date_range(self, date_from: Optional[str], date_to: Optional[str]) -> None:
        """Validate date range parameters."""
        if date_from and date_to:
            # Both dates provided, validate range
            from datetime import datetime
            try:
                start_date = datetime.strptime(date_from, "%Y-%m-%d")
                end_date = datetime.strptime(date_to, "%Y-%m-%d")
                
                if start_date > end_date:
                    raise ValidationError("date_from cannot be later than date_to")
                    
                # Check if range is reasonable (not more than 2 years)
                days_diff = (end_date - start_date).days
                if days_diff > 730:  # 2 years
                    raise ValidationError("Date range cannot exceed 2 years")
                    
            except ValueError as e:
                if "date_from cannot be later" in str(e) or "Date range cannot exceed" in str(e):
                    raise
                raise ValidationError("Invalid date format. Use YYYY-MM-DD")
    
    def _build_filter_by(self, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build FilterBy structure from filters."""
        if not filters:
            return None
        
        filter_by = {}
        
        # Map simple array filters
        array_mappings = {
            "order_states": "OrderState",
            "payment_states": "PaymentState", 
            "payment_methods": "PaymentMethod",
            "reservation_modes": "ReservationMode",
            "channels": "Channel",
            "customers": "Customer"
        }
        
        for filter_key, api_key in array_mappings.items():
            if filter_key in filters and filters[filter_key]:
                filter_by[api_key] = filters[filter_key]
        
        # Map boolean filters
        boolean_mappings = {
            "reviewed": "Reviewed",
            "from_professional": "FromProfessional"
        }
        
        for filter_key, api_key in boolean_mappings.items():
            if filter_key in filters and filters[filter_key] is not None:
                filter_by[api_key] = filters[filter_key]
        
        # Map notification status
        if "notification_status" in filters and filters["notification_status"]:
            filter_by["Notified"] = filters["notification_status"]
        
        return filter_by if filter_by else None
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the order search request.
        
        Args:
            arguments: Tool arguments containing search criteria
            
        Returns:
            Dictionary containing the search results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids", [])
            order_ids = arguments.get("order_ids", [])
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            date_by = arguments.get("date_by", "creationdate")
            order_by = arguments.get("order_by", "creationdate")
            order_type = arguments.get("order_type", "desc")
            page = arguments.get("page", 1)
            num_results = arguments.get("num_results", 10)
            filters = arguments.get("filters", {})
            language = arguments.get("language", "es")
            
            # Validate date range
            if date_from:
                parse_date(date_from)
            if date_to:
                parse_date(date_to)
            self._validate_date_range(date_from, date_to)
            
            # Validate and sanitize ID lists
            validated_hotel_ids = []
            for hotel_id in hotel_ids:
                validated_hotel_ids.append(sanitize_string(str(hotel_id).strip()))
            
            validated_order_ids = []
            for order_id in order_ids:
                validated_order_ids.append(sanitize_string(str(order_id).strip()))
            
            self.logger.info(
                "Searching orders",
                hotel_count=len(validated_hotel_ids),
                order_count=len(validated_order_ids),
                date_from=date_from,
                date_to=date_to,
                date_by=date_by,
                order_by=order_by,
                order_type=order_type,
                page=page,
                num_results=num_results,
                has_filters=bool(filters),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "OrderBy": order_by,
                "OrderType": order_type
            }
            
            # Add optional hotel IDs
            if validated_hotel_ids:
                request_payload["HotelId"] = validated_hotel_ids
            
            # Add optional order IDs
            if validated_order_ids:
                request_payload["OrderId"] = validated_order_ids
            
            # Add date range filters
            if date_from:
                request_payload["DateFrom"] = date_from
            if date_to:
                request_payload["DateTo"] = date_to
            if date_from or date_to:
                request_payload["DateBy"] = date_by
            
            # Add pagination
            request_payload["Page"] = page
            request_payload["NumResults"] = num_results
            
            # Add filters
            filter_by = self._build_filter_by(filters)
            if filter_by:
                request_payload["FilterBy"] = filter_by
            
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
                
                # Make the order search request
                response = await client.post("/OrderSearchRQ", request_payload)
            
            # Extract response data
            current_page = response.get("CurrentPage", page)
            total_pages = response.get("TotalPages", 0)
            total_records = response.get("TotalRecords", 0)
            order_basic_details = response.get("OrderBasicDetail", [])
            api_response = response.get("Response", {})
            
            # Log successful operation
            self.logger.info(
                "Order search completed successfully",
                current_page=current_page,
                total_pages=total_pages,
                total_records=total_records,
                results_returned=len(order_basic_details),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Process order details
            processed_orders = []
            for order in order_basic_details:
                order_summary = {
                    "order_id": order.get("OrderId"),
                    "order_id_origin": order.get("OrderIdOrigin"),
                    "origin": order.get("Origin"),
                    "origin_ads": order.get("OriginAds"),
                    "order_status": order.get("OrderStatusDetail", {}),
                    "amounts": order.get("AmountsDetail", {}),
                    "customer": order.get("CustomerDetail", {}),
                    "room_summaries": order.get("HotelRoomSummaryBasicDetail", []),
                    "has_products": order.get("HasProducts", False),
                    "has_packets": order.get("HasPackets", False),
                    "external_systems": order.get("ExternalSystem", []),
                    "tracking": order.get("Tracking", {})
                }
                processed_orders.append(order_summary)
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "hotel_ids": validated_hotel_ids,
                    "order_ids": validated_order_ids,
                    "date_range": {
                        "from": date_from,
                        "to": date_to,
                        "filter_by": date_by
                    },
                    "sorting": {
                        "order_by": order_by,
                        "order_type": order_type
                    },
                    "pagination": {
                        "page": page,
                        "num_results": num_results
                    },
                    "filters_applied": filter_by
                },
                "pagination_info": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "total_records": total_records,
                    "results_per_page": num_results,
                    "results_returned": len(order_basic_details)
                },
                "orders": processed_orders,
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            success_message = f"Found {total_records} orders, returning page {current_page} of {total_pages}"
            
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
handler = OrderSearchRQHandler()


async def call_order_search_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the OrderSearchRQ endpoint.
    
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
            pagination = data["pagination_info"]
            criteria = data["search_criteria"]
            orders = data["orders"]
            
            response_text = f"""✅ **Order Search Results**

📊 **Search Summary:**
- **Total Records Found**: {pagination['total_records']}
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Results This Page**: {pagination['results_returned']} of {pagination['results_per_page']}

🔍 **Search Criteria:**
- **Hotels**: {len(criteria['hotel_ids'])} specified
- **Orders**: {len(criteria['order_ids'])} specified
- **Date Range**: {criteria['date_range']['from'] or 'No start'} to {criteria['date_range']['to'] or 'No end'} ({criteria['date_range']['filter_by']})
- **Sorting**: {criteria['sorting']['order_by']} ({criteria['sorting']['order_type']})
- **Filters**: {'Applied' if criteria['filters_applied'] else 'None'}

📋 **Found Orders:**
"""
            
            if not orders:
                response_text += "- No orders found matching the search criteria\n"
            else:
                for i, order in enumerate(orders, 1):
                    status = order.get("order_status", {})
                    amounts = order.get("amounts", {})
                    customer = order.get("customer", {})
                    
                    order_state = status.get("OrderState", "Unknown")
                    payment_state = status.get("PaymentState", "Unknown")
                    total_amount = amounts.get("AmountTotal", 0)
                    currency = amounts.get("Currency", "")
                    customer_name = f"{customer.get('Firstname', '')} {customer.get('Surname', '')}".strip()
                    
                    response_text += f"""
**{i}. Order {order['order_id']}**
- **Status**: {order_state} | **Payment**: {payment_state}
- **Customer**: {customer_name or 'N/A'}
- **Amount**: {total_amount} {currency}
- **Origin**: {order.get('origin', 'N/A')}
- **Rooms**: {len(order.get('room_summaries', []))}
- **Has Products**: {'Yes' if order.get('has_products') else 'No'}
- **Has Packages**: {'Yes' if order.get('has_packets') else 'No'}
"""
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Navigation:**
- **Previous Page**: {max(1, pagination['current_page'] - 1) if pagination['current_page'] > 1 else 'N/A'}
- **Next Page**: {pagination['current_page'] + 1 if pagination['current_page'] < pagination['total_pages'] else 'N/A'}
- **Total Pages**: {pagination['total_pages']}

📝 **Search Tips:**
- Use specific hotel IDs to narrow results
- Apply date ranges for time-based searches
- Filter by order states (confirm, cancel, invalid)
- Filter by payment states (entire, partial, pending)
- Use pagination to browse through large result sets
- Sort by different fields (date, price, name)
- Combine multiple filters for precise searches

🔄 **Actions Available:**
- View specific order details using OrderDetailsRQ
- Modify orders using OrderDataModifyRQ
- Cancel orders using OrderCancelRQ
- Create payments using OrderPaymentCreateRQ
- Search with different criteria to refine results
"""
            
        else:
            response_text = f"""❌ **Order Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify hotel IDs are correct and exist
- Check order IDs format if specified
- Ensure date format is YYYY-MM-DD
- Verify date range is valid (from <= to)
- Check that date range doesn't exceed 2 years
- Ensure order_by field is valid
- Verify order_type is 'asc' or 'desc'
- Check page number is positive
- Ensure num_results is between 1-100
- Validate filter values are from allowed enums
- Ensure authentication credentials are valid
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching orders:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
