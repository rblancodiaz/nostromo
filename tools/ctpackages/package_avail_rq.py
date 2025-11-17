"""
PackageAvailRQ - Package Availability Tool

This tool retrieves availability information for tourism packages in the Neobookings system.
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
PACKAGE_AVAIL_RQ_TOOL = Tool(
    name="package_avail_rq",
    description="""
    Search and retrieve availability information for tourism packages.
    
    This tool allows searching for available tourism packages that combine accommodations
    with additional services. It supports comprehensive filtering by location, dates,
    guest distribution, and various criteria to find suitable package deals.
    
    Parameters:
    - hotel_room_distribution (required): Room and guest distribution details
    - country (optional): List of country codes to filter by
    - zone (optional): List of zone codes to filter by  
    - hotel_ids (optional): Specific hotel IDs to search
    - hotel_room_ids (optional): Specific room IDs to include
    - hotel_types (optional): Hotel type filters
    - hotel_categories (optional): Hotel category filters
    - result_type (optional): Type of pricing result (besthotelprice/liveprice)
    - order_by (optional): Sort results by specific criteria
    - order_type (optional): Sort direction (asc/desc)
    - page (optional): Page number for pagination
    - num_results (optional): Number of results per page
    - show_details (optional): Include detailed information flags
    - filters (optional): Additional filtering criteria
    - promo_code (optional): Promotional code to apply
    - rewards (optional): Include loyalty rewards
    - origin (optional): Booking origin
    - client_location (optional): Client location information
    - client_device (optional): Client device type
    
    Returns:
    - Available packages with pricing and details
    - Hotel and room information
    - Package descriptions and inclusions
    - Availability dates and restrictions
    - Pagination information for large result sets
    
    Example usage:
    "Find vacation packages in Spain for 2 adults from March 1-8"
    "Search for family packages in beach hotels for 4 people"
    "Show available romantic packages in Paris hotels"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_room_distribution": {
                "type": "array",
                "description": "Room and guest distribution details",
                "items": {
                    "type": "object",
                    "properties": {
                        "hotel_room_rph": {
                            "type": "integer",
                            "description": "Room reference number"
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Check-in date (YYYY-MM-DD)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "date_to": {
                            "type": "string", 
                            "description": "Check-out date (YYYY-MM-DD)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "guest": {
                            "type": "array",
                            "description": "Guest distribution by age",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "age": {"type": "integer", "minimum": 0, "maximum": 120},
                                    "amount": {"type": "integer", "minimum": 1, "maximum": 10}
                                },
                                "required": ["age", "amount"]
                            }
                        }
                    },
                    "required": ["hotel_room_rph", "date_from", "date_to", "guest"]
                },
                "minItems": 1,
                "maxItems": 10
            },
            "country": {
                "type": "array",
                "description": "Country codes to filter by (ISO 3166-1)",
                "items": {"type": "string", "pattern": "^[A-Z]{2}$"},
                "maxItems": 50
            },
            "zone": {
                "type": "array", 
                "description": "Zone codes defined by Neobookings",
                "items": {"type": "string"},
                "maxItems": 100
            },
            "hotel_ids": {
                "type": "array",
                "description": "Specific hotel IDs to search",
                "items": {"type": "string"},
                "maxItems": 100
            },
            "hotel_room_ids": {
                "type": "array",
                "description": "Specific room IDs to include", 
                "items": {"type": "string"},
                "maxItems": 100
            },
            "hotel_types": {
                "type": "array",
                "description": "Hotel types to filter by",
                "items": {"type": "string"},
                "maxItems": 20
            },
            "hotel_categories": {
                "type": "array",
                "description": "Hotel categories to filter by",
                "items": {"type": "string"},
                "maxItems": 20
            },
            "result_type": {
                "type": "string",
                "description": "Type of pricing result",
                "enum": ["besthotelprice", "liveprice"],
                "default": "liveprice"
            },
            "order_by": {
                "type": "string",
                "description": "Sort results by",
                "enum": ["id", "hotelid", "roomid", "price", "quantity", "location", "order"],
                "default": "price"
            },
            "order_type": {
                "type": "string",
                "description": "Sort direction",
                "enum": ["asc", "desc"],
                "default": "asc"
            },
            "page": {
                "type": "integer",
                "description": "Page number for pagination",
                "minimum": 1,
                "default": 1
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results per page",
                "minimum": 1,
                "maximum": 100,
                "default": 20
            },
            "show_hotel_basic_detail": {
                "type": "boolean",
                "description": "Include basic hotel information",
                "default": True
            },
            "show_hotel_room_basic_detail": {
                "type": "boolean", 
                "description": "Include basic room information",
                "default": True
            },
            "show_hotel_room_extra_basic_detail": {
                "type": "boolean",
                "description": "Include room extra information", 
                "default": False
            },
            "show_package_not_availability": {
                "type": "boolean",
                "description": "Include packages not available",
                "default": False
            },
            "show_package_detail": {
                "type": "boolean",
                "description": "Include detailed package information",
                "default": True
            },
            "filters": {
                "type": "object",
                "description": "Additional filtering criteria",
                "properties": {
                    "reservation_mode": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["room", "package", "product"]},
                        "description": "Reservation modes to include"
                    },
                    "hotel_room_amenity_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Required room amenities"
                    },
                    "hotel_amenity_ids": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "Required hotel amenities"
                    },
                    "location_data": {
                        "type": "object",
                        "description": "Geographic location filtering",
                        "properties": {
                            "latitude": {"type": "string"},
                            "longitude": {"type": "string"},
                            "response_unit": {"type": "string", "enum": ["km", "mt", "ml"]},
                            "radio": {"type": "number", "minimum": 0}
                        }
                    }
                },
                "additionalProperties": False
            },
            "promo_code": {
                "type": "string",
                "description": "Promotional code to apply",
                "maxLength": 50
            },
            "rewards": {
                "type": "boolean",
                "description": "Include loyalty rewards",
                "default": False
            },
            "origin": {
                "type": "string",
                "description": "Booking origin identifier",
                "maxLength": 100
            },
            "client_location": {
                "type": "object",
                "description": "Client location information",
                "properties": {
                    "country": {"type": "string", "pattern": "^[A-Z]{2}$"},
                    "ip": {"type": "string"}
                },
                "additionalProperties": False
            },
            "client_device": {
                "type": "string",
                "description": "Client device type",
                "enum": ["desktop", "mobile", "tablet"],
                "default": "desktop"
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["hotel_room_distribution"],
        "additionalProperties": False
    }
)


