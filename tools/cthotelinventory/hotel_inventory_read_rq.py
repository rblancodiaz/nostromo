"""
HotelInventoryReadRQ - Read Hotel Inventory Tool

This tool retrieves inventory information for hotel rooms,
including availability, quotas, pricing, and restrictions.
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
HOTEL_INVENTORY_READ_RQ_TOOL = Tool(
    name="hotel_inventory_read_rq",
    description="""
    Retrieve comprehensive inventory information for hotel rooms within a date range.
    
    This tool provides detailed inventory data including:
    - Room availability and quotas
    - Minimum and maximum stay restrictions
    - Release requirements (advance booking days)
    - Inventory status (open/closed)
    - Stop sale information
    - Daily inventory details per room type
    
    Parameters:
    - hotel_ids (optional): List of hotel identifiers to get inventory for
    - date_from (required): Start date for inventory period (YYYY-MM-DD)
    - date_to (required): End date for inventory period (YYYY-MM-DD)
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Hotel inventory details by date range
    - Room availability and restrictions
    - Inventory status information
    - Stop sale conditions
    
    Example usage:
    "Get inventory for hotel 'HTL123' from 2024-03-01 to 2024-03-31"
    "Show room availability for all hotels between March 1st and March 15th 2024"
    "Check inventory restrictions for hotels 'HTL123' and 'HTL456' next week"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to get inventory for (optional - if not provided, returns for all accessible hotels)",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 50
            },
            "date_from": {
                "type": "string",
                "description": "Start date for inventory period in YYYY-MM-DD format",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "date_to": {
                "type": "string", 
                "description": "End date for inventory period in YYYY-MM-DD format",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["date_from", "date_to"],
        "additionalProperties": False
    }
)


