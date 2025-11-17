"""
HotelInventoryUpdateRQ - Update Hotel Inventory Tool

This tool updates hotel room inventory information including availability,
quotas, restrictions, and pricing for specific date ranges.
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
HOTEL_INVENTORY_UPDATE_RQ_TOOL = Tool(
    name="hotel_inventory_update_rq",
    description="""
    Update hotel room inventory information including availability, quotas, and restrictions.
    
    This tool allows updating inventory data such as:
    - Room availability and quotas
    - Minimum and maximum stay restrictions
    - Release requirements (advance booking days)
    - Stop sale settings (closed/open status)
    - Arrival/departure restrictions
    - Rate and board specific settings
    
    Parameters:
    - inventory_updates (required): List of inventory update objects
    - language (optional): Language code for the request (default: "es")
    
    Each inventory update object should contain:
    - hotel_id (required): Hotel identifier
    - room_id (required): Room identifier
    - date_from (required): Start date (YYYY-MM-DD)
    - date_to (required): End date (YYYY-MM-DD)
    - partner (required): Partner mapping settings
    - availability (optional): Room availability count
    - restrictions (optional): Stay and booking restrictions
    - rate_id (optional): Specific rate identifier
    - board_id (optional): Specific board identifier
    
    Returns:
    - Update operation success status
    - Processing results and confirmations
    
    Example usage:
    "Update availability for hotel 'HTL123' room 'RM456' to 10 rooms from 2024-03-01 to 2024-03-31"
    "Set minimum stay to 3 nights for hotel 'HTL123' room 'RM456' for next month"
    "Close sales for hotel 'HTL123' room 'RM456' from 2024-03-15 to 2024-03-20"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "inventory_updates": {
                "type": "array",
                "description": "List of inventory update operations to perform",
                "items": {
                    "type": "object",
                    "properties": {
                        "hotel_id": {
                            "type": "string",
                            "description": "Hotel identifier"
                        },
                        "room_id": {
                            "type": "string",
                            "description": "Room identifier"
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Start date for update period in YYYY-MM-DD format",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "date_to": {
                            "type": "string",
                            "description": "End date for update period in YYYY-MM-DD format",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "partner": {
                            "type": "object",
                            "description": "Partner mapping configuration",
                            "properties": {
                                "use_partner_mapping": {
                                    "type": "boolean",
                                    "description": "Whether to use partner ID mapping"
                                },
                                "partner_mapping_name": {
                                    "type": "string",
                                    "description": "Name of the partner mapping to use"
                                }
                            },
                            "required": ["use_partner_mapping"]
                        },
                        "availability": {
                            "type": "integer",
                            "description": "Room availability count",
                            "minimum": 0,
                            "maximum": 999
                        },
                        "restrictions": {
                            "type": "object",
                            "description": "Stay and booking restrictions",
                            "properties": {
                                "release": {
                                    "type": "integer",
                                    "description": "Maximum release days (advance booking requirement)",
                                    "minimum": 0,
                                    "maximum": 365
                                },
                                "min_stay": {
                                    "type": "integer",
                                    "description": "Minimum stay requirement in nights",
                                    "minimum": 1,
                                    "maximum": 90
                                },
                                "max_stay": {
                                    "type": "integer",
                                    "description": "Maximum stay limit in nights",
                                    "minimum": 1,
                                    "maximum": 365
                                },
                                "closed": {
                                    "type": "boolean",
                                    "description": "Whether sales are closed (stop sale)"
                                },
                                "closed_on_arrival": {
                                    "type": "boolean",
                                    "description": "Whether arrivals are closed"
                                },
                                "closed_on_departure": {
                                    "type": "boolean",
                                    "description": "Whether departures are closed"
                                }
                            }
                        },
                        "rate_id": {
                            "type": "string",
                            "description": "Specific rate identifier (optional)"
                        },
                        "board_id": {
                            "type": "string",
                            "description": "Specific board identifier (optional)"
                        }
                    },
                    "required": ["hotel_id", "room_id", "date_from", "date_to", "partner"]
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
        "required": ["inventory_updates"],
        "additionalProperties": False
    }
)


class HotelInventoryUpdateRQHandler:
    """Handler for the HotelInventoryUpdateRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_inventory_update_rq")
    
    def _validate_inventory_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize a single inventory update object."""
        # Validate required fields
        required_fields = ["hotel_id", "room_id", "date_from", "date_to", "partner"]
        for field in required_fields:
            if field not in update:
                raise ValidationError(f"Missing required field: {field}")
        
        # Sanitize and validate hotel and room IDs
        hotel_id = sanitize_string(update["hotel_id"])
        room_id = sanitize_string(update["room_id"])
        
        if not hotel_id:
            raise ValidationError("hotel_id cannot be empty")
        if not room_id:
            raise ValidationError("room_id cannot be empty")
        
        # Validate and parse dates
        date_from = parse_date(update["date_from"])
        date_to = parse_date(update["date_to"])
        
        # Validate date range
        from datetime import datetime
        date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
        date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
        
        if date_from_obj >= date_to_obj:
            raise ValidationError(f"date_from must be before date_to for hotel {hotel_id} room {room_id}")
        
        # Check date range is not too large (max 1 year)
        date_diff = (date_to_obj - date_from_obj).days
        if date_diff > 365:
            raise ValidationError(f"Date range cannot exceed 365 days for hotel {hotel_id} room {room_id}")
        
        # Validate partner configuration
        partner = update["partner"]
        if not isinstance(partner, dict):
            raise ValidationError("partner must be an object")
        
        if "use_partner_mapping" not in partner:
            raise ValidationError("partner.use_partner_mapping is required")
        
        # Build validated update object
        validated_update = {
            "HotelId": hotel_id,
            "RoomId": room_id,
            "DateFrom": date_from,
            "DateTo": date_to,
            "Partner": {
                "UsePartnerMapping": partner["use_partner_mapping"]
            }
        }
        
        # Add optional partner mapping name
        if "partner_mapping_name" in partner and partner["partner_mapping_name"]:
            validated_update["Partner"]["PartnerMappingName"] = sanitize_string(partner["partner_mapping_name"])
        
        # Add optional availability
        if "availability" in update and update["availability"] is not None:
            availability = update["availability"]
            if not isinstance(availability, int) or availability < 0:
                raise ValidationError(f"availability must be a non-negative integer for hotel {hotel_id} room {room_id}")
            validated_update["Avail"] = availability
        
        # Add optional restrictions
        if "restrictions" in update and update["restrictions"]:
            restrictions = update["restrictions"]
            restriction_obj = {}
            
            if "release" in restrictions and restrictions["release"] is not None:
                release = restrictions["release"]
                if not isinstance(release, int) or release < 0:
                    raise ValidationError(f"restrictions.release must be a non-negative integer for hotel {hotel_id} room {room_id}")
                restriction_obj["Release"] = release
            
            if "min_stay" in restrictions and restrictions["min_stay"] is not None:
                min_stay = restrictions["min_stay"]
                if not isinstance(min_stay, int) or min_stay < 1:
                    raise ValidationError(f"restrictions.min_stay must be a positive integer for hotel {hotel_id} room {room_id}")
                restriction_obj["MinStay"] = min_stay
            
            if "max_stay" in restrictions and restrictions["max_stay"] is not None:
                max_stay = restrictions["max_stay"]
                if not isinstance(max_stay, int) or max_stay < 1:
                    raise ValidationError(f"restrictions.max_stay must be a positive integer for hotel {hotel_id} room {room_id}")
                restriction_obj["MaxStay"] = max_stay
            
            if "closed" in restrictions and restrictions["closed"] is not None:
                restriction_obj["Closed"] = bool(restrictions["closed"])
            
            if "closed_on_arrival" in restrictions and restrictions["closed_on_arrival"] is not None:
                restriction_obj["ClosedOnArrival"] = bool(restrictions["closed_on_arrival"])
            
            if "closed_on_departure" in restrictions and restrictions["closed_on_departure"] is not None:
                restriction_obj["ClosedOnDeparture"] = bool(restrictions["closed_on_departure"])
            
            if restriction_obj:
                validated_update["Restriction"] = restriction_obj
        
        # Add optional rate and board IDs
        if "rate_id" in update and update["rate_id"]:
            validated_update["RateId"] = sanitize_string(update["rate_id"])
        
        if "board_id" in update and update["board_id"]:
            validated_update["BoardId"] = sanitize_string(update["board_id"])
        
        return validated_update
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel inventory update request.
        
        Args:
            arguments: Tool arguments containing inventory updates
            
        Returns:
            Dictionary containing the update operation results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            inventory_updates = arguments.get("inventory_updates", [])
            language = arguments.get("language", "es")
            
            # Validate inventory updates
            if not inventory_updates:
                raise ValidationError("At least one inventory update is required")
            
            if not isinstance(inventory_updates, list):
                raise ValidationError("inventory_updates must be a list")
            
            if len(inventory_updates) > 100:
                raise ValidationError("Cannot process more than 100 inventory updates at once")
            
            # Validate and sanitize each update
            validated_updates = []
            for i, update in enumerate(inventory_updates):
                try:
                    validated_update = self._validate_inventory_update(update)
                    validated_updates.append(validated_update)
                except ValidationError as e:
                    raise ValidationError(f"Inventory update #{i+1}: {e.message}")
            
            self.logger.info(
                "Updating hotel inventory",
                update_count=len(validated_updates),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload["InventoryUpdate"] = validated_updates
            
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
                
                # Make the hotel inventory update request
                response = await client.post("/HotelInventoryUpdateRQ", request_payload)
            
            # Extract success status from response
            success_status = response.get("Success", False)
            
            # Log successful operation
            self.logger.info(
                "Hotel inventory update completed",
                update_count=len(validated_updates),
                success=success_status,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "update_success": success_status,
                "updates_processed": len(validated_updates),
                "inventory_updates": validated_updates,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_updates": len(validated_updates),
                    "success": success_status,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Processed {len(validated_updates)} inventory update(s) with {'success' if success_status else 'warnings/errors'}"
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
handler = HotelInventoryUpdateRQHandler()


async def call_hotel_inventory_update_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelInventoryUpdateRQ endpoint.
    
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
            
            response_text = f"""📝 **Hotel Inventory Update Results**

✅ **Summary:**
- **Updates Processed**: {summary['total_updates']}
- **Update Success**: {'✅ Yes' if summary['success'] else '⚠️ With Warnings/Errors'}
- **Language**: {summary['language'].upper()}

"""
            
            # Display details for each update
            updates = data["inventory_updates"]
            for i, update in enumerate(updates, 1):
                response_text += f"""
{'='*50}
📋 **Update #{i}**
{'='*50}

🏨 **Target:**
- **Hotel ID**: {update.get('HotelId', 'N/A')}
- **Room ID**: {update.get('RoomId', 'N/A')}
- **Date Range**: {update.get('DateFrom', 'N/A')} to {update.get('DateTo', 'N/A')}
"""
                
                # Show rate and board if specified
                if update.get('RateId'):
                    response_text += f"- **Rate ID**: {update['RateId']}\n"
                if update.get('BoardId'):
                    response_text += f"- **Board ID**: {update['BoardId']}\n"
                
                # Show availability update
                if 'Avail' in update:
                    response_text += f"""
📊 **Availability Update:**
- **New Availability**: {update['Avail']} rooms
"""
                
                # Show restrictions
                restrictions = update.get('Restriction', {})
                if restrictions:
                    response_text += f"""
🚫 **Restriction Updates:**
"""
                    if 'Release' in restrictions:
                        response_text += f"- **Release Days**: {restrictions['Release']} days advance booking required\n"
                    if 'MinStay' in restrictions:
                        response_text += f"- **Minimum Stay**: {restrictions['MinStay']} nights\n"
                    if 'MaxStay' in restrictions:
                        response_text += f"- **Maximum Stay**: {restrictions['MaxStay']} nights\n"
                    if 'Closed' in restrictions:
                        response_text += f"- **Sales Status**: {'🔒 Closed (Stop Sale)' if restrictions['Closed'] else '🔓 Open'}\n"
                    if 'ClosedOnArrival' in restrictions:
                        response_text += f"- **Arrivals**: {'🔒 Closed' if restrictions['ClosedOnArrival'] else '🔓 Open'}\n"
                    if 'ClosedOnDeparture' in restrictions:
                        response_text += f"- **Departures**: {'🔒 Closed' if restrictions['ClosedOnDeparture'] else '🔓 Open'}\n"
                
                # Show partner configuration
                partner = update.get('Partner', {})
                if partner:
                    response_text += f"""
🤝 **Partner Configuration:**
- **Use Partner Mapping**: {'Yes' if partner.get('UsePartnerMapping') else 'No'}
"""
                    if partner.get('PartnerMappingName'):
                        response_text += f"- **Partner Name**: {partner['PartnerMappingName']}\n"
            
            # Show overall operation status
            if data["update_success"]:
                response_text += f"""

✅ **Operation Status: SUCCESS**

All inventory updates have been processed successfully. The changes have been applied to the hotel's availability and restrictions.

📋 **Next Steps:**
- Changes are now active in the booking system
- You can verify the updates using the Hotel Inventory Read tool
- Monitor booking patterns to assess impact
"""
            else:
                response_text += f"""

⚠️ **Operation Status: COMPLETED WITH WARNINGS**

The inventory updates have been processed, but there may have been warnings or partial failures. Please review the details above and check the system logs for more information.

📋 **Recommended Actions:**
- Verify the updates using the Hotel Inventory Read tool
- Check for any error notifications in the system
- Contact support if issues persist
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Update Hotel Inventory**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify all hotel and room IDs exist and are accessible
- Check your authentication credentials and permissions
- Ensure all date ranges are valid (YYYY-MM-DD format)
- Verify date_from is before date_to for all updates
- Check that availability values are non-negative integers
- Ensure restriction values are within valid ranges
- Verify you have inventory management permissions
- Check partner mapping configuration
- Contact support if the issue persists

📋 **Common Issues:**
- Invalid hotel or room IDs
- Date ranges exceeding 365 days
- Missing required partner configuration
- Insufficient permissions for inventory updates
- Conflicting restriction settings
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while updating hotel inventory:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
