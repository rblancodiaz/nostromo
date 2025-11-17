"""
HotelSearchRQ - Hotel Search Tool

This tool searches for hotels based on various criteria such as name, location,
category, and other filters to help find the most suitable accommodations.
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
HOTEL_SEARCH_RQ_TOOL = Tool(
    name="hotel_search_rq",
    description="""
    Search for hotels based on various criteria and filters.
    
    This tool allows comprehensive hotel searching with multiple filters:
    - Hotel name search (partial or complete matches)
    - Location-based filtering (country, zone)
    - Category and classification filtering
    - Pagination for large result sets
    
    Parameters:
    - hotel_names (optional): List of hotel names (partial matches allowed)
    - countries (optional): List of country codes (ISO 3166-1)
    - zones (optional): List of zone codes defined by Neobookings
    - hotel_categories (optional): List of minimum hotel category levels
    - page (optional): Page number for pagination (default: 1)
    - num_results (optional): Number of results per page (default: 25, max: 100)
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Matching hotels with basic information
    - Hotel details including location and category
    - Pagination information
    - Search result statistics
    
    Example usage:
    "Search for hotels in Spain"
    "Find hotels with name containing 'Palace'"
    "Search for 4-star hotels in Madrid zone"
    "Find hotels in zones MAD and BCN"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_names": {
                "type": "array",
                "description": "List of hotel names to search for (partial matches allowed)",
                "items": {
                    "type": "string",
                    "description": "Hotel name or partial name"
                },
                "maxItems": 10
            },
            "countries": {
                "type": "array",
                "description": "List of country codes (ISO 3166-1) to filter by",
                "items": {
                    "type": "string",
                    "description": "Country code (e.g., 'ES' for Spain, 'FR' for France)"
                },
                "maxItems": 10
            },
            "zones": {
                "type": "array",
                "description": "List of zone codes defined by Neobookings to filter by",
                "items": {
                    "type": "string",
                    "description": "Zone code (e.g., 'MAD' for Madrid, 'BCN' for Barcelona)"
                },
                "maxItems": 20
            },
            "hotel_categories": {
                "type": "array",
                "description": "List of minimum hotel category levels to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel category (e.g., '3', '4', '5')"
                },
                "maxItems": 5
            },
            "page": {
                "type": "integer",
                "description": "Page number for pagination (starts at 1)",
                "minimum": 1,
                "maximum": 1000,
                "default": 1
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results per page",
                "minimum": 1,
                "maximum": 100,
                "default": 25
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


class HotelSearchRQHandler:
    """Handler for the HotelSearchRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_search_rq")
    
    def _format_hotel_location(self, location: Dict[str, Any]) -> Dict[str, Any]:
        """Format hotel location information for readable output."""
        if not location:
            return {}
            
        formatted = {
            "address": location.get("Address"),
            "city": location.get("City"),
            "postal_code": location.get("PostalCode"),
            "latitude": location.get("Latitude"),
            "longitude": location.get("Longitude")
        }
        
        # Format zones
        zones = location.get("Zone", [])
        if zones:
            formatted["zones"] = []
            for zone in zones:
                formatted["zones"].append({
                    "code": zone.get("Code"),
                    "name": zone.get("Name")
                })
        
        # Format state
        state = location.get("State", {})
        if state:
            formatted["state"] = {
                "code": state.get("Code"),
                "name": state.get("Name")
            }
        
        # Format country
        country = location.get("Country", {})
        if country:
            formatted["country"] = {
                "code": country.get("Code"),
                "name": country.get("Name")
            }
        
        return formatted
    
    def _format_hotel_types(self, hotel_types: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format hotel types information for readable output."""
        formatted = []
        for hotel_type in hotel_types:
            formatted.append({
                "code": hotel_type.get("Code"),
                "name": hotel_type.get("Name")
            })
        return formatted
    
    def _format_hotel_categories(self, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format hotel categories information for readable output."""
        formatted = []
        for category in categories:
            formatted.append({
                "code": category.get("Code"),
                "name": category.get("Name")
            })
        return formatted
    
    def _format_guest_types(self, guest_types: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format guest types information for readable output."""
        formatted = []
        for guest_type in guest_types:
            formatted.append({
                "type": guest_type.get("GuestType"),
                "min_age": guest_type.get("MinAge"),
                "max_age": guest_type.get("MaxAge")
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
    
    def _format_hotel_basic(self, hotel: Dict[str, Any]) -> Dict[str, Any]:
        """Format hotel basic information for readable output."""
        formatted = {
            "hotel_id": hotel.get("HotelId"),
            "hotel_hash": hotel.get("HotelHash"),
            "hotel_name": hotel.get("HotelName"),
            "hotel_description": hotel.get("HotelDescription"),
            "currency": hotel.get("Currency"),
            "rewards": hotel.get("Rewards", False),
            "hotel_mode": hotel.get("HotelMode"),
            "hotel_view": hotel.get("HotelView"),
            "time_zone": hotel.get("TimeZone"),
            "opening_date": hotel.get("OpeningDate"),
            "closing_date": hotel.get("ClosingDate"),
            "reopening_date": hotel.get("ReopeningDate"),
            "first_day_with_price": hotel.get("FirstDayWithPrice")
        }
        
        # Format guest types
        guest_types = hotel.get("HotelGuestType", [])
        if guest_types:
            formatted["guest_types"] = self._format_guest_types(guest_types)
        
        # Format hotel types
        hotel_types = hotel.get("HotelType", [])
        if hotel_types:
            formatted["hotel_types"] = self._format_hotel_types(hotel_types)
        
        # Format hotel categories
        categories = hotel.get("HotelCategory", [])
        if categories:
            formatted["categories"] = self._format_hotel_categories(categories)
        
        # Format location
        location = hotel.get("HotelLocation", {})
        if location:
            formatted["location"] = self._format_hotel_location(location)
        
        # Format amenities
        amenities = hotel.get("HotelAmenity", [])
        if amenities:
            formatted["amenities"] = self._format_amenities(amenities)
        
        # Format media
        media = hotel.get("Media", [])
        if media:
            formatted["media"] = self._format_media(media)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel search request.
        
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
            hotel_names = arguments.get("hotel_names", [])
            countries = arguments.get("countries", [])
            zones = arguments.get("zones", [])
            hotel_categories = arguments.get("hotel_categories", [])
            page = arguments.get("page", 1)
            num_results = arguments.get("num_results", 25)
            language = arguments.get("language", "es")
            
            # Validate pagination parameters
            if page < 1:
                raise ValidationError("Page number must be at least 1")
            if num_results < 1 or num_results > 100:
                raise ValidationError("Number of results must be between 1 and 100")
            
            # Sanitize search terms
            sanitized_hotel_names = []
            if hotel_names:
                for name in hotel_names:
                    if not isinstance(name, str) or not name.strip():
                        raise ValidationError(f"Invalid hotel name: {name}")
                    sanitized_hotel_names.append(sanitize_string(name.strip()))
            
            sanitized_countries = []
            if countries:
                for country in countries:
                    if not isinstance(country, str) or not country.strip():
                        raise ValidationError(f"Invalid country code: {country}")
                    # Country codes should be 2-character ISO codes
                    country_code = country.strip().upper()
                    if len(country_code) != 2:
                        raise ValidationError(f"Country code must be 2 characters: {country}")
                    sanitized_countries.append(country_code)
            
            sanitized_zones = []
            if zones:
                for zone in zones:
                    if not isinstance(zone, str) or not zone.strip():
                        raise ValidationError(f"Invalid zone code: {zone}")
                    sanitized_zones.append(sanitize_string(zone.strip()))
            
            sanitized_categories = []
            if hotel_categories:
                for category in hotel_categories:
                    if not isinstance(category, str) or not category.strip():
                        raise ValidationError(f"Invalid hotel category: {category}")
                    sanitized_categories.append(sanitize_string(category.strip()))
            
            self.logger.info(
                "Performing hotel search",
                hotel_names_count=len(sanitized_hotel_names),
                countries_count=len(sanitized_countries),
                zones_count=len(sanitized_zones),
                categories_count=len(sanitized_categories),
                page=page,
                num_results=num_results,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            if sanitized_hotel_names:
                request_payload["HotelName"] = sanitized_hotel_names
            if sanitized_countries:
                request_payload["Country"] = sanitized_countries
            if sanitized_zones:
                request_payload["Zone"] = sanitized_zones
            if sanitized_categories:
                request_payload["HotelCategory"] = sanitized_categories
            if page > 1:
                request_payload["Page"] = page
            if num_results != 25:
                request_payload["NumResults"] = num_results
            
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
                
                # Make the hotel search request
                response = await client.post("/HotelSearchRQ", request_payload)
            
            # Extract search results from response
            hotels_raw = response.get("HotelBasicDetail", [])
            current_page = response.get("CurrentPage", 1)
            total_pages = response.get("TotalPages", 1)
            total_records = response.get("TotalRecords", 0)
            
            # Format hotel results
            formatted_hotels = []
            for hotel in hotels_raw:
                formatted_hotels.append(self._format_hotel_basic(hotel))
            
            # Log successful operation
            self.logger.info(
                "Hotel search completed successfully",
                found_hotels=len(formatted_hotels),
                total_records=total_records,
                current_page=current_page,
                total_pages=total_pages,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "hotels": formatted_hotels,
                "pagination": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "total_records": total_records,
                    "results_per_page": num_results,
                    "has_next_page": current_page < total_pages,
                    "has_previous_page": current_page > 1
                },
                "search_criteria": {
                    "hotel_names": sanitized_hotel_names,
                    "countries": sanitized_countries,
                    "zones": sanitized_zones,
                    "categories": sanitized_categories,
                    "language": language
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_found": total_records,
                    "returned_count": len(formatted_hotels),
                    "page": current_page,
                    "total_pages": total_pages,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {total_records} hotel(s), showing page {current_page} of {total_pages}"
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
handler = HotelSearchRQHandler()


async def call_hotel_search_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelSearchRQ endpoint.
    
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
            pagination = data["pagination"]
            criteria = data["search_criteria"]
            
            response_text = f"""🔍 **Hotel Search Results**

✅ **Search Summary:**
- **Total Hotels Found**: {summary['total_found']:,}
- **Returned This Page**: {summary['returned_count']}
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Language**: {summary['language'].upper()}

📋 **Search Criteria:**
"""
            if criteria["hotel_names"]:
                response_text += f"- **Hotel Names**: {', '.join(criteria['hotel_names'])}\n"
            if criteria["countries"]:
                response_text += f"- **Countries**: {', '.join(criteria['countries'])}\n"
            if criteria["zones"]:
                response_text += f"- **Zones**: {', '.join(criteria['zones'])}\n"
            if criteria["categories"]:
                response_text += f"- **Categories**: {', '.join(criteria['categories'])}\n"
            
            if not any([criteria["hotel_names"], criteria["countries"], criteria["zones"], criteria["categories"]]):
                response_text += "- **No specific filters applied** (showing all hotels)\n"
            
            response_text += f"""
📄 **Pagination:**
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Results Per Page**: {pagination['results_per_page']}
- **Has Next Page**: {'Yes' if pagination['has_next_page'] else 'No'}
- **Has Previous Page**: {'Yes' if pagination['has_previous_page'] else 'No'}

"""
            
            # Display hotel results
            if data["hotels"]:
                response_text += f"""🏨 **Hotels Found ({len(data['hotels'])} on this page):**
{'='*80}
"""
                
                for i, hotel in enumerate(data["hotels"], 1):
                    response_text += f"""
🏨 **Hotel #{i}: {hotel.get('hotel_name', 'Unknown Hotel')}**
{'-'*60}

🏷️ **Basic Information:**
- **Hotel ID**: {hotel.get('hotel_id', 'N/A')}
- **Name**: {hotel.get('hotel_name', 'N/A')}
- **Description**: {hotel.get('hotel_description', 'N/A')[:150]}{'...' if len(hotel.get('hotel_description', '')) > 150 else ''}
- **Currency**: {hotel.get('currency', 'N/A')}
- **Mode**: {hotel.get('hotel_mode', 'N/A').title() if hotel.get('hotel_mode') else 'N/A'}
- **View**: {hotel.get('hotel_view', 'N/A').title() if hotel.get('hotel_view') else 'N/A'}
- **Time Zone**: {hotel.get('time_zone', 'N/A')}
- **Rewards Program**: {'Yes' if hotel.get('rewards') else 'No'}
"""
                    
                    # Location information
                    location = hotel.get('location', {})
                    if location:
                        response_text += f"""
📍 **Location:**
- **Address**: {location.get('address', 'N/A')}
- **City**: {location.get('city', 'N/A')}
- **Postal Code**: {location.get('postal_code', 'N/A')}
- **Coordinates**: {location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}
"""
                        
                        # Country information
                        country = location.get('country', {})
                        if country:
                            response_text += f"- **Country**: {country.get('name', 'N/A')} ({country.get('code', 'N/A')})\n"
                        
                        # State information
                        state = location.get('state', {})
                        if state:
                            response_text += f"- **State/Region**: {state.get('name', 'N/A')} ({state.get('code', 'N/A')})\n"
                        
                        # Zones
                        zones = location.get('zones', [])
                        if zones:
                            zone_names = [f"{zone['name']} ({zone['code']})" for zone in zones]
                            response_text += f"- **Zones**: {', '.join(zone_names)}\n"
                    
                    # Hotel types
                    hotel_types = hotel.get('hotel_types', [])
                    if hotel_types:
                        type_names = [f"{ht['name']} ({ht['code']})" for ht in hotel_types]
                        response_text += f"""
🏢 **Hotel Types**: {', '.join(type_names)}
"""
                    
                    # Categories
                    categories = hotel.get('categories', [])
                    if categories:
                        category_names = [f"{cat['name']} ({cat['code']})" for cat in categories]
                        response_text += f"""
⭐ **Categories**: {', '.join(category_names)}
"""
                    
                    # Guest types
                    guest_types = hotel.get('guest_types', [])
                    if guest_types:
                        response_text += f"""
👥 **Accepted Guest Types**:
"""
                        for guest_type in guest_types:
                            response_text += f"- **{guest_type['type'].upper()}**: Ages {guest_type['min_age']}-{guest_type['max_age']}\n"
                    
                    # Amenities (show first 10)
                    amenities = hotel.get('amenities', [])
                    if amenities:
                        response_text += f"""
🎯 **Amenities** ({len(amenities)} available):
"""
                        for amenity in amenities[:10]:
                            response_text += f"- {amenity['name']}"
                            if amenity['filterable']:
                                response_text += " 🔍"
                            response_text += "\n"
                        if len(amenities) > 10:
                            response_text += f"... and {len(amenities) - 10} more amenities\n"
                    
                    # Media
                    media = hotel.get('media', [])
                    if media:
                        response_text += f"""
📸 **Media**: {len(media)} item(s)
"""
                        for media_item in media[:3]:
                            response_text += f"- {media_item['type'].title()}: {media_item.get('caption', 'No caption')}"
                            if media_item.get('is_main'):
                                response_text += " 🌟 (Main)"
                            response_text += "\n"
                        if len(media) > 3:
                            response_text += f"... and {len(media) - 3} more media items\n"
                    
                    # Dates
                    if hotel.get('opening_date'):
                        response_text += f"- **Opening Date**: {hotel['opening_date']}\n"
                    if hotel.get('closing_date'):
                        response_text += f"- **Closing Date**: {hotel['closing_date']}\n"
                    if hotel.get('reopening_date'):
                        response_text += f"- **Reopening Date**: {hotel['reopening_date']}\n"
                    if hotel.get('first_day_with_price'):
                        response_text += f"- **First Day with Price**: {hotel['first_day_with_price']}\n"
                    
                    response_text += "\n"
            
            else:
                response_text += """
❌ **No Hotels Found**

No hotels match your search criteria. Try:
- Broadening your search terms
- Removing some filters
- Checking spelling of hotel names
- Using different zone or country codes
"""
            
            # Navigation hints
            if pagination["has_next_page"] or pagination["has_previous_page"]:
                response_text += f"""
🧭 **Navigation:**
"""
                if pagination["has_previous_page"]:
                    response_text += f"- Use page {pagination['current_page'] - 1} to see previous results\n"
                if pagination["has_next_page"]:
                    response_text += f"- Use page {pagination['current_page'] + 1} to see more results\n"
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use hotel IDs for availability searches
- Refine searches with specific zones or categories
- Check hotel amenities for guest requirements
- Review location details for convenience
- Consider pagination for large result sets
"""
        else:
            response_text = f"""❌ **Hotel Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Check your search criteria format
- Verify country codes are valid (2-letter ISO codes)
- Ensure zone codes exist in the system
- Try simplifying your search criteria
- Check your authentication credentials
- Verify pagination parameters are within limits
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching for hotels:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
