"""
PackageCalendarAvailRQ - Package Calendar Availability Tool

This tool retrieves calendar availability information for tourism packages in the Neobookings system.
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
PACKAGE_CALENDAR_AVAIL_RQ_TOOL = Tool(
    name="package_calendar_avail_rq",
    description="""
    Retrieve calendar availability information for tourism packages.
    
    This tool provides day-by-day availability and pricing information for tourism packages
    within a specified date range. It's useful for displaying availability calendars
    and helping customers choose optimal booking dates.
    
    Parameters:
    - date_from (required): Start date for calendar range
    - date_to (required): End date for calendar range  
    - adults (required): Number of adults for pricing calculation
    - hotel_ids (optional): Specific hotel IDs to check
    - package_ids (optional): Specific package IDs to check
    - hotel_room_ids (optional): Specific room IDs to check
    - language (optional): Language for the request
    
    Returns:
    - Day-by-day availability information
    - Pricing details per day
    - Minimum/maximum stay requirements
    - Release period restrictions
    - Inventory status for each date
    - Quota information
    
    Example usage:
    "Show package availability calendar for March 2024"
    "Get pricing calendar for vacation packages in hotel HTL123"
    "Display availability dates for family packages"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Start date for calendar range (YYYY-MM-DD)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "date_to": {
                "type": "string",
                "description": "End date for calendar range (YYYY-MM-DD)",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "adults": {
                "type": "integer",
                "description": "Number of adults for pricing",
                "minimum": 1,
                "maximum": 20
            },
            "hotel_ids": {
                "type": "array",
                "description": "Specific hotel IDs to check",
                "items": {"type": "string"},
                "maxItems": 100
            },
            "package_ids": {
                "type": "array",
                "description": "Specific package IDs to check",
                "items": {"type": "string"},
                "maxItems": 100
            },
            "hotel_room_ids": {
                "type": "array",
                "description": "Specific room IDs to check",
                "items": {"type": "string"},
                "maxItems": 100
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


class PackageCalendarAvailRQHandler:
    """Handler for the PackageCalendarAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="package_calendar_avail_rq")
    
    def _validate_date_range(self, date_from: str, date_to: str) -> tuple[str, str]:
        """Validate date range."""
        if not date_from or not date_to:
            raise ValidationError("Both date_from and date_to are required")
        
        date_from = date_from.strip()
        date_to = date_to.strip()
        
        # Basic date format validation is handled by JSON schema
        # Additional business logic validation could be added here
        
        return date_from, date_to
    
    def _validate_string_list(self, values: List[str], field_name: str, max_items: int = 100) -> List[str]:
        """Validate and sanitize a list of strings."""
        if not values:
            return []
        
        if len(values) > max_items:
            raise ValidationError(f"{field_name}: maximum {max_items} items allowed")
        
        validated_values = []
        for i, value in enumerate(values):
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{field_name} {i+1}: must be a non-empty string")
            
            sanitized_value = sanitize_string(value.strip())
            if not sanitized_value:
                raise ValidationError(f"{field_name} {i+1}: invalid format after sanitization")
            
            validated_values.append(sanitized_value)
        
        return validated_values
    
    def _format_calendar_availability(self, calendar_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format calendar availability information for readable output."""
        formatted_calendar = []
        
        for day in calendar_data:
            formatted_day = {
                "hotel_id": day.get("HotelId"),
                "package_id": day.get("PackageId"),
                "hotel_room_ids": day.get("HotelRoomId", []),
                "date": day.get("Date"),
                "adults": day.get("Adults"),
                "availability": day.get("Availability"),
                "min_stay": day.get("MinStay"),
                "max_stay": day.get("MaxStay"),
                "release": day.get("Release"),
                "amounts": {},
                "inventory_status": {}
            }
            
            # Format amounts detail
            amounts = day.get("AmountsDetail", {})
            if amounts:
                formatted_day["amounts"] = {
                    "currency": amounts.get("Currency"),
                    "final_amount": amounts.get("AmountFinal"),
                    "total_amount": amounts.get("AmountTotal"),
                    "base_amount": amounts.get("AmountBase"),
                    "taxes_amount": amounts.get("AmountTaxes"),
                    "tourist_tax_amount": amounts.get("AmountTouristTax"),
                    "before_amount": amounts.get("AmountBefore"),
                    "offers_amount": amounts.get("AmountOffers"),
                    "discounts_amount": amounts.get("AmountDiscounts")
                }
            
            # Format inventory status
            inventory_status = day.get("HotelInventoryStatus", {})
            if inventory_status:
                formatted_day["inventory_status"] = {
                    "status": inventory_status.get("Status"),
                    "restriction": inventory_status.get("Restriction"),
                    "stop_sale": {}
                }
                
                # Format stop sale information
                stop_sale = inventory_status.get("StopSale", {})
                if stop_sale:
                    formatted_day["inventory_status"]["stop_sale"] = {
                        "code": stop_sale.get("Code"),
                        "name": stop_sale.get("Name")
                    }
            
            formatted_calendar.append(formatted_day)
        
        return formatted_calendar
    
    def _analyze_calendar_data(self, calendar_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze calendar data to provide insights."""
        if not calendar_data:
            return {
                "total_days": 0,
                "available_days": 0,
                "closed_days": 0,
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "currency": None,
                "best_deals": [],
                "availability_summary": "No data available"
            }
        
        total_days = len(calendar_data)
        available_days = 0
        closed_days = 0
        prices = []
        currency = None
        best_deals = []
        
        for day in calendar_data:
            # Count availability
            inventory_status = day.get("inventory_status", {})
            if inventory_status.get("status") == "open" and day.get("availability", 0) > 0:
                available_days += 1
            elif inventory_status.get("status") == "closed":
                closed_days += 1
            
            # Collect pricing information
            amounts = day.get("amounts", {})
            if amounts.get("final_amount") is not None:
                prices.append(amounts["final_amount"])
                if not currency:
                    currency = amounts.get("currency")
                
                # Identify potential best deals (lower prices with good availability)
                if day.get("availability", 0) > 0 and amounts["final_amount"] > 0:
                    best_deals.append({
                        "date": day.get("date"),
                        "price": amounts["final_amount"],
                        "availability": day.get("availability"),
                        "min_stay": day.get("min_stay")
                    })
        
        # Sort best deals by price
        best_deals.sort(key=lambda x: x["price"])
        best_deals = best_deals[:5]  # Top 5 best deals
        
        # Calculate statistics
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None
        avg_price = sum(prices) / len(prices) if prices else None
        
        # Generate availability summary
        availability_percentage = (available_days / total_days * 100) if total_days > 0 else 0
        if availability_percentage >= 70:
            availability_summary = "Excellent availability"
        elif availability_percentage >= 50:
            availability_summary = "Good availability"
        elif availability_percentage >= 30:
            availability_summary = "Limited availability"
        else:
            availability_summary = "Very limited availability"
        
        return {
            "total_days": total_days,
            "available_days": available_days,
            "closed_days": closed_days,
            "unavailable_days": total_days - available_days - closed_days,
            "availability_percentage": round(availability_percentage, 1),
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": round(avg_price, 2) if avg_price else None,
            "currency": currency,
            "best_deals": best_deals,
            "availability_summary": availability_summary
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the package calendar availability request.
        
        Args:
            arguments: Tool arguments containing calendar criteria
            
        Returns:
            Dictionary containing the calendar availability results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            date_from = arguments.get("date_from", "").strip()
            date_to = arguments.get("date_to", "").strip()
            adults = arguments.get("adults")
            hotel_ids = arguments.get("hotel_ids", [])
            package_ids = arguments.get("package_ids", [])
            hotel_room_ids = arguments.get("hotel_room_ids", [])
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_date_from, validated_date_to = self._validate_date_range(date_from, date_to)
            
            if not isinstance(adults, int) or adults < 1 or adults > 20:
                raise ValidationError("Adults must be between 1 and 20")
            
            validated_hotel_ids = self._validate_string_list(hotel_ids, "Hotel ID", 100)
            validated_package_ids = self._validate_string_list(package_ids, "Package ID", 100)
            validated_hotel_room_ids = self._validate_string_list(hotel_room_ids, "Hotel Room ID", 100)
            
            self.logger.info(
                "Retrieving package calendar availability",
                date_from=validated_date_from,
                date_to=validated_date_to,
                adults=adults,
                hotel_ids=len(validated_hotel_ids),
                package_ids=len(validated_package_ids),
                hotel_room_ids=len(validated_hotel_room_ids),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "DateFrom": validated_date_from,
                "DateTo": validated_date_to,
                "Adults": adults
            }
            
            # Add optional parameters
            if validated_hotel_ids:
                request_payload["HotelId"] = validated_hotel_ids
            if validated_package_ids:
                request_payload["PackageId"] = validated_package_ids
            if validated_hotel_room_ids:
                request_payload["HotelRoomId"] = validated_hotel_room_ids
            
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
                
                # Make the package calendar availability request
                response = await client.post("/PackageCalendarAvailRQ", request_payload)
            
            # Extract data from response
            calendar_data = response.get("PackageCalendarAvail", [])
            api_response = response.get("Response", {})
            
            # Format results
            formatted_calendar = self._format_calendar_availability(calendar_data)
            analysis = self._analyze_calendar_data(formatted_calendar)
            
            # Group data by package and hotel for better organization
            grouped_data = {}
            for day in formatted_calendar:
                key = f"{day['hotel_id']}_{day['package_id']}"
                if key not in grouped_data:
                    grouped_data[key] = {
                        "hotel_id": day["hotel_id"],
                        "package_id": day["package_id"],
                        "hotel_room_ids": day["hotel_room_ids"],
                        "days": []
                    }
                grouped_data[key]["days"].append(day)
            
            # Log successful operation
            self.logger.info(
                "Package calendar availability retrieved",
                total_days=analysis["total_days"],
                available_days=analysis["available_days"],
                packages_found=len(grouped_data),
                availability_percentage=analysis["availability_percentage"],
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "date_from": validated_date_from,
                    "date_to": validated_date_to,
                    "adults": adults,
                    "hotel_ids": validated_hotel_ids,
                    "package_ids": validated_package_ids,
                    "hotel_room_ids": validated_hotel_room_ids
                },
                "calendar_data": formatted_calendar,
                "grouped_data": list(grouped_data.values()),
                "analysis": analysis,
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved calendar data for {analysis['total_days']} days with {analysis['availability_percentage']}% availability"
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
handler = PackageCalendarAvailRQHandler()


async def call_package_calendar_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the PackageCalendarAvailRQ endpoint.
    
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
            analysis = data["analysis"]
            grouped_data = data["grouped_data"]
            calendar_data = data["calendar_data"]
            search_criteria = data["search_criteria"]
            
            response_text = f"""📅 **Package Calendar Availability**

📊 **Calendar Overview:**
- **Date Range**: {search_criteria['date_from']} to {search_criteria['date_to']}
- **Adults**: {search_criteria['adults']}
- **Total Days**: {analysis['total_days']}
- **Available Days**: {analysis['available_days']} ({analysis['availability_percentage']}%)
- **Closed Days**: {analysis['closed_days']}
- **Unavailable Days**: {analysis['unavailable_days']}
- **Availability**: {analysis['availability_summary']}

"""
            
            # Pricing summary
            if analysis['min_price'] is not None:
                response_text += f"""💰 **Pricing Summary:**
- **Currency**: {analysis['currency']}
- **Minimum Price**: {analysis['min_price']} {analysis['currency']}
- **Maximum Price**: {analysis['max_price']} {analysis['currency']}
- **Average Price**: {analysis['avg_price']} {analysis['currency']}

"""
            
            # Best deals
            if analysis['best_deals']:
                response_text += f"""🎯 **Best Deals (Top {len(analysis['best_deals'])}):**
"""
                for i, deal in enumerate(analysis['best_deals'], 1):
                    response_text += f"""
{i}. **{deal['date']}**
   - Price: {deal['price']} {analysis['currency']}
   - Availability: {deal['availability']} unit(s)
   - Min Stay: {deal['min_stay']} night(s)
"""
            
            # Package details by hotel
            if grouped_data:
                response_text += f"""
📦 **Package Calendar Details ({len(grouped_data)} package(s)):**
{'='*80}
"""
                
                for i, package_group in enumerate(grouped_data, 1):
                    days_data = package_group["days"]
                    available_days_count = sum(1 for day in days_data if day.get("availability", 0) > 0)
                    
                    response_text += f"""
📦 **Package #{i}**
{'-'*60}

🏷️ **Package Information:**
- **Hotel ID**: {package_group['hotel_id']}
- **Package ID**: {package_group['package_id']}
- **Room IDs**: {', '.join(package_group['hotel_room_ids']) if package_group['hotel_room_ids'] else 'N/A'}
- **Available Days**: {available_days_count} of {len(days_data)}

📅 **Daily Availability:**
"""
                    
                    # Group days by week for better readability
                    for j, day in enumerate(days_data[:14]):  # Show first 14 days
                        amounts = day.get("amounts", {})
                        inventory = day.get("inventory_status", {})
                        
                        status_icon = "✅" if day.get("availability", 0) > 0 else "❌"
                        if inventory.get("status") == "closed":
                            status_icon = "🚫"
                        
                        response_text += f"""
{status_icon} **{day['date']}**:
   - Availability: {day.get('availability', 0)} unit(s)
   - Price: {amounts.get('final_amount', 'N/A')} {amounts.get('currency', '')}
   - Min Stay: {day.get('min_stay', 'N/A')} night(s)
   - Release: {day.get('release', 'N/A')} day(s)
   - Status: {inventory.get('status', 'Unknown')}"""
                    
                    if len(days_data) > 14:
                        response_text += f"""
   ... and {len(days_data) - 14} more days"""
                    
                    response_text += "\n"
            
            else:
                response_text += """❌ **No Calendar Data Available**

No package calendar data was found for the specified criteria.

**Possible reasons:**
- No packages exist for the selected hotels
- Date range is outside available periods
- No packages configured for the specified criteria
- Packages may be temporarily unavailable
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use calendar data for booking date selection
- Look for best deals with lowest prices
- Check minimum stay requirements
- Consider release periods for booking timing
- Review availability trends for optimal pricing
- Use this data for package recommendation systems
"""
                
        else:
            response_text = f"""❌ **Package Calendar Availability Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify date range is valid and in the future
- Check that adult count is within valid range (1-20)
- Ensure hotel/package IDs exist and are valid
- Verify authentication credentials
- Check if packages are active and configured
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving package calendar availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