class PackageAvailRQHandler:
    """Handler for the PackageAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="package_avail_rq")
    
    def _validate_hotel_room_distribution(self, distribution: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and sanitize hotel room distribution data."""
        if not distribution:
            raise ValidationError("Hotel room distribution is required")
        
        validated_distribution = []
        for i, room in enumerate(distribution):
            try:
                # Validate required fields
                hotel_room_rph = room.get("hotel_room_rph")
                if not isinstance(hotel_room_rph, int) or hotel_room_rph < 1:
                    raise ValidationError(f"Room {i+1}: hotel_room_rph must be a positive integer")
                
                date_from = room.get("date_from", "").strip()
                date_to = room.get("date_to", "").strip()
                
                if not date_from or not date_to:
                    raise ValidationError(f"Room {i+1}: date_from and date_to are required")
                
                # Validate guest distribution
                guests = room.get("guest", [])
                if not guests:
                    raise ValidationError(f"Room {i+1}: at least one guest is required")
                
                validated_guests = []
                for j, guest in enumerate(guests):
                    age = guest.get("age")
                    amount = guest.get("amount")
                    
                    if not isinstance(age, int) or age < 0 or age > 120:
                        raise ValidationError(f"Room {i+1}, Guest {j+1}: age must be between 0 and 120")
                    
                    if not isinstance(amount, int) or amount < 1 or amount > 10:
                        raise ValidationError(f"Room {i+1}, Guest {j+1}: amount must be between 1 and 10")
                    
                    validated_guests.append({
                        "Age": age,
                        "Amount": amount
                    })
                
                validated_distribution.append({
                    "HotelRoomRPH": hotel_room_rph,
                    "DateFrom": date_from,
                    "DateTo": date_to,
                    "Guest": validated_guests
                })
                
            except Exception as e:
                raise ValidationError(f"Room {i+1} validation error: {str(e)}")
        
        return validated_distribution
    
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
    
    def _format_package_availability(self, packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format package availability information for readable output."""
        formatted_packages = []
        
        for package in packages:
            formatted_package = {
                "availability_id": package.get("PackageAvailabilityId"),
                "package_rph": package.get("PackageRPH"),
                "package_id": package.get("PackageId"),
                "hotel_rooms": [],
                "hotel_room_extras": []
            }
            
            # Format hotel room availability
            hotel_rooms = package.get("HotelRoomAvail", [])
            for room in hotel_rooms:
                formatted_room = {
                    "availability_id": room.get("HotelRoomAvailabilityId"),
                    "hotel_id": room.get("HotelId"),
                    "hotel_hash": room.get("HotelHash"), 
                    "room_id": room.get("HotelRoomId"),
                    "room_rph": room.get("HotelRoomRPH"),
                    "quantity": room.get("Quantity"),
                    "distance_to_location": room.get("DistanceToLocation"),
                    "amounts": {}
                }
                
                # Format amounts detail
                amounts = room.get("AmountsDetail", {})
                if amounts:
                    formatted_room["amounts"] = {
                        "currency": amounts.get("Currency"),
                        "final_amount": amounts.get("AmountFinal"),
                        "total_amount": amounts.get("AmountTotal"),
                        "base_amount": amounts.get("AmountBase"),
                        "taxes_amount": amounts.get("AmountTaxes"),
                        "tourist_tax_amount": amounts.get("AmountTouristTax")
                    }
                
                formatted_package["hotel_rooms"].append(formatted_room)
            
            # Format hotel room extra availability
            room_extras = package.get("HotelRoomExtraAvail", [])
            for extra in room_extras:
                formatted_extra = {
                    "availability_id": extra.get("HotelRoomExtraAvailabilityId"),
                    "room_availability_id": extra.get("HotelRoomAvailabilityId"),
                    "extra_id": extra.get("HotelRoomExtraId"),
                    "included": extra.get("Included", False),
                    "release": extra.get("Release"),
                    "min_stay": extra.get("MinStay"),
                    "availability": extra.get("Availability"),
                    "visibility": extra.get("Visibility")
                }
                
                formatted_package["hotel_room_extras"].append(formatted_extra)
            
            formatted_packages.append(formatted_package)
        
        return formatted_packages
    
    def _format_package_not_available(self, packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format package not available information."""
        formatted_packages = []
        
        for package in packages:
            formatted_package = {
                "package_rph": package.get("PackageRPH"),
                "package_id": package.get("PackageId"),
                "cause": {}
            }
            
            # Format cause information
            cause = package.get("Cause", {})
            if cause:
                formatted_package["cause"] = {
                    "code": cause.get("Code"),
                    "description": cause.get("Description"),
                    "target": cause.get("Target")
                }
            
            formatted_packages.append(formatted_package)
        
        return formatted_packages
    
    def _format_hotel_basic_details(self, hotels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format hotel basic detail information."""
        formatted_hotels = []
        
        for hotel in hotels:
            formatted_hotel = {
                "hotel_id": hotel.get("HotelId"),
                "hotel_hash": hotel.get("HotelHash"),
                "hotel_name": hotel.get("HotelName"),
                "hotel_description": hotel.get("HotelDescription"),
                "currency": hotel.get("Currency"),
                "rewards": hotel.get("Rewards", False),
                "hotel_mode": hotel.get("HotelMode"),
                "hotel_view": hotel.get("HotelView"),
                "timezone": hotel.get("TimeZone"),
                "location": {}
            }
            
            # Format location information
            location = hotel.get("HotelLocation", {})
            if location:
                formatted_hotel["location"] = {
                    "address": location.get("Address"),
                    "city": location.get("City"),
                    "postal_code": location.get("PostalCode"),
                    "latitude": location.get("Latitude"),
                    "longitude": location.get("Longitude"),
                    "country": location.get("Country", {}).get("Name"),
                    "country_code": location.get("Country", {}).get("Code"),
                    "state": location.get("State", {}).get("Name"),
                    "zones": [zone.get("Name") for zone in location.get("Zone", [])]
                }
            
            formatted_hotels.append(formatted_hotel)
        
        return formatted_hotels
    
    def _format_package_details(self, packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format package detail information."""
        formatted_packages = []
        
        for package in packages:
            formatted_package = {
                "package_id": package.get("PackageId"),
                "hotel_id": package.get("HotelId"),
                "hotel_hash": package.get("HotelHash"),
                "package_name": package.get("PackageName"),
                "package_description": package.get("PackageDescription"),
                "status": package.get("Status"),
                "order": package.get("Order"),
                "hotel_room_ids": package.get("HotelRoomId", []),
                "hotel_board_ids": package.get("HotelBoardId", []),
                "hotel_room_extra_ids": package.get("HotelRoomExtraId", []),
                "categories": []
            }
            
            # Format categories
            categories = package.get("PackageCategory", [])
            for category in categories:
                formatted_package["categories"].append({
                    "code": category.get("Code"),
                    "name": category.get("Name")
                })
            
            formatted_packages.append(formatted_package)
        
        return formatted_packages
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the package availability search request.
        
        Args:
            arguments: Tool arguments containing search criteria
            
        Returns:
            Dictionary containing the package availability results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_room_distribution = arguments.get("hotel_room_distribution", [])
            country = arguments.get("country", [])
            zone = arguments.get("zone", [])
            hotel_ids = arguments.get("hotel_ids", [])
            hotel_room_ids = arguments.get("hotel_room_ids", [])
            hotel_types = arguments.get("hotel_types", [])
            hotel_categories = arguments.get("hotel_categories", [])
            result_type = arguments.get("result_type", "liveprice")
            order_by = arguments.get("order_by", "price")
            order_type = arguments.get("order_type", "asc")
            page = arguments.get("page", 1)
            num_results = arguments.get("num_results", 20)
            show_hotel_basic_detail = arguments.get("show_hotel_basic_detail", True)
            show_hotel_room_basic_detail = arguments.get("show_hotel_room_basic_detail", True)
            show_hotel_room_extra_basic_detail = arguments.get("show_hotel_room_extra_basic_detail", False)
            show_package_not_availability = arguments.get("show_package_not_availability", False)
            show_package_detail = arguments.get("show_package_detail", True)
            filters = arguments.get("filters", {})
            promo_code = arguments.get("promo_code")
            rewards = arguments.get("rewards", False)
            origin = arguments.get("origin")
            client_location = arguments.get("client_location", {})
            client_device = arguments.get("client_device", "desktop")
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_distribution = self._validate_hotel_room_distribution(hotel_room_distribution)
            validated_country = self._validate_string_list(country, "Country", 50)
            validated_zone = self._validate_string_list(zone, "Zone", 100)
            validated_hotel_ids = self._validate_string_list(hotel_ids, "Hotel ID", 100)
            validated_hotel_room_ids = self._validate_string_list(hotel_room_ids, "Hotel Room ID", 100)
            validated_hotel_types = self._validate_string_list(hotel_types, "Hotel Type", 20)
            validated_hotel_categories = self._validate_string_list(hotel_categories, "Hotel Category", 20)
            
            if page < 1:
                raise ValidationError("Page must be at least 1")
            if num_results < 1 or num_results > 100:
                raise ValidationError("Number of results must be between 1 and 100")
            
            self.logger.info(
                "Searching package availability",
                room_distribution_count=len(validated_distribution),
                countries=len(validated_country),
                zones=len(validated_zone),
                hotel_ids=len(validated_hotel_ids),
                result_type=result_type,
                order_by=order_by,
                page=page,
                num_results=num_results,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "HotelRoomDistribution": validated_distribution,
                "ShowHotelBasicDetail": show_hotel_basic_detail,
                "ShowHotelRoomBasicDetail": show_hotel_room_basic_detail,
                "ShowHotelRoomExtraBasicDetail": show_hotel_room_extra_basic_detail,
                "ShowPackageNotAvailability": show_package_not_availability
            }
            
            # Add optional parameters
            if validated_country:
                request_payload["Country"] = validated_country
            if validated_zone:
                request_payload["Zone"] = validated_zone
            if validated_hotel_ids:
                request_payload["HotelId"] = validated_hotel_ids
            if validated_hotel_room_ids:
                request_payload["HotelRoomId"] = validated_hotel_room_ids
            if validated_hotel_types:
                request_payload["HotelType"] = validated_hotel_types
            if validated_hotel_categories:
                request_payload["HotelCategory"] = validated_hotel_categories
            if result_type:
                request_payload["ResultType"] = result_type
            if order_by:
                request_payload["OrderBy"] = order_by
            if order_type:
                request_payload["OrderType"] = order_type
            if page:
                request_payload["Page"] = page
            if num_results:
                request_payload["NumResults"] = num_results
            if show_package_detail:
                request_payload["ShowPackageDetail"] = show_package_detail
            if promo_code:
                request_payload["PromoCode"] = sanitize_string(promo_code)
            if rewards:
                request_payload["Rewards"] = rewards
            if origin:
                request_payload["Origin"] = sanitize_string(origin)
            if client_location:
                request_payload["ClientLocation"] = client_location
            if client_device:
                request_payload["ClientDevice"] = client_device
            
            # Add filters if provided
            if filters:
                filter_by = {}
                if filters.get("reservation_mode"):
                    filter_by["ReservationMode"] = filters["reservation_mode"]
                if filters.get("hotel_room_amenity_ids"):
                    filter_by["HotelRoomAmenityId"] = filters["hotel_room_amenity_ids"]
                if filters.get("hotel_amenity_ids"):
                    filter_by["HotelAmenityId"] = filters["hotel_amenity_ids"]
                if filters.get("location_data"):
                    filter_by["LocationData"] = filters["location_data"]
                
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
                
                # Make the package availability request
                response = await client.post("/PackageAvailRQ", request_payload)
            
            # Extract data from response
            current_page = response.get("CurrentPage", 1)
            total_pages = response.get("TotalPages", 1)
            total_records = response.get("TotalRecords", 0)
            package_distribution = response.get("PackageDistribution", [])
            hotel_basic_detail = response.get("HotelBasicDetail", [])
            hotel_room_basic_detail = response.get("HotelRoomBasicDetail", [])
            package_detail = response.get("PackageDetail", [])
            hotel_room_extra_detail = response.get("HotelRoomExtraDetail", [])
            package_avail = response.get("PackageAvail", [])
            package_not_avail = response.get("PackageNotAvail", [])
            api_response = response.get("Response", {})
            
            # Format results
            formatted_package_avail = self._format_package_availability(package_avail)
            formatted_package_not_avail = self._format_package_not_available(package_not_avail)
            formatted_hotels = self._format_hotel_basic_details(hotel_basic_detail)
            formatted_packages = self._format_package_details(package_detail)
            
            # Log successful operation
            self.logger.info(
                "Package availability search completed",
                total_records=total_records,
                current_page=current_page,
                total_pages=total_pages,
                packages_available=len(formatted_package_avail),
                packages_not_available=len(formatted_package_not_avail),
                hotels_found=len(formatted_hotels),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "room_distribution": validated_distribution,
                    "countries": validated_country,
                    "zones": validated_zone,
                    "hotel_ids": validated_hotel_ids,
                    "result_type": result_type,
                    "order_by": order_by,
                    "order_type": order_type
                },
                "pagination": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "total_records": total_records,
                    "page_size": num_results
                },
                "packages_available": formatted_package_avail,
                "packages_not_available": formatted_package_not_avail,
                "hotels": formatted_hotels,
                "package_details": formatted_packages,
                "summary": {
                    "total_packages_found": len(formatted_package_avail),
                    "packages_not_available": len(formatted_package_not_avail),
                    "hotels_with_packages": len(formatted_hotels),
                    "has_more_pages": current_page < total_pages
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(formatted_package_avail)} available packages"
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
handler = PackageAvailRQHandler()


async def call_package_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the PackageAvailRQ endpoint.
    
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
            pagination = data["pagination"]
            packages_available = data["packages_available"]
            packages_not_available = data["packages_not_available"]
            hotels = data["hotels"]
            package_details = data["package_details"]
            summary = data["summary"]
            
            response_text = f"""🏖️ **Package Availability Search Results**

📊 **Search Summary:**
- **Total Packages Found**: {summary['total_packages_found']}
- **Packages Not Available**: {summary['packages_not_available']}
- **Hotels with Packages**: {summary['hotels_with_packages']}
- **Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Total Records**: {pagination['total_records']:,}

"""
            
            if packages_available:
                response_text += f"""📦 **Available Packages ({len(packages_available)}):**
{'='*80}
"""
                
                for i, package in enumerate(packages_available, 1):
                    response_text += f"""
📦 **Package #{i}**
{'-'*60}

🏷️ **Package Information:**
- **Availability ID**: {package['availability_id']}
- **Package RPH**: {package['package_rph']}
- **Package ID**: {package['package_id']}
"""
                    
                    # Hotel rooms included
                    hotel_rooms = package.get('hotel_rooms', [])
                    if hotel_rooms:
                        response_text += f"""
🏨 **Included Hotel Rooms ({len(hotel_rooms)}):**
"""
                        for j, room in enumerate(hotel_rooms, 1):
                            amounts = room.get('amounts', {})
                            response_text += f"""
  **Room #{j}:**
  - **Hotel ID**: {room.get('hotel_id', 'N/A')}
  - **Room ID**: {room.get('room_id', 'N/A')}
  - **Quantity Available**: {room.get('quantity', 'N/A')}
"""
                            if amounts.get('final_amount'):
                                response_text += f"  - **Price**: {amounts['final_amount']} {amounts.get('currency', '')}\n"
                            if room.get('distance_to_location'):
                                response_text += f"  - **Distance**: {room['distance_to_location']} km\n"
                    
                    # Hotel room extras
                    room_extras = package.get('hotel_room_extras', [])
                    if room_extras:
                        included_extras = [e for e in room_extras if e.get('included')]
                        optional_extras = [e for e in room_extras if not e.get('included')]
                        
                        if included_extras:
                            response_text += f"""
✅ **Included Extras ({len(included_extras)}):**
"""
                            for extra in included_extras:
                                response_text += f"  - Extra ID: {extra.get('extra_id', 'N/A')}\n"
                        
                        if optional_extras:
                            response_text += f"""
🛍️ **Optional Extras ({len(optional_extras)}):**
"""
                            for extra in optional_extras:
                                response_text += f"  - Extra ID: {extra.get('extra_id', 'N/A')} (Available: {extra.get('availability', 'N/A')})\n"
                    
                    response_text += "\n"
            
            # Package details
            if package_details:
                response_text += f"""
📋 **Package Details ({len(package_details)}):**
{'='*80}
"""
                
                for i, package in enumerate(package_details, 1):
                    response_text += f"""
📋 **Package Detail #{i}**
{'-'*60}

🏷️ **Package Information:**
- **Package ID**: {package['package_id']}
- **Name**: {package['package_name']}
- **Hotel ID**: {package['hotel_id']}
- **Status**: {package['status']}
- **Order**: {package['order']}

📝 **Description:**
{package.get('package_description', 'No description available')}

🏨 **Inclusions:**
- **Hotel Rooms**: {len(package.get('hotel_room_ids', []))} room type(s)
- **Board Types**: {len(package.get('hotel_board_ids', []))} board option(s)
- **Extra Services**: {len(package.get('hotel_room_extra_ids', []))} extra(s)
"""
                    
                    # Categories
                    categories = package.get('categories', [])
                    if categories:
                        response_text += f"""
🏷️ **Categories:**
{', '.join([f"{cat.get('name', 'N/A')} ({cat.get('code', 'N/A')})" for cat in categories])}
"""
                    
                    response_text += "\n"
            
            # Hotels information
            if hotels:
                response_text += f"""
🏨 **Hotels with Available Packages ({len(hotels)}):**
{'='*80}
"""
                
                for i, hotel in enumerate(hotels, 1):
                    location = hotel.get('location', {})
                    response_text += f"""
🏨 **Hotel #{i}**
{'-'*60}

🏷️ **Hotel Information:**
- **Hotel ID**: {hotel['hotel_id']}
- **Name**: {hotel['hotel_name']}
- **Currency**: {hotel['currency']}
- **Mode**: {hotel.get('hotel_mode', 'N/A')}
- **Rewards Program**: {'Yes' if hotel.get('rewards') else 'No'}

📍 **Location:**
- **Address**: {location.get('address', 'N/A')}
- **City**: {location.get('city', 'N/A')}
- **Country**: {location.get('country', 'N/A')}
"""
                    if location.get('zones'):
                        response_text += f"- **Zones**: {', '.join(location['zones'])}\n"
                    if location.get('latitude') and location.get('longitude'):
                        response_text += f"- **Coordinates**: {location['latitude']}, {location['longitude']}\n"
                    
                    response_text += "\n"
            
            # Packages not available
            if packages_not_available:
                response_text += f"""
❌ **Packages Not Available ({len(packages_not_available)}):**
{'='*80}
"""
                
                for i, package in enumerate(packages_not_available, 1):
                    cause = package.get('cause', {})
                    response_text += f"""
❌ **Package #{i}**
- **Package ID**: {package['package_id']}
- **Package RPH**: {package['package_rph']}
- **Reason**: {cause.get('description', 'No reason provided')}
- **Code**: {cause.get('code', 'N/A')}
"""
            
            # Pagination info
            if pagination['total_pages'] > 1:
                response_text += f"""
📄 **Pagination Information:**
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Total Records**: {pagination['total_records']:,}
- **Records per Page**: {pagination['page_size']}
- **More Pages Available**: {'Yes' if summary['has_more_pages'] else 'No'}
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use package availability for vacation package bookings
- Combine with hotel details for complete information
- Check included services and optional extras
- Use filters to narrow down results by preferences
- Consider different result types for best pricing
"""
                
        else:
            response_text = f"""❌ **Package Availability Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel room distribution is properly formatted
- Check that dates are valid and in the future
- Ensure guest distribution includes at least one guest
- Verify location filters are valid
- Check authentication credentials
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching package availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
