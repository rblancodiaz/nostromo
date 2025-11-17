"""
ZoneSearchRQ - Zone Search Tool

This tool retrieves a list of geographic zones available in the Neobookings system.
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
ZONE_SEARCH_RQ_TOOL = Tool(
    name="zone_search_rq",
    description="""
    Search and retrieve geographic zones available in the Neobookings system.
    
    This tool allows querying geographic zones, regions, and locations available
    for hotel searches and bookings. It returns detailed zone information including
    coordinates, hierarchical location data, and zone relationships.
    
    Parameters:
    - order_by (optional): Sort order for results (order/alphabetical)
    - order_type (optional): Sort direction (asc/desc)
    - language (optional): Language code for the request
    
    Returns:
    - List of available zones with detailed information
    - Geographic coordinates (latitude/longitude)
    - Zone hierarchy (country, state, main zone)
    - Zone ordering and classification
    
    Example usage:
    "List all available travel zones"
    "Get geographic zones for hotel search"
    "Retrieve destination zones alphabetically"
    "Search zones ordered by priority"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "order_by": {
                "type": "string",
                "description": "Sort order for the results",
                "enum": ["order", "alphabetical"],
                "default": "order"
            },
            "order_type": {
                "type": "string",
                "description": "Sort direction",
                "enum": ["asc", "desc"],
                "default": "asc"
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": [],
        "additionalProperties": False
    }
)


