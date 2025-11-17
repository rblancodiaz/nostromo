"""
HotelRoomExtraDetailsRQ - Hotel Room Extra Details Tool

This tool retrieves comprehensive detailed information about specific hotel room extras
including features, pricing types, restrictions, and service details.
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
HOTEL_ROOM_EXTRA_DETAILS_RQ_TOOL = Tool(
    name="hotel_room_extra_details_rq",
    description="""
    Retrieve comprehensive detailed information about specific hotel room extras.
    
    This tool provides complete extra service information including:
    - Extra service specifications and features
    - Pricing models and billing types
    - Availability restrictions and rules
    - Media content and descriptions
    - Mandatory vs. optional classification
    - Release times and minimum stay requirements
    - Hotel and room associations
    
    Parameters:
    - hotel_ids (optional): Specific hotel IDs to get room extras for
    - room_ids (optional): Specific room IDs to get extras for
    - extra_ids (optional): Specific extra IDs to get details for
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Complete extra service specifications
    - Pricing and billing information
    - Availability rules and restrictions
    - Media gallery content
    - Hotel and room associations
    - Service classifications
    
    Example usage:
    "Get detailed information for extra 'EXT123' in hotel 'HTL456'"
    "Show me complete details for all room extras in hotel 'HTL789'"
    "Retrieve extra specifications for room 'RM001'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to get room extras for",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 20
            },
            "room_ids": {
                "type": "array",
                "description": "List of room identifiers to get extras for",
                "items": {
                    "type": "string",
                    "description": "Room identifier"
                },
                "maxItems": 50
            },
            "extra_ids": {
                "type": "array",
                "description": "List of extra identifiers to get details for",
                "items": {
                    "type": "string",
                    "description": "Extra identifier"
                },
                "maxItems": 100
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "additionalProperties": False
    }
)