class HotelInventoryReadRQHandler:
    """Handler for the HotelInventoryReadRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_inventory_read_rq")
    
    def _format_inventory_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Format inventory status information for readable output."""
        if not status:
            return {}
            
        formatted = {
            "status": status.get("Status"),
            "restriction": status.get("Restriction")
        }
        
        # Format stop sale information
        stop_sale = status.get("StopSale", {})
        if stop_sale:
            formatted["stop_sale"] = {
                "code": stop_sale.get("Code"),
                "name": stop_sale.get("Name")
            }
        
        return formatted
    
    def _format_room_inventory_detail(self, detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format room inventory detail for readable output."""
        return {
            "date": detail.get("Date"),
            "availability": detail.get("Availability"),
            "quota": detail.get("Quota"),
            "min_stay": detail.get("MinStay"),
            "max_stay": detail.get("MaxStay"),
            "release": detail.get("Release"),
            "inventory_status": self._format_inventory_status(detail.get("HotelInventoryStatus", {}))
        }
    
    def _format_room_inventory(self, room_inventory: Dict[str, Any]) -> Dict[str, Any]:
        """Format complete room inventory information for readable output."""
        formatted = {}
        
        # Format basic room details
        room_basic = room_inventory.get("HotelRoomBasicDetail", {})
        if room_basic:
            formatted["room_info"] = {
                "hotel_id": room_basic.get("HotelId"),
                "hotel_hash": room_basic.get("HotelHash"),
                "hotel_name": room_basic.get("HotelName"),
                "room_id": room_basic.get("HotelRoomId"),
                "room_name": room_basic.get("HotelRoomName"),
                "room_description": room_basic.get("HotelRoomDescription"),
                "room_area": room_basic.get("HotelRoomArea"),
                "hidden": room_basic.get("Hidden", False),
                "order": room_basic.get("Order", 0),
                "upgrade_class": room_basic.get("UpgradeClass"),
                "upgrade_allowed": room_basic.get("UpgradeAllowed")
            }
        
        # Format inventory details by date
        inventory_details = room_inventory.get("HotelRoomInventoryDetail", [])
        if inventory_details:
            formatted["inventory_details"] = []
            for detail in inventory_details:
                formatted["inventory_details"].append(self._format_room_inventory_detail(detail))
        
        return formatted
    
    def _format_hotel_inventory(self, hotel_inventory: Dict[str, Any]) -> Dict[str, Any]:
        """Format complete hotel inventory information for readable output."""
        formatted = {
            "hotel_id": hotel_inventory.get("HotelId"),
            "hotel_hash": hotel_inventory.get("HotelHash")
        }
        
        # Format room inventories
        room_inventories = hotel_inventory.get("HotelRoomInventory", [])
        if room_inventories:
            formatted["rooms"] = []
            for room_inventory in room_inventories:
                formatted["rooms"].append(self._format_room_inventory(room_inventory))
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel inventory read request.
        
        Args:
            arguments: Tool arguments containing date range and optional hotel IDs
            
        Returns:
            Dictionary containing the hotel inventory information
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids")
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            language = arguments.get("language", "es")
            
            # Validate required fields
            if not date_from:
                raise ValidationError("date_from is required")
            if not date_to:
                raise ValidationError("date_to is required")
            
            # Validate and parse dates
            date_from = parse_date(date_from)
            date_to = parse_date(date_to)
            
            # Validate date range
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
            
            if date_from_obj >= date_to_obj:
                raise ValidationError("date_from must be before date_to")
            
            # Check date range is not too large (max 1 year)
            date_diff = (date_to_obj - date_from_obj).days
            if date_diff > 365:
                raise ValidationError("Date range cannot exceed 365 days")
            
            # Validate and sanitize hotel IDs if provided
            sanitized_hotel_ids = None
            if hotel_ids:
                if not isinstance(hotel_ids, list):
                    raise ValidationError("hotel_ids must be a list")
                
                sanitized_hotel_ids = []
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            self.logger.info(
                "Reading hotel inventory",
                hotel_count=len(sanitized_hotel_ids) if sanitized_hotel_ids else "all",
                date_from=date_from,
                date_to=date_to,
                date_range_days=date_diff,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload["DateFrom"] = date_from
            request_payload["DateTo"] = date_to
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            
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
                
                # Make the hotel inventory read request
                response = await client.post("/HotelInventoryReadRQ", request_payload)
            
            # Extract hotel inventory from response
            hotel_inventories_raw = response.get("HotelInventory", [])
            
            # Format hotel inventories
            formatted_inventories = []
            for hotel_inventory in hotel_inventories_raw:
                formatted_inventories.append(self._format_hotel_inventory(hotel_inventory))
            
            # Log successful operation
            self.logger.info(
                "Hotel inventory read successfully",
                hotel_count=len(formatted_inventories),
                date_from=date_from,
                date_to=date_to,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "hotel_inventories": formatted_inventories,
                "date_range": {
                    "from": date_from,
                    "to": date_to,
                    "days": date_diff
                },
                "requested_hotel_ids": sanitized_hotel_ids,
                "found_count": len(formatted_inventories),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "hotels_found": len(formatted_inventories),
                    "date_range_days": date_diff,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved inventory for {len(formatted_inventories)} hotel(s) over {date_diff} days"
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
handler = HotelInventoryReadRQHandler()


async def call_hotel_inventory_read_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelInventoryReadRQ endpoint.
    
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
            date_range = data["date_range"]
            
            response_text = f"""📊 **Hotel Inventory Report**

✅ **Summary:**
- **Hotels Found**: {summary['hotels_found']}
- **Date Range**: {date_range['from']} to {date_range['to']} ({date_range['days']} days)
- **Language**: {summary['language'].upper()}

"""
            
            # Display inventory for each hotel
            for i, hotel in enumerate(data["hotel_inventories"], 1):
                room_info = hotel.get("room_info", {})
                response_text += f"""
{'='*70}
🏨 **Hotel #{i}: {room_info.get('hotel_name', 'Unknown Hotel')}**
{'='*70}

🏷️ **Hotel Information:**
- **Hotel ID**: {hotel.get('hotel_id', 'N/A')}
- **Hotel Hash**: {hotel.get('hotel_hash', 'N/A')}

"""
                
                # Display room inventories
                rooms = hotel.get("rooms", [])
                if rooms:
                    for room_idx, room in enumerate(rooms, 1):
                        room_info = room.get("room_info", {})
                        inventory_details = room.get("inventory_details", [])
                        
                        response_text += f"""
🛏️ **Room #{room_idx}: {room_info.get('room_name', 'Unknown Room')}**

📋 **Room Details:**
- **Room ID**: {room_info.get('room_id', 'N/A')}
- **Description**: {room_info.get('room_description', 'N/A')[:100]}{'...' if len(room_info.get('room_description', '')) > 100 else ''}
- **Area**: {room_info.get('room_area', 'N/A')} m²
- **Order**: {room_info.get('order', 'N/A')}
- **Upgrade Class**: {room_info.get('upgrade_class', 'N/A')}
- **Upgrade Allowed**: {room_info.get('upgrade_allowed', 'N/A').title()}
- **Hidden**: {'Yes' if room_info.get('hidden') else 'No'}

"""
                        
                        if inventory_details:
                            response_text += f"""📅 **Daily Inventory ({len(inventory_details)} days):**

| Date       | Avail | Quota | MinStay | MaxStay | Release | Status     |
|------------|-------|-------|---------|---------|---------|------------|
"""
                            
                            for detail in inventory_details[:20]:  # Show first 20 days
                                date = detail.get("date", "N/A")
                                availability = detail.get("availability", "N/A")
                                quota = detail.get("quota", "N/A")
                                min_stay = detail.get("min_stay", "N/A")
                                max_stay = detail.get("max_stay", "N/A")
                                release = detail.get("release", "N/A")
                                
                                inventory_status = detail.get("inventory_status", {})
                                status = inventory_status.get("status", "N/A")
                                
                                response_text += f"| {date} | {availability:>5} | {quota:>5} | {min_stay:>7} | {max_stay:>7} | {release:>7} | {status:<10} |\n"
                            
                            if len(inventory_details) > 20:
                                response_text += f"... and {len(inventory_details) - 20} more days\n"
                            
                            # Show status summary
                            status_summary = {}
                            restriction_summary = {}
                            for detail in inventory_details:
                                inventory_status = detail.get("inventory_status", {})
                                status = inventory_status.get("status", "unknown")
                                restriction = inventory_status.get("restriction")
                                
                                status_summary[status] = status_summary.get(status, 0) + 1
                                if restriction:
                                    restriction_summary[restriction] = restriction_summary.get(restriction, 0) + 1
                            
                            response_text += f"""
📊 **Inventory Status Summary:**
"""
                            for status, count in status_summary.items():
                                response_text += f"- **{status.title()}**: {count} days\n"
                            
                            if restriction_summary:
                                response_text += f"""
🚫 **Restrictions Summary:**
"""
                                for restriction, count in restriction_summary.items():
                                    response_text += f"- **{restriction.replace('closed', 'Closed ').title()}**: {count} days\n"
                            
                            # Calculate availability statistics
                            availabilities = [detail.get("availability", 0) for detail in inventory_details if isinstance(detail.get("availability"), (int, float))]
                            quotas = [detail.get("quota", 0) for detail in inventory_details if isinstance(detail.get("quota"), (int, float))]
                            
                            if availabilities:
                                avg_availability = sum(availabilities) / len(availabilities)
                                max_availability = max(availabilities)
                                min_availability = min(availabilities)
                                
                                response_text += f"""
📈 **Availability Statistics:**
- **Average**: {avg_availability:.1f} rooms
- **Maximum**: {max_availability} rooms
- **Minimum**: {min_availability} rooms
"""
                            
                            if quotas:
                                avg_quota = sum(quotas) / len(quotas)
                                max_quota = max(quotas)
                                min_quota = min(quotas)
                                
                                response_text += f"""
📊 **Quota Statistics:**
- **Average**: {avg_quota:.1f} rooms
- **Maximum**: {max_quota} rooms
- **Minimum**: {min_quota} rooms
"""
                        else:
                            response_text += f"""📅 **No inventory details available for this room.**
"""
                else:
                    response_text += f"""🛏️ **No rooms found for this hotel.**
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Hotel Inventory**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel IDs exist and are accessible
- Check your authentication credentials
- Ensure the date range is valid (YYYY-MM-DD format)
- Verify the date range is not too large (max 365 days)
- Check that date_from is before date_to
- Ensure you have permission to view inventory data
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while reading hotel inventory:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
