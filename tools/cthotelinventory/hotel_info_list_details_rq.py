"""
HotelInfoListDetailsRQ - Get Hotel Info List Details Tool

This tool retrieves a comprehensive list of hotels and their associated components
(rooms, packages, products, rates, boards, offers, extras) in the Neobookings system.
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
HOTEL_INFO_LIST_DETAILS_RQ_TOOL = Tool(
    name="hotel_info_list_details_rq",
    description="""
    Retrieve comprehensive lists of hotels and all their associated components.
    
    This tool provides detailed listings including:
    - Hotel information (ID, name, code, zone)
    - Room information for each hotel
    - Package information
    - Generic product information
    - Rate information
    - Board information (meal plans)
    - Offer information
    - Extra information
    - Complete mappings and relationships
    
    Parameters:
    - hotel_ids (optional): List of hotel identifiers to filter by
    - show_hidden (optional): Include hidden items (default: false)
    - show_disabled (optional): Include disabled items (default: false)
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Complete hotel inventory listings
    - All associated rooms, packages, products, rates, boards, offers, and extras
    - Relationship mappings between components
    - Hierarchical organization of hotel data
    
    Example usage:
    "Get complete hotel inventory list"
    "Show me all hotels with their rooms and packages"
    "Retrieve hotel info including hidden and disabled items"
    "Get inventory details for hotel 'HTL123'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 100
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Include hidden items in the results",
                "default": False
            },
            "show_disabled": {
                "type": "boolean", 
                "description": "Include disabled items in the results",
                "default": False
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


class HotelInfoListDetailsRQHandler:
    """Handler for the HotelInfoListDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_info_list_details_rq")
    
    def _format_hotel_info(self, hotel_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format hotel information for readable output."""
        return {
            "hotel_hash": hotel_info.get("HotelHash"),
            "hotel_id": hotel_info.get("HotelId"),
            "hotel_name": hotel_info.get("HotelName"),
            "hotel_code": hotel_info.get("HotelCode"),
            "hotel_code_name": hotel_info.get("HotelCodeName"),
            "hotel_zone": hotel_info.get("HotelZone"),
            "hotel_zone_name": hotel_info.get("HotelZoneName"),
            "hotel_main_zone": hotel_info.get("HotelMainZone"),
            "hotel_main_zone_name": hotel_info.get("HotelMainZoneName")
        }
    
    def _format_room_info(self, room_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format room information for readable output."""
        return {
            "hotel_id": room_info.get("HotelId"),
            "room_id": room_info.get("RoomId"),
            "room_name": room_info.get("RoomName"),
            "room_code": room_info.get("RoomCode"),
            "room_code_name": room_info.get("RoomCodeName"),
            "room_parent_id": room_info.get("RoomParentId")
        }
    
    def _format_package_info(self, package_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format package information for readable output."""
        return {
            "hotel_id": package_info.get("HotelId"),
            "package_id": package_info.get("PackageId"),
            "package_name": package_info.get("PackageName")
        }
    
    def _format_generic_product_info(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format generic product information for readable output."""
        return {
            "hotel_id": product_info.get("HotelId"),
            "product_id": product_info.get("GenericProductId"),
            "product_name": product_info.get("GenericProductName")
        }
    
    def _format_rate_info(self, rate_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format rate information for readable output."""
        return {
            "hotel_id": rate_info.get("HotelId"),
            "rate_id": rate_info.get("RateId"),
            "rate_name": rate_info.get("RateName")
        }
    
    def _format_board_info(self, board_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format board information for readable output."""
        return {
            "hotel_id": board_info.get("HotelId"),
            "board_id": board_info.get("BoardId"),
            "board_name": board_info.get("BoardName"),
            "board_type_code": board_info.get("BoardTypeCode"),
            "board_type_name": board_info.get("BoardTypeName"),
            "board_type_description": board_info.get("BoardTypeDesc")
        }
    
    def _format_offer_info(self, offer_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format offer information for readable output."""
        return {
            "hotel_id": offer_info.get("HotelId"),
            "offer_id": offer_info.get("OfferId"),
            "offer_name": offer_info.get("OfferName")
        }
    
    def _format_extra_info(self, extra_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format extra information for readable output."""
        return {
            "hotel_id": extra_info.get("HotelId"),
            "extra_id": extra_info.get("ExtraId"),
            "extra_name": extra_info.get("ExtraName")
        }
    
    def _group_components_by_hotel(self, hotels: List[Dict[str, Any]], 
                                  rooms: List[Dict[str, Any]], 
                                  packages: List[Dict[str, Any]],
                                  products: List[Dict[str, Any]], 
                                  rates: List[Dict[str, Any]], 
                                  boards: List[Dict[str, Any]],
                                  offers: List[Dict[str, Any]], 
                                  extras: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group all components by hotel for better organization."""
        grouped = {}
        
        # Create hotel entries
        for hotel in hotels:
            hotel_id = hotel["hotel_id"]
            grouped[hotel_id] = {
                "hotel_info": hotel,
                "rooms": [],
                "packages": [],
                "products": [],
                "rates": [],
                "boards": [],
                "offers": [],
                "extras": []
            }
        
        # Group rooms by hotel
        for room in rooms:
            hotel_id = room["hotel_id"]
            if hotel_id in grouped:
                grouped[hotel_id]["rooms"].append(room)
        
        # Group packages by hotel
        for package in packages:
            hotel_id = package["hotel_id"]
            if hotel_id in grouped:
                grouped[hotel_id]["packages"].append(package)
        
        # Group products by hotel
        for product in products:
            hotel_id = product["hotel_id"]
            if hotel_id in grouped:
                grouped[hotel_id]["products"].append(product)
        
        # Group rates by hotel
        for rate in rates:
            hotel_id = rate["hotel_id"]
            if hotel_id in grouped:
                grouped[hotel_id]["rates"].append(rate)
        
        # Group boards by hotel
        for board in boards:
            hotel_id = board["hotel_id"]
            if hotel_id in grouped:
                grouped[hotel_id]["boards"].append(board)
        
        # Group offers by hotel
        for offer in offers:
            hotel_id = offer["hotel_id"]
            if hotel_id in grouped:
                grouped[hotel_id]["offers"].append(offer)
        
        # Group extras by hotel
        for extra in extras:
            hotel_id = extra["hotel_id"]
            if hotel_id in grouped:
                grouped[hotel_id]["extras"].append(extra)
        
        return grouped
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel info list details request.
        
        Args:
            arguments: Tool arguments containing filters and options
            
        Returns:
            Dictionary containing the hotel info list details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids", [])
            show_hidden = arguments.get("show_hidden", False)
            show_disabled = arguments.get("show_disabled", False)
            language = arguments.get("language", "es")
            
            # Validate and sanitize hotel IDs
            sanitized_hotel_ids = []
            if hotel_ids:
                if not isinstance(hotel_ids, list):
                    raise ValidationError("hotel_ids must be a list")
                
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            self.logger.info(
                "Retrieving hotel info list details",
                hotel_count=len(sanitized_hotel_ids),
                show_hidden=show_hidden,
                show_disabled=show_disabled,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload.update({
                "ShowHidden": show_hidden,
                "ShowDisabled": show_disabled
            })
            
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
                
                # Make the hotel info list details request
                response = await client.post("/HotelInfoListDetailsRQ", request_payload)
            
            # Extract information from response
            hotel_info_raw = response.get("HotelInfoListDetail", [])
            room_info_raw = response.get("RoomInfoListDetail", [])
            package_info_raw = response.get("PackageInfoListDetail", [])
            product_info_raw = response.get("GenericProductInfoListDetail", [])
            rate_info_raw = response.get("RateInfoListDetail", [])
            board_info_raw = response.get("BoardInfoListDetail", [])
            offer_info_raw = response.get("OfferInfoListDetail", [])
            extra_info_raw = response.get("ExtraInfoListDetail", [])
            
            # Format all information
            formatted_hotels = [self._format_hotel_info(hotel) for hotel in hotel_info_raw]
            formatted_rooms = [self._format_room_info(room) for room in room_info_raw]
            formatted_packages = [self._format_package_info(package) for package in package_info_raw]
            formatted_products = [self._format_generic_product_info(product) for product in product_info_raw]
            formatted_rates = [self._format_rate_info(rate) for rate in rate_info_raw]
            formatted_boards = [self._format_board_info(board) for board in board_info_raw]
            formatted_offers = [self._format_offer_info(offer) for offer in offer_info_raw]
            formatted_extras = [self._format_extra_info(extra) for extra in extra_info_raw]
            
            # Group components by hotel
            grouped_by_hotel = self._group_components_by_hotel(
                formatted_hotels, formatted_rooms, formatted_packages, formatted_products,
                formatted_rates, formatted_boards, formatted_offers, formatted_extras
            )
            
            # Log successful operation
            self.logger.info(
                "Hotel info list details retrieved successfully",
                hotel_count=len(formatted_hotels),
                room_count=len(formatted_rooms),
                package_count=len(formatted_packages),
                product_count=len(formatted_products),
                rate_count=len(formatted_rates),
                board_count=len(formatted_boards),
                offer_count=len(formatted_offers),
                extra_count=len(formatted_extras),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "hotels": formatted_hotels,
                "rooms": formatted_rooms,
                "packages": formatted_packages,
                "products": formatted_products,
                "rates": formatted_rates,
                "boards": formatted_boards,
                "offers": formatted_offers,
                "extras": formatted_extras,
                "grouped_by_hotel": grouped_by_hotel,
                "filters_applied": {
                    "hotel_ids": sanitized_hotel_ids,
                    "show_hidden": show_hidden,
                    "show_disabled": show_disabled
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_hotels": len(formatted_hotels),
                    "total_rooms": len(formatted_rooms),
                    "total_packages": len(formatted_packages),
                    "total_products": len(formatted_products),
                    "total_rates": len(formatted_rates),
                    "total_boards": len(formatted_boards),
                    "total_offers": len(formatted_offers),
                    "total_extras": len(formatted_extras),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved info for {len(formatted_hotels)} hotels with complete component listings"
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
handler = HotelInfoListDetailsRQHandler()


async def call_hotel_info_list_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelInfoListDetailsRQ endpoint.
    
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
            filters = data["filters_applied"]
            
            response_text = f"""🏨 **Hotel Info List Details Retrieved**

✅ **Summary:**
- **Total Hotels**: {summary['total_hotels']}
- **Total Rooms**: {summary['total_rooms']}
- **Total Packages**: {summary['total_packages']}
- **Total Products**: {summary['total_products']}
- **Total Rates**: {summary['total_rates']}
- **Total Boards**: {summary['total_boards']}
- **Total Offers**: {summary['total_offers']}
- **Total Extras**: {summary['total_extras']}
- **Language**: {summary['language'].upper()}

📋 **Filters Applied:**
- **Hotel Filter**: {', '.join(filters['hotel_ids']) if filters['hotel_ids'] else 'All hotels'}
- **Show Hidden**: {'Yes' if filters['show_hidden'] else 'No'}
- **Show Disabled**: {'Yes' if filters['show_disabled'] else 'No'}

"""
            
            # Display grouped information by hotel
            grouped_data = data["grouped_by_hotel"]
            if grouped_data:
                response_text += f"""
{'='*80}
🏨 **HOTEL INVENTORY BY HOTEL**
{'='*80}
"""
                
                for hotel_id, hotel_data in grouped_data.items():
                    hotel_info = hotel_data["hotel_info"]
                    components = {
                        "rooms": len(hotel_data["rooms"]),
                        "packages": len(hotel_data["packages"]),
                        "products": len(hotel_data["products"]),
                        "rates": len(hotel_data["rates"]),
                        "boards": len(hotel_data["boards"]),
                        "offers": len(hotel_data["offers"]),
                        "extras": len(hotel_data["extras"])
                    }
                    
                    response_text += f"""
🏨 **{hotel_info['hotel_name']}**
   **Hotel ID**: {hotel_id}
   **Zone**: {hotel_info.get('hotel_zone_name', 'N/A')} ({hotel_info.get('hotel_zone', 'N/A')})
   **Main Zone**: {hotel_info.get('hotel_main_zone_name', 'N/A')} ({hotel_info.get('hotel_main_zone', 'N/A')})
   **Code**: {hotel_info.get('hotel_code_name', 'N/A')} ({hotel_info.get('hotel_code', 'N/A')})

   🏠 **Inventory Summary:**
   - **Rooms**: {components['rooms']}
   - **Packages**: {components['packages']}
   - **Products**: {components['products']}
   - **Rates**: {components['rates']}
   - **Boards**: {components['boards']}
   - **Offers**: {components['offers']}
   - **Extras**: {components['extras']}
"""
                    
                    # Show sample rooms
                    if hotel_data["rooms"]:
                        response_text += f"""
   🛏️ **Sample Rooms** (showing first 3):
"""
                        for i, room in enumerate(hotel_data["rooms"][:3], 1):
                            response_text += f"""   {i}. {room['room_name']} (ID: {room['room_id']})
"""
                        if len(hotel_data["rooms"]) > 3:
                            response_text += f"""   ... and {len(hotel_data["rooms"]) - 3} more rooms
"""
                    
                    # Show sample packages
                    if hotel_data["packages"]:
                        response_text += f"""
   📦 **Sample Packages** (showing first 3):
"""
                        for i, package in enumerate(hotel_data["packages"][:3], 1):
                            response_text += f"""   {i}. {package['package_name']} (ID: {package['package_id']})
"""
                        if len(hotel_data["packages"]) > 3:
                            response_text += f"""   ... and {len(hotel_data["packages"]) - 3} more packages
"""
                    
                    # Show sample boards
                    if hotel_data["boards"]:
                        response_text += f"""
   🍽️ **Sample Boards** (showing first 3):
"""
                        for i, board in enumerate(hotel_data["boards"][:3], 1):
                            response_text += f"""   {i}. {board['board_name']} ({board['board_type_name']}) (ID: {board['board_id']})
"""
                        if len(hotel_data["boards"]) > 3:
                            response_text += f"""   ... and {len(hotel_data["boards"]) - 3} more boards
"""
            
            # Display summary statistics
            response_text += f"""

{'='*80}
📊 **INVENTORY STATISTICS**
{'='*80}

📈 **Component Distribution:**
- **Hotels with Rooms**: {len([h for h in grouped_data.values() if h['rooms']])}
- **Hotels with Packages**: {len([h for h in grouped_data.values() if h['packages']])}
- **Hotels with Products**: {len([h for h in grouped_data.values() if h['products']])}
- **Hotels with Rates**: {len([h for h in grouped_data.values() if h['rates']])}
- **Hotels with Boards**: {len([h for h in grouped_data.values() if h['boards']])}
- **Hotels with Offers**: {len([h for h in grouped_data.values() if h['offers']])}
- **Hotels with Extras**: {len([h for h in grouped_data.values() if h['extras']])}

"""
            
            # Show average components per hotel
            if grouped_data:
                total_hotels = len(grouped_data)
                avg_rooms = sum(len(h["rooms"]) for h in grouped_data.values()) / total_hotels
                avg_packages = sum(len(h["packages"]) for h in grouped_data.values()) / total_hotels
                avg_products = sum(len(h["products"]) for h in grouped_data.values()) / total_hotels
                
                response_text += f"""📏 **Average Components per Hotel:**
- **Rooms**: {avg_rooms:.1f}
- **Packages**: {avg_packages:.1f}
- **Products**: {avg_products:.1f}

"""
            
            response_text += f"""🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Hotel Info List Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel IDs exist and are accessible
- Check your authentication credentials
- Ensure you have permission to view hotel inventory details
- Verify the ID formats are correct
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving hotel info list details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
