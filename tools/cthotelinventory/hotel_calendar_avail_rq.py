"""
HotelCalendarAvailRQ - Get Hotel Calendar Availability Tool

This tool retrieves hotel room availability calendar information for a specified date range.
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
HOTEL_CALENDAR_AVAIL_RQ_TOOL = Tool(
    name="hotel_calendar_avail_rq",
    description="""
    Retrieve hotel room availability calendar for a specified date range.
    
    This tool provides comprehensive calendar availability information including:
    - Daily availability status for each room type
    - Pricing information per day
    - Minimum and maximum stay requirements
    - Release periods and quotas
    - Inventory status and restrictions
    
    Parameters:
    - date_from (required): Start date in YYYY-MM-DD format
    - date_to (required): End date in YYYY-MM-DD format  
    - adults (required): Number of adults for the search
    - hotel_ids (optional): List of hotel identifiers to filter by
    - room_ids (optional): List of room identifiers to filter by
    - calendar_type (optional): Type of calendar view ("normal" or "merge", default: "normal")
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Daily availability calendar for specified hotels/rooms
    - Pricing information per day
    - Availability restrictions and quotas
    - Inventory status information
    
    Example usage:
    "Check availability calendar for hotel 'HTL123' from 2024-06-01 to 2024-06-30 for 2 adults"
    "Get room availability for next month for 1 adult"
    "Show calendar availability for room 'RM456' in July 2024"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format",
                "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
            },
            "date_to": {
                "type": "string", 
                "description": "End date in YYYY-MM-DD format",
                "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
            },
            "adults": {
                "type": "integer",
                "description": "Number of adults for the search",
                "minimum": 1,
                "maximum": 20
            },
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 50
            },
            "room_ids": {
                "type": "array",
                "description": "List of room identifiers to filter by", 
                "items": {
                    "type": "string",
                    "description": "Room identifier"
                },
                "maxItems": 50
            },
            "calendar_type": {
                "type": "string",
                "description": "Type of calendar view",
                "enum": ["normal", "merge"],
                "default": "normal"
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["date_from", "date_to", "adults"],
        "additionalProperties": False
    }
)