class HotelRoomExtraDetailsRQHandler:
    """Handler for the HotelRoomExtraDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_room_extra_details_rq")
    
    def _format_media(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format media information for readable output."""
        formatted = []
        for media in media_list:
            formatted.append({
                "type": media.get("MediaType"),
                "caption": media.get("Caption"),
                "url": media.get("Url"),
                "is_main": media.get("Main", False),
                "order": media.get("Order", 0)
            })
        return formatted
    
    def _format_room_extra_detail(self, extra_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format complete room extra detail information for readable output."""
        formatted = {
            "hotel_id": extra_detail.get("HotelId"),
            "hotel_hash": extra_detail.get("HotelHash"),
            "room_ids": extra_detail.get("HotelRoomId", []),
            "status": extra_detail.get("Status"),
            "extra_id": extra_detail.get("HotelExtraId"),
            "extra_name": extra_detail.get("HotelExtraName"),
            "extra_description": extra_detail.get("HotelExtraDescription"),
            "order": extra_detail.get("Order"),
            "release": extra_detail.get("Release"),
            "min_stay": extra_detail.get("MinStay"),
            "billing": extra_detail.get("Billing"),
            "hidden": extra_detail.get("Hidden", False),
            "mandatory": extra_detail.get("Mandatory", False)
        }
        
        # Format media
        media = extra_detail.get("Media", [])
        if media:
            formatted["media"] = self._format_media(media)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel room extra details request.
        
        Args:
            arguments: Tool arguments containing hotel/room/extra IDs
            
        Returns:
            Dictionary containing the room extra details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids", [])
            room_ids = arguments.get("room_ids", [])
            extra_ids = arguments.get("extra_ids", [])
            language = arguments.get("language", "es")
            
            # Validate that at least one filter is provided
            if not hotel_ids and not room_ids and not extra_ids:
                raise ValidationError("At least one hotel ID, room ID, or extra ID is required")
            
            # Sanitize IDs
            sanitized_hotel_ids = []
            if hotel_ids:
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            sanitized_room_ids = []
            if room_ids:
                for room_id in room_ids:
                    if not isinstance(room_id, str) or not room_id.strip():
                        raise ValidationError(f"Invalid room ID: {room_id}")
                    sanitized_room_ids.append(sanitize_string(room_id.strip()))
            
            sanitized_extra_ids = []
            if extra_ids:
                for extra_id in extra_ids:
                    if not isinstance(extra_id, str) or not extra_id.strip():
                        raise ValidationError(f"Invalid extra ID: {extra_id}")
                    sanitized_extra_ids.append(sanitize_string(extra_id.strip()))
            
            self.logger.info(
                "Retrieving room extra details",
                hotel_count=len(sanitized_hotel_ids),
                room_count=len(sanitized_room_ids),
                extra_count=len(sanitized_extra_ids),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            if sanitized_room_ids:
                request_payload["HotelRoomId"] = sanitized_room_ids
            if sanitized_extra_ids:
                request_payload["HotelRoomExtraId"] = sanitized_extra_ids
            
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
                
                # Make the room extra details request
                response = await client.post("/HotelRoomExtraDetailsRQ", request_payload)
            
            # Extract room extra details from response
            extra_details_raw = response.get("HotelRoomExtraDetail", [])
            
            # Format room extra details
            formatted_extras = []
            for extra_detail in extra_details_raw:
                formatted_extras.append(self._format_room_extra_detail(extra_detail))
            
            # Log successful operation
            self.logger.info(
                "Room extra details retrieved successfully",
                extra_count=len(formatted_extras),
                found_extras=len(extra_details_raw),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "extra_details": formatted_extras,
                "requested_hotel_ids": sanitized_hotel_ids,
                "requested_room_ids": sanitized_room_ids,
                "requested_extra_ids": sanitized_extra_ids,
                "found_count": len(formatted_extras),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "requested_hotels": len(sanitized_hotel_ids),
                    "requested_rooms": len(sanitized_room_ids),
                    "requested_extras": len(sanitized_extra_ids),
                    "found_count": len(formatted_extras),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {len(formatted_extras)} room extra(s)"
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
handler = HotelRoomExtraDetailsRQHandler()


async def call_hotel_room_extra_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelRoomExtraDetailsRQ endpoint.
    
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
            
            response_text = f"""🎯 **Hotel Room Extra Details Retrieved**

✅ **Summary:**
- **Hotels Requested**: {summary['requested_hotels']}
- **Rooms Requested**: {summary['requested_rooms']}
- **Extras Requested**: {summary['requested_extras']}
- **Extras Found**: {summary['found_count']}
- **Language**: {summary['language'].upper()}

"""
            
            # Display details for each extra
            for i, extra in enumerate(data["extra_details"], 1):
                response_text += f"""
{'='*70}
🎯 **Extra #{i}: {extra.get('extra_name', 'Unknown Extra')}**
{'='*70}

🏷️ **Basic Information:**
- **Extra ID**: {extra.get('extra_id', 'N/A')}
- **Hotel ID**: {extra.get('hotel_id', 'N/A')}
- **Name**: {extra.get('extra_name', 'N/A')}
- **Description**: {extra.get('extra_description', 'N/A')[:300]}{'...' if len(extra.get('extra_description', '')) > 300 else ''}
- **Status**: {extra.get('status', 'N/A').title()}
- **Order**: {extra.get('order', 'N/A')}
"""
                
                # Classification
                response_text += f"""
📋 **Classification:**
- **Mandatory**: {'Yes' if extra.get('mandatory') else 'No'}
- **Hidden**: {'Yes' if extra.get('hidden') else 'No'}
- **Billing Type**: {extra.get('billing', 'N/A')}
"""
                
                # Add billing type explanation
                billing_type = extra.get('billing', '').lower()
                billing_explanations = {
                    'day': 'Charged per day of stay',
                    'stay': 'Charged once per entire stay',
                    'unit': 'Charged per unit/item',
                    'person': 'Charged per person',
                    'unitday': 'Charged per unit per day',
                    'personday': 'Charged per person per day',
                    'personstay': 'Charged per person per stay'
                }
                
                if billing_type in billing_explanations:
                    response_text += f"  💡 **Billing Explanation**: {billing_explanations[billing_type]}\n"
                
                # Restrictions
                response_text += f"""
⏰ **Restrictions:**
- **Release Time**: {extra.get('release', 'N/A')} days in advance
- **Minimum Stay**: {extra.get('min_stay', 'N/A')} nights
"""
                
                # Room associations
                room_ids = extra.get('room_ids', [])
                if room_ids:
                    response_text += f"""
🏠 **Associated Rooms** ({len(room_ids)}):
"""
                    for room_id in room_ids[:10]:  # Show first 10 rooms
                        response_text += f"- {room_id}\n"
                    if len(room_ids) > 10:
                        response_text += f"... and {len(room_ids) - 10} more rooms\n"
                else:
                    response_text += f"""
🏠 **Room Association**: Available for all rooms in hotel
"""
                
                # Media
                media = extra.get('media', [])
                if media:
                    response_text += f"""
📸 **Media Gallery**: {len(media)} item(s)
"""
                    for media_item in media[:5]:  # Show first 5 media items
                        response_text += f"- {media_item['type'].title()}: {media_item.get('caption', 'No caption')}"
                        if media_item.get('is_main'):
                            response_text += " 🌟 (Main)"
                        response_text += "\n"
                    if len(media) > 5:
                        response_text += f"... and {len(media) - 5} more media items\n"
                
                # Status indicators
                response_text += f"""
📊 **Service Indicators:**
"""
                if extra.get('mandatory'):
                    response_text += "- 🔴 **Mandatory Service** - Required for all bookings\n"
                else:
                    response_text += "- 🟢 **Optional Service** - Can be added to booking\n"
                
                if extra.get('hidden'):
                    response_text += "- 👁️‍🗨️ **Hidden Service** - Not displayed in standard listings\n"
                else:
                    response_text += "- 👁️ **Visible Service** - Displayed in standard listings\n"
                
                response_text += f"- 📍 **Status**: {extra.get('status', 'Unknown').title()}\n"
                
                # Usage guidelines based on billing type
                response_text += f"""
💡 **Usage Guidelines:**
"""
                if billing_type == 'day':
                    response_text += "- Price multiplied by number of nights\n- Ideal for daily services like parking or WiFi\n"
                elif billing_type == 'stay':
                    response_text += "- Fixed price regardless of stay length\n- Ideal for one-time services or amenities\n"
                elif billing_type == 'person':
                    response_text += "- Price multiplied by number of guests\n- Ideal for per-person services\n"
                elif billing_type == 'unit':
                    response_text += "- Price per unit ordered\n- Ideal for consumables or equipment\n"
                elif billing_type in ['personday', 'unitday']:
                    response_text += "- Price multiplied by guests/units AND days\n- Ideal for daily per-person/unit services\n"
                elif billing_type == 'personstay':
                    response_text += "- Price per person for entire stay\n- Ideal for stay-long per-person services\n"
                
                # Booking recommendations
                release = extra.get('release', 0)
                min_stay = extra.get('min_stay', 0)
                
                if release > 0 or min_stay > 0:
                    response_text += f"""
⚠️ **Booking Requirements:**
"""
                    if release > 0:
                        response_text += f"- Must be booked at least {release} days in advance\n"
                    if min_stay > 0:
                        response_text += f"- Requires minimum stay of {min_stay} nights\n"
            
            # Group extras by hotel
            if len(data["extra_details"]) > 1:
                response_text += f"""
{'='*70}
📊 **EXTRAS BY HOTEL**
{'='*70}
"""
                
                # Group by hotel
                extras_by_hotel = {}
                for extra in data["extra_details"]:
                    hotel_id = extra.get("hotel_id", "Unknown")
                    if hotel_id not in extras_by_hotel:
                        extras_by_hotel[hotel_id] = []
                    extras_by_hotel[hotel_id].append(extra)
                
                for hotel_id, extras in extras_by_hotel.items():
                    mandatory_count = sum(1 for e in extras if e.get('mandatory'))
                    optional_count = len(extras) - mandatory_count
                    
                    response_text += f"""
🏨 **Hotel: {hotel_id}** ({len(extras)} extras)
- **Mandatory**: {mandatory_count}
- **Optional**: {optional_count}
- **Billing Types**: {', '.join(set(e.get('billing', 'N/A') for e in extras))}
"""
            
            # Service statistics
            if len(data["extra_details"]) > 1:
                response_text += f"""
{'='*70}
📈 **SERVICE STATISTICS**
{'='*70}
"""
                
                total_extras = len(data["extra_details"])
                mandatory_extras = sum(1 for e in data["extra_details"] if e.get('mandatory'))
                hidden_extras = sum(1 for e in data["extra_details"] if e.get('hidden'))
                
                # Count billing types
                billing_types = {}
                for extra in data["extra_details"]:
                    billing = extra.get('billing', 'Unknown')
                    billing_types[billing] = billing_types.get(billing, 0) + 1
                
                response_text += f"""
**Service Distribution:**
- **Total Extras**: {total_extras}
- **Mandatory**: {mandatory_extras} ({mandatory_extras/total_extras*100:.1f}%)
- **Optional**: {total_extras - mandatory_extras} ({(total_extras-mandatory_extras)/total_extras*100:.1f}%)
- **Hidden**: {hidden_extras} ({hidden_extras/total_extras*100:.1f}%)

**Billing Types:**
"""
                for billing_type, count in sorted(billing_types.items()):
                    percentage = count / total_extras * 100
                    response_text += f"- **{billing_type.title()}**: {count} ({percentage:.1f}%)\n"
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Check mandatory extras when calculating total costs
- Review billing types to understand pricing structure
- Consider release times when planning bookings
- Verify minimum stay requirements
- Use extra IDs for availability searches
- Contact hotel for special arrangements
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Room Extra Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel IDs, room IDs, and extra IDs exist
- Check your authentication credentials
- Ensure you have permission to view these extra details
- Verify the ID formats are correct
- Try requesting fewer items at once
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving room extra details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