class ZoneSearchRQHandler:
    """Handler for the ZoneSearchRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="zone_search_rq")
    
    def _format_zone_details(self, zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format zone details for readable output."""
        formatted_zones = []
        
        for zone in zones:
            zone_info = zone.get("Zone", {})
            state_info = zone.get("State", {})
            country_info = zone.get("Country", {})
            main_zone_info = zone.get("MainZone", {})
            
            formatted_zone = {
                "coordinates": {
                    "latitude": zone.get("Latitude"),
                    "longitude": zone.get("Longitude")
                },
                "zone": {
                    "code": zone_info.get("Code"),
                    "name": zone_info.get("Name")
                },
                "state": {
                    "code": state_info.get("Code"),
                    "name": state_info.get("Name")
                },
                "country": {
                    "code": country_info.get("Code"),
                    "name": country_info.get("Name")
                },
                "main_zone": {
                    "code": main_zone_info.get("Code"),
                    "name": main_zone_info.get("Name")
                } if main_zone_info else None,
                "order": zone.get("Order")
            }
            
            formatted_zones.append(formatted_zone)
        
        return formatted_zones
    
    def _group_zones_by_country(self, zones: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group zones by country for better organization."""
        grouped_zones = {}
        
        for zone in zones:
            country_name = zone.get("country", {}).get("name", "Unknown")
            country_code = zone.get("country", {}).get("code", "XX")
            country_key = f"{country_name} ({country_code})"
            
            if country_key not in grouped_zones:
                grouped_zones[country_key] = []
            
            grouped_zones[country_key].append(zone)
        
        return grouped_zones
    
    def _group_zones_by_state(self, zones: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group zones by state for better organization."""
        grouped_zones = {}
        
        for zone in zones:
            state_name = zone.get("state", {}).get("name", "Unknown")
            state_code = zone.get("state", {}).get("code", "XX")
            state_key = f"{state_name} ({state_code})"
            
            if state_key not in grouped_zones:
                grouped_zones[state_key] = []
            
            grouped_zones[state_key].append(zone)
        
        return grouped_zones
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the zone search request.
        
        Args:
            arguments: Tool arguments containing search criteria
            
        Returns:
            Dictionary containing the zone search results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            order_by = arguments.get("order_by", "order")
            order_type = arguments.get("order_type", "asc")
            language = arguments.get("language", "es")
            
            self.logger.info(
                "Searching geographic zones",
                order_by=order_by,
                order_type=order_type,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"]
            }
            
            # Add optional parameters
            if order_by:
                request_payload["OrderBy"] = order_by
            if order_type:
                request_payload["OrderType"] = order_type
            
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
                
                # Make the zone search request
                response = await client.post("/ZoneSearchRQ", request_payload)
            
            # Extract data from response
            zone_details = response.get("ZoneDetail", [])
            api_response = response.get("Response", {})
            
            # Format results
            formatted_zones = self._format_zone_details(zone_details)
            
            # Group zones for better organization
            zones_by_country = self._group_zones_by_country(formatted_zones)
            zones_by_state = self._group_zones_by_state(formatted_zones)
            
            # Log successful operation
            self.logger.info(
                "Zone search completed successfully",
                zones_found=len(formatted_zones),
                countries=len(zones_by_country),
                states=len(zones_by_state),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "order_by": order_by,
                    "order_type": order_type,
                    "language": language
                },
                "zones": formatted_zones,
                "zones_by_country": zones_by_country,
                "zones_by_state": zones_by_state,
                "summary": {
                    "total_zones": len(formatted_zones),
                    "total_countries": len(zones_by_country),
                    "total_states": len(zones_by_state)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(formatted_zones)} geographic zones"
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
handler = ZoneSearchRQHandler()


async def call_zone_search_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the ZoneSearchRQ endpoint.
    
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
            zones = data["zones"]
            zones_by_country = data["zones_by_country"]
            zones_by_state = data["zones_by_state"]
            summary = data["summary"]
            search_criteria = data["search_criteria"]
            
            response_text = f"""🌍 **Geographic Zone Search Results**

📊 **Search Summary:**
- **Total Zones Found**: {summary['total_zones']}
- **Countries**: {summary['total_countries']}
- **States/Regions**: {summary['total_states']}
- **Order By**: {search_criteria['order_by'].title()}
- **Sort Direction**: {search_criteria['order_type'].upper()}
- **Language**: {search_criteria['language'].upper()}

"""
            
            if zones:
                # Show zones grouped by country
                response_text += f"""🌍 **Zones by Country ({len(zones_by_country)} countries):**
{'='*80}
"""
                
                for country, country_zones in zones_by_country.items():
                    response_text += f"""
🌍 **{country}** ({len(country_zones)} zones)
{'-'*60}
"""
                    
                    for zone in country_zones:
                        zone_info = zone.get("zone", {})
                        state_info = zone.get("state", {})
                        main_zone_info = zone.get("main_zone")
                        coordinates = zone.get("coordinates", {})
                        
                        response_text += f"""
📍 **{zone_info.get('name', 'N/A')}** ({zone_info.get('code', 'N/A')})
   • **State/Region**: {state_info.get('name', 'N/A')} ({state_info.get('code', 'N/A')})
"""
                        if main_zone_info:
                            response_text += f"   • **Main Zone**: {main_zone_info.get('name', 'N/A')} ({main_zone_info.get('code', 'N/A')})\n"
                        
                        if coordinates.get('latitude') and coordinates.get('longitude'):
                            response_text += f"   • **Coordinates**: {coordinates['latitude']}, {coordinates['longitude']}\n"
                        
                        if zone.get('order'):
                            response_text += f"   • **Order**: {zone['order']}\n"
                
                # Show summary by states if there are multiple states
                if len(zones_by_state) > 1:
                    response_text += f"""

🏛️ **Zones by State/Region ({len(zones_by_state)} states):**
{'='*80}
"""
                    
                    for state, state_zones in zones_by_state.items():
                        zone_names = [zone.get("zone", {}).get("name", "N/A") for zone in state_zones]
                        response_text += f"""
🏛️ **{state}** ({len(state_zones)} zones)
   Zones: {', '.join(zone_names)}
"""
                
                # Show detailed zone list if order_by is 'order'
                if search_criteria['order_by'] == 'order':
                    response_text += f"""

📋 **Zones by Priority Order:**
{'='*80}
"""
                    
                    sorted_zones = sorted(zones, key=lambda x: x.get('order', 999))
                    for i, zone in enumerate(sorted_zones[:20], 1):  # Show top 20
                        zone_info = zone.get("zone", {})
                        country_info = zone.get("country", {})
                        
                        response_text += f"""
{i:2d}. **{zone_info.get('name', 'N/A')}** ({zone_info.get('code', 'N/A')})
    📍 {country_info.get('name', 'N/A')} - Order: {zone.get('order', 'N/A')}
"""
                    
                    if len(zones) > 20:
                        response_text += f"\n... and {len(zones) - 20} more zones"
                
            else:
                response_text += f"""❌ **No Zones Found**

No geographic zones were found in the system.

🔍 **Possible Reasons:**
- System may be temporarily unavailable
- API configuration issues
- No zones configured in the system
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use zone codes for hotel search filters
- Zones are hierarchically organized (Country > State > Zone)
- Order by 'order' shows zones by business priority
- Order by 'alphabetical' shows zones alphabetically
- Use coordinates for map-based searches
- Main zones help group related destinations
"""
                
        else:
            response_text = f"""❌ **Zone Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Check authentication credentials
- Verify API access permissions
- Ensure network connectivity
- Try different sorting options
- Contact support if the issue persists

🌍 **About Geographic Zones:**
Geographic zones are used to organize destinations and hotels
by location hierarchy. They help filter search results and
provide location-based services in the booking system.
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching geographic zones:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
