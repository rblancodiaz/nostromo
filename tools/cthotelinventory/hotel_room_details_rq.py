"""
HotelRoomDetailsRQ - Hotel Room Details Tool

This tool retrieves comprehensive detailed information about specific hotel rooms
including features, amenities, occupancy rules, and media content.
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
HOTEL_ROOM_DETAILS_RQ_TOOL = Tool(
    name="hotel_room_details_rq",
    description="""
    Retrieve comprehensive detailed information about specific hotel rooms.
    
    This tool provides complete room information including:
    - Room specifications and features
    - Occupancy rules and guest restrictions
    - Amenities and services
    - Media gallery (photos, videos)
    - Room types and classifications
    - Accessibility features
    - Room text descriptions and vibes
    - Location within hotel
    - Upgrade possibilities
    
    Parameters:
    - hotel_ids (optional): Specific hotel IDs to get room details for
    - room_ids (optional): Specific room IDs to get details for
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Complete room specifications
    - Occupancy and guest type information
    - Amenities and feature listings
    - Media gallery content
    - Room classifications and types
    - Location and upgrade information
    
    Example usage:
    "Get detailed information for room 'RM123' in hotel 'HTL456'"
    "Show me complete details for all rooms in hotel 'HTL789'"
    "Retrieve room specifications for rooms 'RM001' and 'RM002'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to get room details for",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 20
            },
            "room_ids": {
                "type": "array",
                "description": "List of room identifiers to get details for",
                "items": {
                    "type": "string",
                    "description": "Room identifier"
                },
                "maxItems": 50
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


class HotelRoomDetailsRQHandler:
    """Handler for the HotelRoomDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_room_details_rq")
    
    def _format_room_types(self, room_types: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format room types information for readable output."""
        formatted = []
        for room_type in room_types:
            formatted.append({
                "code": room_type.get("Code"),
                "name": room_type.get("Name")
            })
        return formatted
    
    def _format_occupancy(self, occupancy: Dict[str, Any]) -> Dict[str, Any]:
        """Format occupancy information for readable output."""
        if not occupancy:
            return {}
            
        formatted = {
            "min": occupancy.get("Min"),
            "max": occupancy.get("Max")
        }
        
        # Format guest occupancy restrictions
        guest_occupancy = occupancy.get("HotelRoomGuestOccupancy", [])
        if guest_occupancy:
            formatted["guest_restrictions"] = []
            for restriction in guest_occupancy:
                formatted["guest_restrictions"].append({
                    "code": restriction.get("Code"),
                    "min_age": restriction.get("MinAge"),
                    "max_age": restriction.get("MaxAge"),
                    "min": restriction.get("Min"),
                    "max": restriction.get("Max")
                })
        
        return formatted
    
    def _format_guest_types(self, guest_types: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format guest types information for readable output."""
        formatted = []
        for guest_type in guest_types:
            formatted.append({
                "name": guest_type.get("Name"),
                "min_age": guest_type.get("MinAge"),
                "max_age": guest_type.get("MaxAge")
            })
        return formatted
    
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
    
    def _format_amenities(self, amenities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format amenities information for readable output."""
        formatted = []
        for amenity in amenities:
            formatted.append({
                "code": amenity.get("Code"),
                "name": amenity.get("Name"),
                "filterable": amenity.get("Filterable", False)
            })
        return formatted
    
    def _format_chain_features(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format chain features information for readable output."""
        formatted = []
        for feature in features:
            feature_formatted = {
                "id": feature.get("Id"),
                "code": feature.get("Code"),
                "name": feature.get("Name"),
                "restrictive": feature.get("Restrictive", False),
                "level": feature.get("Level"),
                "icon": feature.get("Icon"),
                "order": feature.get("Order")
            }
            
            # Format sub-features
            sub_features = feature.get("Features", [])
            if sub_features:
                feature_formatted["features"] = []
                for sub_feature in sub_features:
                    feature_formatted["features"].append({
                        "id": sub_feature.get("Id"),
                        "code": sub_feature.get("Code"),
                        "name": sub_feature.get("Name"),
                        "order": sub_feature.get("Order"),
                        "value": sub_feature.get("Value")
                    })
            
            formatted.append(feature_formatted)
        return formatted
    
    def _format_room_features(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format room features information for readable output."""
        formatted = []
        for feature in features:
            feature_formatted = {
                "code": feature.get("Code"),
                "name": feature.get("Name"),
                "restrictive": feature.get("Restrictive", False)
            }
            
            # Format sub-features
            sub_features = feature.get("Features", [])
            if sub_features:
                feature_formatted["features"] = []
                for sub_feature in sub_features:
                    feature_formatted["features"].append({
                        "id": sub_feature.get("Id"),
                        "code": sub_feature.get("Code"),
                        "name": sub_feature.get("Name"),
                        "order": sub_feature.get("Order"),
                        "value": sub_feature.get("Value")
                    })
            
            formatted.append(feature_formatted)
        return formatted
    
    def _format_room_texts(self, texts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format room texts information for readable output."""
        formatted = []
        for text in texts:
            formatted.append({
                "order": text.get("Order"),
                "title": text.get("Title"),
                "description": text.get("Description")
            })
        return formatted
    
    def _format_room_vibes(self, vibes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format room vibes information for readable output."""
        formatted = []
        for vibe in vibes:
            vibe_formatted = {
                "order": vibe.get("Order"),
                "title": vibe.get("Title"),
                "description": vibe.get("Description")
            }
            
            # Format vibe media
            vibe_media = vibe.get("Media", [])
            if vibe_media:
                vibe_formatted["media"] = []
                for media in vibe_media:
                    vibe_formatted["media"].append({
                        "type": media.get("MediaType"),
                        "url": media.get("Url"),
                        "is_main": media.get("Main", False),
                        "order": media.get("Order", 0),
                        "description": media.get("Description")
                    })
            
            formatted.append(vibe_formatted)
        return formatted
    
    def _format_location(self, location: Dict[str, Any]) -> Dict[str, Any]:
        """Format room location information for readable output."""
        if not location:
            return {}
            
        formatted = {
            "latitude": location.get("Latitude"),
            "longitude": location.get("Longitude"),
            "zoom": location.get("Zoom"),
            "view": location.get("View"),
            "poi": location.get("Poi", [])
        }
        
        return formatted
    
    def _format_room_detail(self, room_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format complete room detail information for readable output."""
        formatted = {
            "hotel_id": room_detail.get("HotelId"),
            "hotel_hash": room_detail.get("HotelHash"),
            "room_id": room_detail.get("HotelRoomId"),
            "room_group_id": room_detail.get("HotelRoomGroupId"),
            "room_group_leader_id": room_detail.get("HotelRoomGroupLeaderId"),
            "room_group_room_ids": room_detail.get("HotelRoomGroupRoomIds", []),
            "room_name": room_detail.get("HotelRoomName"),
            "room_description": room_detail.get("HotelRoomDescription"),
            "room_area": room_detail.get("HotelRoomArea"),
            "hidden": room_detail.get("Hidden", False),
            "order": room_detail.get("Order"),
            "upgrade_class": room_detail.get("UpgradeClass"),
            "upgrade_allowed": room_detail.get("UpgradeAllowed"),
            "first_day_with_price": room_detail.get("FirstDayWithPrice"),
            "parent_room_id": room_detail.get("HotelRoomParentId")
        }
        
        # Format room types
        room_types = room_detail.get("HotelRoomType", [])
        if room_types:
            formatted["room_types"] = self._format_room_types(room_types)
        
        # Format occupancy
        occupancy = room_detail.get("HotelRoomOccupancy", {})
        if occupancy:
            formatted["occupancy"] = self._format_occupancy(occupancy)
        
        # Format guest types
        guest_types = room_detail.get("HotelRoomGuestType", [])
        if guest_types:
            formatted["guest_types"] = self._format_guest_types(guest_types)
        
        # Format media
        media = room_detail.get("Media", [])
        if media:
            formatted["media"] = self._format_media(media)
        
        # Format amenities
        amenities = room_detail.get("HotelRoomAmenity", [])
        if amenities:
            formatted["amenities"] = self._format_amenities(amenities)
        
        # Format chain features
        chain_features = room_detail.get("HotelRoomChainFeature", [])
        if chain_features:
            formatted["chain_features"] = self._format_chain_features(chain_features)
        
        # Format room features
        room_features = room_detail.get("HotelRoomFeature", [])
        if room_features:
            formatted["room_features"] = self._format_room_features(room_features)
        
        # Format room texts
        room_texts = room_detail.get("HotelRoomText", [])
        if room_texts:
            formatted["room_texts"] = self._format_room_texts(room_texts)
        
        # Format room vibes
        room_vibes = room_detail.get("HotelRoomVibe", [])
        if room_vibes:
            formatted["room_vibes"] = self._format_room_vibes(room_vibes)
        
        # Format location
        location = room_detail.get("Location", {})
        if location:
            formatted["location"] = self._format_location(location)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel room details request.
        
        Args:
            arguments: Tool arguments containing hotel/room IDs
            
        Returns:
            Dictionary containing the room details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids", [])
            room_ids = arguments.get("room_ids", [])
            language = arguments.get("language", "es")
            
            # Validate that at least one filter is provided
            if not hotel_ids and not room_ids:
                raise ValidationError("At least one hotel ID or room ID is required")
            
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
            
            self.logger.info(
                "Retrieving room details",
                hotel_count=len(sanitized_hotel_ids),
                room_count=len(sanitized_room_ids),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            if sanitized_room_ids:
                request_payload["HotelRoomId"] = sanitized_room_ids
            
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
                
                # Make the room details request
                response = await client.post("/HotelRoomDetailsRQ", request_payload)
            
            # Extract room details from response
            room_details_raw = response.get("HotelRoomDetail", [])
            
            # Format room details
            formatted_rooms = []
            for room_detail in room_details_raw:
                formatted_rooms.append(self._format_room_detail(room_detail))
            
            # Log successful operation
            self.logger.info(
                "Room details retrieved successfully",
                room_count=len(formatted_rooms),
                found_rooms=len(room_details_raw),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "room_details": formatted_rooms,
                "requested_hotel_ids": sanitized_hotel_ids,
                "requested_room_ids": sanitized_room_ids,
                "found_count": len(formatted_rooms),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "requested_hotels": len(sanitized_hotel_ids),
                    "requested_rooms": len(sanitized_room_ids),
                    "found_count": len(formatted_rooms),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {len(formatted_rooms)} room(s)"
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
handler = HotelRoomDetailsRQHandler()


async def call_hotel_room_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelRoomDetailsRQ endpoint.
    
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
            
            response_text = f"""🏠 **Hotel Room Details Retrieved**

✅ **Summary:**
- **Hotels Requested**: {summary['requested_hotels']}
- **Rooms Requested**: {summary['requested_rooms']}
- **Rooms Found**: {summary['found_count']}
- **Language**: {summary['language'].upper()}

"""
            
            # Display details for each room
            for i, room in enumerate(data["room_details"], 1):
                response_text += f"""
{'='*70}
🏠 **Room #{i}: {room.get('room_name', 'Unknown Room')}**
{'='*70}

🏷️ **Basic Information:**
- **Room ID**: {room.get('room_id', 'N/A')}
- **Hotel ID**: {room.get('hotel_id', 'N/A')}
- **Name**: {room.get('room_name', 'N/A')}
- **Description**: {room.get('room_description', 'N/A')[:200]}{'...' if len(room.get('room_description', '')) > 200 else ''}
- **Area**: {room.get('room_area', 'N/A')} m²
- **Order**: {room.get('order', 'N/A')}
- **Hidden**: {'Yes' if room.get('hidden') else 'No'}
- **Upgrade Class**: {room.get('upgrade_class', 'N/A')}
- **Upgrade Allowed**: {room.get('upgrade_allowed', 'N/A')}
"""
                
                # Room types
                room_types = room.get('room_types', [])
                if room_types:
                    response_text += f"""
🏷️ **Room Types:**
"""
                    for room_type in room_types:
                        response_text += f"- **{room_type['code']}**: {room_type['name']}\n"
                
                # Occupancy information
                occupancy = room.get('occupancy', {})
                if occupancy:
                    response_text += f"""
👥 **Occupancy:**
- **Minimum**: {occupancy.get('min', 'N/A')} guests
- **Maximum**: {occupancy.get('max', 'N/A')} guests
"""
                    
                    guest_restrictions = occupancy.get('guest_restrictions', [])
                    if guest_restrictions:
                        response_text += f"**Guest Restrictions:**\n"
                        for restriction in guest_restrictions:
                            response_text += f"- **{restriction['code']}**: Ages {restriction['min_age']}-{restriction['max_age']}, {restriction['min']}-{restriction['max']} guests\n"
                
                # Guest types
                guest_types = room.get('guest_types', [])
                if guest_types:
                    response_text += f"""
👥 **Allowed Guest Types:**
"""
                    for guest_type in guest_types:
                        response_text += f"- **{guest_type['name']}**: Ages {guest_type['min_age']}-{guest_type['max_age']}\n"
                
                # Amenities
                amenities = room.get('amenities', [])
                if amenities:
                    response_text += f"""
🎯 **Room Amenities** ({len(amenities)} available):
"""
                    for amenity in amenities[:10]:  # Show first 10 amenities
                        response_text += f"- {amenity['name']}"
                        if amenity['filterable']:
                            response_text += " 🔍"
                        response_text += "\n"
                    if len(amenities) > 10:
                        response_text += f"... and {len(amenities) - 10} more amenities\n"
                
                # Chain features
                chain_features = room.get('chain_features', [])
                if chain_features:
                    response_text += f"""
⭐ **Chain Features** ({len(chain_features)} categories):
"""
                    for feature in chain_features[:5]:  # Show first 5 feature categories
                        response_text += f"- **{feature['name']}** (Level {feature.get('level', 'N/A')})"
                        if feature.get('restrictive'):
                            response_text += " 🚫 Restrictive"
                        response_text += "\n"
                        
                        # Show sub-features
                        sub_features = feature.get('features', [])
                        if sub_features:
                            for sub_feature in sub_features[:3]:  # Show first 3 sub-features
                                response_text += f"  - {sub_feature['name']}"
                                if sub_feature.get('value'):
                                    response_text += f" ({sub_feature['value']})"
                                response_text += "\n"
                    if len(chain_features) > 5:
                        response_text += f"... and {len(chain_features) - 5} more feature categories\n"
                
                # Room features
                room_features = room.get('room_features', [])
                if room_features:
                    response_text += f"""
🏠 **Room Features** ({len(room_features)} categories):
"""
                    for feature in room_features[:5]:  # Show first 5 feature categories
                        response_text += f"- **{feature['name']}**"
                        if feature.get('restrictive'):
                            response_text += " 🚫 Restrictive"
                        response_text += "\n"
                
                # Room texts
                room_texts = room.get('room_texts', [])
                if room_texts:
                    response_text += f"""
📝 **Room Descriptions:**
"""
                    for text in room_texts[:3]:  # Show first 3 texts
                        response_text += f"**{text['title']}**: {text['description'][:100]}{'...' if len(text['description']) > 100 else ''}\n"
                
                # Room vibes
                room_vibes = room.get('room_vibes', [])
                if room_vibes:
                    response_text += f"""
✨ **Room Vibes:**
"""
                    for vibe in room_vibes[:3]:  # Show first 3 vibes
                        response_text += f"**{vibe['title']}**: {vibe['description'][:100]}{'...' if len(vibe['description']) > 100 else ''}\n"
                        
                        vibe_media = vibe.get('media', [])
                        if vibe_media:
                            response_text += f"  📸 {len(vibe_media)} media item(s)\n"
                
                # Media
                media = room.get('media', [])
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
                
                # Location
                location = room.get('location', {})
                if location and any(location.values()):
                    response_text += f"""
📍 **Room Location:**
- **Coordinates**: {location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}
- **View**: {location.get('view', 'N/A')}
- **Zoom Level**: {location.get('zoom', 'N/A')}
"""
                    poi = location.get('poi', [])
                    if poi:
                        response_text += f"- **Points of Interest**: {', '.join(poi[:5])}{'...' if len(poi) > 5 else ''}\n"
                
                # Group information
                group_room_ids = room.get('room_group_room_ids', [])
                if group_room_ids:
                    response_text += f"""
🏠 **Room Group:**
- **Group ID**: {room.get('room_group_id', 'N/A')}
- **Leader Room**: {room.get('room_group_leader_id', 'N/A')}
- **Group Members**: {len(group_room_ids)} room(s)
"""
                
                # Parent room
                parent_room_id = room.get('parent_room_id')
                if parent_room_id:
                    response_text += f"""
👨‍👩‍👧‍👦 **Parent Room**: {parent_room_id}
"""
                
                # Dates
                first_day_with_price = room.get('first_day_with_price')
                if first_day_with_price:
                    response_text += f"""
📅 **First Day with Price**: {first_day_with_price}
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use room IDs for availability searches
- Check occupancy rules before booking
- Review amenities for guest preferences
- Consider upgrade possibilities
- Verify room features match requirements
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Room Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel IDs and room IDs exist
- Check your authentication credentials
- Ensure you have permission to view these room details
- Verify the ID formats are correct
- Try requesting fewer rooms at once
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving room details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