class HotelCalendarAvailRQHandler:
    """Handler for the HotelCalendarAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_calendar_avail_rq")
    
    def _format_amounts_detail(self, amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Format amounts detail information for readable output."""
        if not amounts:
            return {}
            
        return {
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
            "deposit": amounts.get("AmountDeposit")
        }
    
    def _format_inventory_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Format inventory status information for readable output."""
        if not status:
            return {}
            
        formatted = {
            "status": status.get("Status"),
            "restriction": status.get("Restriction")
        }
        
        # Format stop sale info
        stop_sale = status.get("StopSale", {})
        if stop_sale:
            formatted["stop_sale"] = {
                "code": stop_sale.get("Code"),
                "name": stop_sale.get("Name")
            }
        
        return formatted
    
    def _format_calendar_avail(self, calendar_avail: Dict[str, Any]) -> Dict[str, Any]:
        """Format calendar availability information for readable output."""
        formatted = {
            "hotel_id": calendar_avail.get("HotelId"),
            "room_id": calendar_avail.get("HotelRoomId"),
            "date": calendar_avail.get("Date"),
            "adults": calendar_avail.get("Adults"),
            "availability": calendar_avail.get("Availability"),
            "quota": calendar_avail.get("Quota"),
            "min_stay": calendar_avail.get("MinStay"),
            "max_stay": calendar_avail.get("MaxStay"),
            "release": calendar_avail.get("Release")
        }
        
        # Format amounts
        amounts = calendar_avail.get("AmountsDetail", {})
        if amounts:
            formatted["amounts"] = self._format_amounts_detail(amounts)
        
        # Format inventory status
        inventory_status = calendar_avail.get("HotelInventoryStatus", {})
        if inventory_status:
            formatted["inventory_status"] = self._format_inventory_status(inventory_status)
        
        return formatted
    
    def _group_availability_by_hotel_room(self, availability_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group availability data by hotel and room for better organization."""
        grouped = {}
        
        for avail in availability_list:
            hotel_id = avail["hotel_id"]
            room_id = avail["room_id"]
            
            if hotel_id not in grouped:
                grouped[hotel_id] = {}
            
            if room_id not in grouped[hotel_id]:
                grouped[hotel_id][room_id] = []
            
            grouped[hotel_id][room_id].append(avail)
        
        return grouped
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the hotel calendar availability request.
        
        Args:
            arguments: Tool arguments containing date range and filters
            
        Returns:
            Dictionary containing the calendar availability information
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            adults = arguments.get("adults")
            hotel_ids = arguments.get("hotel_ids", [])
            room_ids = arguments.get("room_ids", [])
            calendar_type = arguments.get("calendar_type", "normal")
            language = arguments.get("language", "es")
            
            # Validate required fields
            if not date_from:
                raise ValidationError("date_from is required")
            if not date_to:
                raise ValidationError("date_to is required")
            if not adults:
                raise ValidationError("adults is required")
            
            # Validate and parse dates
            parsed_date_from = parse_date(date_from)
            parsed_date_to = parse_date(date_to)
            
            # Validate adults
            if not isinstance(adults, int) or adults < 1:
                raise ValidationError("adults must be a positive integer")
            
            # Validate and sanitize hotel IDs
            sanitized_hotel_ids = []
            if hotel_ids:
                if not isinstance(hotel_ids, list):
                    raise ValidationError("hotel_ids must be a list")
                
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            # Validate and sanitize room IDs
            sanitized_room_ids = []
            if room_ids:
                if not isinstance(room_ids, list):
                    raise ValidationError("room_ids must be a list")
                
                for room_id in room_ids:
                    if not isinstance(room_id, str) or not room_id.strip():
                        raise ValidationError(f"Invalid room ID: {room_id}")
                    sanitized_room_ids.append(sanitize_string(room_id.strip()))
            
            self.logger.info(
                "Retrieving hotel calendar availability",
                date_from=parsed_date_from,
                date_to=parsed_date_to,
                adults=adults,
                hotel_count=len(sanitized_hotel_ids),
                room_count=len(sanitized_room_ids),
                calendar_type=calendar_type,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload.update({
                "DateFrom": parsed_date_from,
                "DateTo": parsed_date_to,
                "Adults": adults,
                "CalendarType": calendar_type
            })
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            
            if sanitized_room_ids:
                request_payload["HotelRoomId"] = sanitized_room_ids
            
            # Add FilterBy for calendar-specific filters
            request_payload["FilterBy"] = {
                "Visibility": ["visible"]  # Only show visible availability
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
                
                # Make the hotel calendar availability request
                response = await client.post("/HotelCalendarAvailRQ", request_payload)
            
            # Extract calendar availability from response
            calendar_avail_raw = response.get("HotelCalendarAvail", [])
            
            # Format calendar availability
            formatted_availability = []
            for calendar_avail in calendar_avail_raw:
                formatted_availability.append(self._format_calendar_avail(calendar_avail))
            
            # Group availability by hotel and room
            grouped_availability = self._group_availability_by_hotel_room(formatted_availability)
            
            # Log successful operation
            self.logger.info(
                "Hotel calendar availability retrieved successfully",
                availability_count=len(formatted_availability),
                hotels_found=len(grouped_availability),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "calendar_availability": formatted_availability,
                "grouped_by_hotel_room": grouped_availability,
                "search_criteria": {
                    "date_from": parsed_date_from,
                    "date_to": parsed_date_to,
                    "adults": adults,
                    "calendar_type": calendar_type,
                    "hotel_ids": sanitized_hotel_ids,
                    "room_ids": sanitized_room_ids
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_availability_records": len(formatted_availability),
                    "hotels_with_availability": len(grouped_availability),
                    "date_range_days": len(formatted_availability) // max(len(grouped_availability), 1) if grouped_availability else 0,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved calendar availability for {len(grouped_availability)} hotels ({len(formatted_availability)} records)"
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
handler = HotelCalendarAvailRQHandler()


async def call_hotel_calendar_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the HotelCalendarAvailRQ endpoint.
    
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
            criteria = data["search_criteria"]
            
            response_text = f"""📅 **Hotel Calendar Availability Retrieved**

✅ **Summary:**
- **Total Records**: {summary['total_availability_records']}
- **Hotels with Availability**: {summary['hotels_with_availability']}
- **Date Range Days**: {summary['date_range_days']}
- **Language**: {summary['language'].upper()}

🔍 **Search Criteria:**
- **Date Range**: {criteria['date_from']} to {criteria['date_to']}
- **Adults**: {criteria['adults']}
- **Calendar Type**: {criteria['calendar_type'].title()}
- **Hotel Filter**: {', '.join(criteria['hotel_ids']) if criteria['hotel_ids'] else 'All hotels'}
- **Room Filter**: {', '.join(criteria['room_ids']) if criteria['room_ids'] else 'All rooms'}

"""
            
            # Display availability grouped by hotel and room
            grouped_data = data["grouped_by_hotel_room"]
            if grouped_data:
                response_text += f"""
{'='*80}
📅 **CALENDAR AVAILABILITY BY HOTEL & ROOM**
{'='*80}
"""
                
                for hotel_id, rooms_data in grouped_data.items():
                    response_text += f"""
🏨 **Hotel ID: {hotel_id}**
   **Available Rooms**: {len(rooms_data)} room type(s)

"""
                    
                    for room_id, availability_records in rooms_data.items():
                        response_text += f"""   🛏️ **Room ID: {room_id}**
      **Available Dates**: {len(availability_records)} day(s)

"""
                        
                        # Show first few availability records for this room
                        for i, record in enumerate(availability_records[:7], 1):  # Show first 7 days
                            availability_status = "✅ Available" if record.get("availability", 0) > 0 else "❌ No availability"
                            response_text += f"""      {i:2d}. **{record['date']}** - {availability_status}
"""
                            
                            if record.get("availability", 0) > 0:
                                response_text += f"""          💰 Availability: {record['availability']} / {record.get('quota', 'N/A')} units
"""
                                
                                amounts = record.get("amounts", {})
                                if amounts and amounts.get("final"):
                                    response_text += f"""          💵 Price: {amounts['final']} {amounts.get('currency', '')}
"""
                                
                                if record.get("min_stay"):
                                    response_text += f"""          📅 Min Stay: {record['min_stay']} nights
"""
                                
                                inventory_status = record.get("inventory_status", {})
                                if inventory_status.get("status") == "closed":
                                    response_text += f"""          🚫 Status: Closed ({inventory_status.get('restriction', '')})
"""
                        
                        if len(availability_records) > 7:
                            response_text += f"""      ... and {len(availability_records) - 7} more days
"""
                        
                        response_text += "\n"
            
            # Display summary statistics
            calendar_data = data["calendar_availability"]
            if calendar_data:
                available_days = sum(1 for record in calendar_data if record.get("availability", 0) > 0)
                closed_days = sum(1 for record in calendar_data if record.get("inventory_status", {}).get("status") == "closed")
                
                response_text += f"""
{'='*80}
📊 **AVAILABILITY STATISTICS**
{'='*80}

📈 **Overall Statistics:**
- **Total Days Checked**: {len(calendar_data)}
- **Days with Availability**: {available_days}
- **Closed Days**: {closed_days}
- **No Availability Days**: {len(calendar_data) - available_days - closed_days}

"""
                
                # Show pricing range if available
                prices = []
                for record in calendar_data:
                    amounts = record.get("amounts", {})
                    if amounts and amounts.get("final"):
                        prices.append(amounts["final"])
                
                if prices:
                    min_price = min(prices)
                    max_price = max(prices)
                    avg_price = sum(prices) / len(prices)
                    
                    currency = calendar_data[0].get("amounts", {}).get("currency", "")
                    
                    response_text += f"""💰 **Price Range:**
- **Minimum**: {min_price} {currency}
- **Maximum**: {max_price} {currency}
- **Average**: {avg_price:.2f} {currency}

"""
            
            response_text += f"""🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Calendar Availability**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the date range is valid (date_from should be before date_to)
- Check that hotel IDs and room IDs exist and are accessible
- Ensure the date range is not too far in the future
- Verify your authentication credentials
- Check that adults count is reasonable (1-20)
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving calendar availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
