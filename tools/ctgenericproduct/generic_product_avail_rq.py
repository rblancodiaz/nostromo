"""
GenericProductAvailRQ - Generic Product Availability Search Tool

This tool searches for availability of generic products based on distribution
criteria, dates, guests, and various filters to find suitable products.
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
GENERIC_PRODUCT_AVAIL_RQ_TOOL = Tool(
    name="generic_product_avail_rq",
    description="""
    Search for availability of generic products with comprehensive filtering options.
    
    This tool searches for generic products across hotels with flexible criteria:
    - Location-based filtering (country, zone, hotel)
    - Product distribution with dates and guest specifications
    - Product type and reservation method filtering
    - Pagination and sorting options
    - Detailed product information display
    
    Parameters:
    - countries (optional): List of country codes to filter by
    - zones (optional): List of zone codes to filter by
    - hotel_ids (optional): List of specific hotel IDs to search
    - hotel_room_ids (optional): List of specific room IDs to search
    - hotel_types (optional): List of hotel types to filter by
    - hotel_categories (optional): List of hotel categories to filter by
    - product_distributions (required): Distribution criteria with dates and guests
    - product_types (optional): Filter by product types (accommodation, simpleproduct, etc.)
    - product_methods (optional): Filter by reservation methods (withdates, undated)
    - reservation_modes (optional): Filter by modes (room, package, product)
    - result_type (optional): Type of pricing result (besthotelprice, liveprice)
    - order_by (optional): Sorting criteria (id, price, location, etc.)
    - order_type (optional): Sort direction (asc, desc)
    - page (optional): Page number for pagination
    - num_results (optional): Number of results per page
    - show_hotel_details (optional): Include hotel basic information
    - show_room_details (optional): Include room basic information
    - show_extra_details (optional): Include extra basic information
    - show_not_available (optional): Include unavailable products
    - show_product_details (optional): Include product detail information
    - promo_code (optional): Promotional code to apply
    - rewards (optional): Include rewards/loyalty pricing
    - origin (optional): Origin of the reservation
    - client_country (optional): Country of the client
    - client_ip (optional): IP address of the client
    - client_device (optional): Type of client device
    - language (optional): Language for the request
    
    Returns:
    - Available generic products with pricing and details
    - Product distribution information
    - Hotel and room basic details (if requested)
    - Product details and extra information
    - Pagination and search metadata
    
    Example usage:
    "Search for accommodation products from 2024-12-15 to 2024-12-20 for 2 adults"
    "Find generic products in Madrid hotels for 1 adult and 1 child"
    "Search for undated products in Spain"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "countries": {
                "type": "array",
                "description": "List of country codes (ISO 3166-1) to filter by",
                "items": {
                    "type": "string",
                    "description": "Country code (e.g., 'ES', 'FR', 'IT')"
                },
                "maxItems": 10
            },
            "zones": {
                "type": "array",
                "description": "List of zone codes defined by Neobookings",
                "items": {
                    "type": "string",
                    "description": "Zone code (e.g., 'MAD', 'BCN', 'NYC')"
                },
                "maxItems": 20
            },
            "hotel_ids": {
                "type": "array",
                "description": "List of specific hotel IDs to search in",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 50
            },
            "hotel_room_ids": {
                "type": "array",
                "description": "List of specific hotel room IDs to search in",
                "items": {
                    "type": "string",
                    "description": "Hotel room identifier"
                },
                "maxItems": 100
            },
            "hotel_types": {
                "type": "array",
                "description": "List of hotel types to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel type identifier"
                },
                "maxItems": 10
            },
            "hotel_categories": {
                "type": "array",
                "description": "List of hotel categories to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel category (e.g., '3', '4', '5')"
                },
                "maxItems": 5
            },
            "product_distributions": {
                "type": "array",
                "description": "Product distribution criteria with dates and guests",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_rph": {
                            "type": "integer",
                            "description": "Reference number for the product",
                            "minimum": 1
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "date_to": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "specific_day": {
                            "type": "string",
                            "description": "Specific day in YYYY-MM-DD format (ignores date_from/date_to)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "guests": {
                            "type": "array",
                            "description": "Guest specifications by age and quantity",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "age": {
                                        "type": "integer",
                                        "description": "Age of the guest",
                                        "minimum": 0,
                                        "maximum": 120
                                    },
                                    "amount": {
                                        "type": "integer",
                                        "description": "Number of guests of this age",
                                        "minimum": 1,
                                        "maximum": 20
                                    }
                                },
                                "required": ["age", "amount"],
                                "additionalProperties": False
                            },
                            "minItems": 1,
                            "maxItems": 10
                        }
                    },
                    "required": ["product_rph", "guests"],
                    "additionalProperties": False
                },
                "minItems": 1,
                "maxItems": 10
            },
            "product_types": {
                "type": "array",
                "description": "Filter by generic product types",
                "items": {
                    "type": "string",
                    "enum": ["accommodation", "simpleproduct", "extraproduct", "combinedproduct"]
                },
                "maxItems": 4
            },
            "product_methods": {
                "type": "array",
                "description": "Filter by reservation methods",
                "items": {
                    "type": "string",
                    "enum": ["withdates", "undated"]
                },
                "maxItems": 2
            },
            "reservation_modes": {
                "type": "array",
                "description": "Filter by reservation modes",
                "items": {
                    "type": "string",
                    "enum": ["room", "package", "product"]
                },
                "maxItems": 3
            },
            "result_type": {
                "type": "string",
                "description": "Type of pricing result to return",
                "enum": ["besthotelprice", "liveprice"],
                "default": "liveprice"
            },
            "order_by": {
                "type": "string",
                "description": "Field to sort results by",
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
            "show_hotel_details": {
                "type": "boolean",
                "description": "Include hotel basic information in results",
                "default": True
            },
            "show_room_details": {
                "type": "boolean",
                "description": "Include room basic information in results",
                "default": True
            },
            "show_extra_details": {
                "type": "boolean",
                "description": "Include extra basic information in results",
                "default": False
            },
            "show_not_available": {
                "type": "boolean",
                "description": "Include products that are not available",
                "default": False
            },
            "show_product_details": {
                "type": "boolean",
                "description": "Include detailed product information",
                "default": True
            },
            "promo_code": {
                "type": "string",
                "description": "Promotional code to apply for special pricing",
                "maxLength": 50
            },
            "rewards": {
                "type": "boolean",
                "description": "Include rewards/loyalty program pricing",
                "default": False
            },
            "origin": {
                "type": "string",
                "description": "Origin of the reservation for tracking",
                "maxLength": 100
            },
            "client_country": {
                "type": "string",
                "description": "Country code of the client",
                "maxLength": 2
            },
            "client_ip": {
                "type": "string",
                "description": "IP address of the client",
                "maxLength": 45
            },
            "client_device": {
                "type": "string",
                "description": "Type of client device",
                "enum": ["desktop", "mobile", "tablet"]
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["product_distributions"],
        "additionalProperties": False
    }
)


class GenericProductAvailRQHandler:
    """Handler for the GenericProductAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="generic_product_avail_rq")
    
    def _validate_product_distributions(self, distributions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and format product distribution data."""
        validated = []
        
        for i, dist in enumerate(distributions):
            try:
                product_rph = dist.get("product_rph")
                if not isinstance(product_rph, int) or product_rph < 1:
                    raise ValidationError(f"Distribution {i+1}: product_rph must be a positive integer")
                
                # Validate dates
                date_from = dist.get("date_from")
                date_to = dist.get("date_to")
                specific_day = dist.get("specific_day")
                
                formatted_dist = {"GenericProductRPH": product_rph}
                
                if specific_day:
                    formatted_dist["Day"] = parse_date(specific_day)
                else:
                    if date_from:
                        formatted_dist["DateFrom"] = parse_date(date_from)
                    if date_to:
                        formatted_dist["DateTo"] = parse_date(date_to)
                
                # Validate guests
                guests = dist.get("guests", [])
                if not guests:
                    raise ValidationError(f"Distribution {i+1}: at least one guest specification is required")
                
                formatted_guests = []
                for j, guest in enumerate(guests):
                    age = guest.get("age")
                    amount = guest.get("amount")
                    
                    if not isinstance(age, int) or age < 0 or age > 120:
                        raise ValidationError(f"Distribution {i+1}, guest {j+1}: age must be between 0 and 120")
                    if not isinstance(amount, int) or amount < 1 or amount > 20:
                        raise ValidationError(f"Distribution {i+1}, guest {j+1}: amount must be between 1 and 20")
                    
                    formatted_guests.append({
                        "Age": age,
                        "Amount": amount
                    })
                
                formatted_dist["Guest"] = formatted_guests
                validated.append(formatted_dist)
                
            except Exception as e:
                raise ValidationError(f"Distribution {i+1}: {str(e)}")
        
        return validated
    
    def _format_amounts_detail(self, amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Format amounts detail information for readable output."""
        if not amounts:
            return {}
        
        return {
            "currency": amounts.get("Currency"),
            "final_amount": amounts.get("AmountFinal"),
            "total_amount": amounts.get("AmountTotal"),
            "base_amount": amounts.get("AmountBase"),
            "taxes_amount": amounts.get("AmountTaxes"),
            "tourist_tax_amount": amounts.get("AmountTouristTax"),
            "before_amount": amounts.get("AmountBefore"),
            "inventory_amount": amounts.get("AmountBeforeInventory"),
            "max_amount": amounts.get("AmountBeforeMax"),
            "offers_amount": amounts.get("AmountOffers"),
            "discounts_amount": amounts.get("AmountDiscounts"),
            "extras_hidden_amount": amounts.get("AmountExtrasHidden"),
            "extras_amount": amounts.get("AmountExtras"),
            "deposit_amount": amounts.get("AmountDeposit"),
            "paid_amount": amounts.get("AmountPaid"),
            "loyalty_amount": amounts.get("AmountLoyalty")
        }
    
    def _format_hotel_room_avail(self, room_avail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format hotel room availability information."""
        formatted = []
        for room in room_avail:
            formatted_room = {
                "availability_id": room.get("HotelRoomAvailabilityId"),
                "hotel_id": room.get("HotelId"),
                "hotel_hash": room.get("HotelHash"),
                "room_id": room.get("HotelRoomId"),
                "room_rph": room.get("HotelRoomRPH"),
                "package_id": room.get("PackageId"),
                "product_id": room.get("ProductId"),
                "quantity": room.get("Quantity"),
                "distance_to_location": room.get("DistanceToLocation"),
                "url": room.get("HotelRoomAvailURL"),
                "type_result": room.get("TypeResult", [])
            }
            
            # Format amounts
            amounts = room.get("AmountsDetail", {})
            if amounts:
                formatted_room["amounts"] = self._format_amounts_detail(amounts)
            
            formatted.append(formatted_room)
        
        return formatted
    
    def _format_hotel_room_extra_avail(self, extra_avail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format hotel room extra availability information."""
        formatted = []
        for extra in extra_avail:
            formatted_extra = {
                "extra_availability_id": extra.get("HotelRoomExtraAvailabilityId"),
                "room_availability_id": extra.get("HotelRoomAvailabilityId"),
                "extra_id": extra.get("HotelRoomExtraId"),
                "included": extra.get("Included", False),
                "release": extra.get("Release"),
                "min_stay": extra.get("MinStay"),
                "availability": extra.get("Availability"),
                "date_for_extra": extra.get("DateForExtra"),
                "amount_extra": extra.get("AmountExtra"),
                "visibility": extra.get("Visibility")
            }
            
            # Format extra amounts
            extra_amounts = extra.get("HotelRoomExtraAmounts", {})
            if extra_amounts:
                formatted_extra["extra_amounts"] = {
                    "amount_type": extra_amounts.get("ExtraAmountType"),
                    "currency": extra_amounts.get("Currency"),
                    "final_amount": extra_amounts.get("AmountFinal"),
                    "base_amount": extra_amounts.get("AmountBase"),
                    "taxes_amount": extra_amounts.get("AmountTaxes"),
                    "before_amount": extra_amounts.get("AmountBefore"),
                    "inventory_amount": extra_amounts.get("AmountBeforeInventory"),
                    "max_amount": extra_amounts.get("AmountBeforeMax"),
                    "offers_amount": extra_amounts.get("AmountOffers"),
                    "discounts_amount": extra_amounts.get("AmountDiscounts")
                }
            
            formatted.append(formatted_extra)
        
        return formatted
    
    def _format_product_avail(self, product_avail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format generic product availability information."""
        formatted = []
        for product in product_avail:
            formatted_product = {
                "availability_id": product.get("GenericProductAvailabilityId"),
                "product_rph": product.get("GenericProductRPH"),
                "product_id": product.get("GenericProductId")
            }
            
            # Format hotel room availability
            room_avail = product.get("HotelRoomAvail", [])
            if room_avail:
                formatted_product["hotel_rooms"] = self._format_hotel_room_avail(room_avail)
            
            # Format hotel room extra availability
            extra_avail = product.get("HotelRoomExtraAvail", [])
            if extra_avail:
                formatted_product["hotel_room_extras"] = self._format_hotel_room_extra_avail(extra_avail)
            
            formatted.append(formatted_product)
        
        return formatted
    
    def _format_product_not_avail(self, product_not_avail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format generic product not available information."""
        formatted = []
        for product in product_not_avail:
            formatted_product = {
                "product_rph": product.get("GenericProductRPH"),
                "product_id": product.get("GenericProductId"),
                "cause": {
                    "code": product.get("Cause", {}).get("Code"),
                    "description": product.get("Cause", {}).get("Description"),
                    "target": product.get("Cause", {}).get("Target")
                }
            }
            
            formatted.append(formatted_product)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the generic product availability search request.
        
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
            countries = arguments.get("countries", [])
            zones = arguments.get("zones", [])
            hotel_ids = arguments.get("hotel_ids", [])
            hotel_room_ids = arguments.get("hotel_room_ids", [])
            hotel_types = arguments.get("hotel_types", [])
            hotel_categories = arguments.get("hotel_categories", [])
            product_distributions = arguments.get("product_distributions", [])
            product_types = arguments.get("product_types", [])
            product_methods = arguments.get("product_methods", [])
            reservation_modes = arguments.get("reservation_modes", [])
            result_type = arguments.get("result_type", "liveprice")
            order_by = arguments.get("order_by", "price")
            order_type = arguments.get("order_type", "asc")
            page = arguments.get("page", 1)
            num_results = arguments.get("num_results", 25)
            show_hotel_details = arguments.get("show_hotel_details", True)
            show_room_details = arguments.get("show_room_details", True)
            show_extra_details = arguments.get("show_extra_details", False)
            show_not_available = arguments.get("show_not_available", False)
            show_product_details = arguments.get("show_product_details", True)
            promo_code = arguments.get("promo_code")
            rewards = arguments.get("rewards", False)
            origin = arguments.get("origin")
            client_country = arguments.get("client_country")
            client_ip = arguments.get("client_ip")
            client_device = arguments.get("client_device")
            language = arguments.get("language", "es")
            
            # Validate pagination parameters
            if page < 1:
                raise ValidationError("Page number must be at least 1")
            if num_results < 1 or num_results > 100:
                raise ValidationError("Number of results must be between 1 and 100")
            
            # Validate and format product distributions
            formatted_distributions = self._validate_product_distributions(product_distributions)
            
            # Sanitize string inputs
            sanitized_countries = []
            if countries:
                for country in countries:
                    if not isinstance(country, str) or not country.strip():
                        raise ValidationError(f"Invalid country code: {country}")
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
            
            sanitized_hotel_ids = []
            if hotel_ids:
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            self.logger.info(
                "Performing generic product availability search",
                distributions_count=len(formatted_distributions),
                countries_count=len(sanitized_countries),
                zones_count=len(sanitized_zones),
                hotels_count=len(sanitized_hotel_ids),
                result_type=result_type,
                page=page,
                num_results=num_results,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            # Add required parameters
            request_payload["GenericProductDistribution"] = formatted_distributions
            request_payload["ShowHotelBasicDetail"] = show_hotel_details
            request_payload["ShowHotelRoomBasicDetail"] = show_room_details
            request_payload["ShowHotelRoomExtraBasicDetail"] = show_extra_details
            request_payload["ShowGenericProductNotAvailability"] = show_not_available
            
            # Add optional parameters
            if sanitized_countries:
                request_payload["Country"] = sanitized_countries
            if sanitized_zones:
                request_payload["Zone"] = sanitized_zones
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            if hotel_room_ids:
                request_payload["HotelRoomId"] = hotel_room_ids
            if hotel_types:
                request_payload["HotelType"] = hotel_types
            if hotel_categories:
                request_payload["HotelCategory"] = hotel_categories
            if result_type != "liveprice":
                request_payload["ResultType"] = result_type
            if product_types or product_methods or reservation_modes:
                filter_by = {}
                if product_types:
                    filter_by["GenericProductType"] = product_types
                if product_methods:
                    filter_by["GenericProductMethod"] = product_methods
                if reservation_modes:
                    filter_by["ReservationMode"] = reservation_modes
                request_payload["GenericProductFilterBy"] = filter_by
            if order_by != "price":
                request_payload["OrderBy"] = order_by
            if order_type != "asc":
                request_payload["OrderType"] = order_type
            if page > 1:
                request_payload["Page"] = page
            if num_results != 25:
                request_payload["NumResults"] = num_results
            if show_product_details:
                request_payload["ShowGenericProductDetail"] = show_product_details
            if promo_code:
                request_payload["PromoCode"] = sanitize_string(promo_code.strip())
            if rewards:
                request_payload["Rewards"] = rewards
            if origin:
                request_payload["Origin"] = sanitize_string(origin.strip())
            
            # Add client location data if provided
            if client_country or client_ip:
                client_location = {}
                if client_country:
                    client_location["Country"] = sanitize_string(client_country.strip().upper())
                if client_ip:
                    client_location["Ip"] = sanitize_string(client_ip.strip())
                request_payload["ClientLocation"] = client_location
            
            if client_device:
                request_payload["ClientDevice"] = client_device
            
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
                
                # Make the generic product availability request
                response = await client.post("/GenericProductAvailRQ", request_payload)
            
            # Extract search results from response
            current_page = response.get("CurrentPage", 1)
            total_pages = response.get("TotalPages", 1)
            total_records = response.get("TotalRecords", 0)
            
            product_distributions_result = response.get("GenericProductDistribution", [])
            hotel_details = response.get("HotelBasicDetail", [])
            room_details = response.get("HotelRoomBasicDetail", [])
            product_details = response.get("GenericProductDetail", [])
            extra_details = response.get("HotelRoomExtraDetail", [])
            product_avail = response.get("GenericProductAvail", [])
            product_not_avail = response.get("GenericProductNotAvail", [])
            
            # Format results
            formatted_product_avail = self._format_product_avail(product_avail)
            formatted_product_not_avail = self._format_product_not_avail(product_not_avail)
            
            # Log successful operation
            self.logger.info(
                "Generic product availability search completed successfully",
                available_products=len(formatted_product_avail),
                unavailable_products=len(formatted_product_not_avail),
                total_records=total_records,
                current_page=current_page,
                total_pages=total_pages,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "product_distributions": product_distributions_result,
                "available_products": formatted_product_avail,
                "unavailable_products": formatted_product_not_avail,
                "hotel_details": hotel_details,
                "room_details": room_details,
                "product_details": product_details,
                "extra_details": extra_details,
                "pagination": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "total_records": total_records,
                    "results_per_page": num_results,
                    "has_next_page": current_page < total_pages,
                    "has_previous_page": current_page > 1
                },
                "search_criteria": {
                    "countries": sanitized_countries,
                    "zones": sanitized_zones,
                    "hotel_ids": sanitized_hotel_ids,
                    "product_types": product_types,
                    "product_methods": product_methods,
                    "reservation_modes": reservation_modes,
                    "result_type": result_type,
                    "order_by": order_by,
                    "order_type": order_type,
                    "promo_code": promo_code,
                    "rewards": rewards,
                    "language": language
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_found": total_records,
                    "available_count": len(formatted_product_avail),
                    "unavailable_count": len(formatted_product_not_avail),
                    "page": current_page,
                    "total_pages": total_pages,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {total_records} product result(s), showing page {current_page} of {total_pages}"
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
handler = GenericProductAvailRQHandler()


async def call_generic_product_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the GenericProductAvailRQ endpoint.
    
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
            
            response_text = f"""🔍 **Generic Product Availability Search Results**

✅ **Search Summary:**
- **Total Results Found**: {summary['total_found']:,}
- **Available Products**: {summary['available_count']}
- **Unavailable Products**: {summary['unavailable_count']}
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Language**: {summary['language'].upper()}

📋 **Search Criteria:**
- **Product Distributions**: {len(data['product_distributions'])} specified
"""
            if criteria["countries"]:
                response_text += f"- **Countries**: {', '.join(criteria['countries'])}\n"
            if criteria["zones"]:
                response_text += f"- **Zones**: {', '.join(criteria['zones'])}\n"
            if criteria["hotel_ids"]:
                response_text += f"- **Hotel IDs**: {len(criteria['hotel_ids'])} specified\n"
            if criteria["product_types"]:
                response_text += f"- **Product Types**: {', '.join(criteria['product_types'])}\n"
            if criteria["product_methods"]:
                response_text += f"- **Reservation Methods**: {', '.join(criteria['product_methods'])}\n"
            if criteria["reservation_modes"]:
                response_text += f"- **Reservation Modes**: {', '.join(criteria['reservation_modes'])}\n"
            if criteria["promo_code"]:
                response_text += f"- **Promo Code**: {criteria['promo_code']}\n"
            if criteria["rewards"]:
                response_text += f"- **Rewards/Loyalty**: Enabled\n"
            
            response_text += f"""
📊 **Results Summary:**
- **Result Type**: {criteria['result_type'].title()}
- **Sorted by**: {criteria['order_by'].title()} ({criteria['order_type'].upper()})

📄 **Pagination:**
- **Current Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Results Per Page**: {pagination['results_per_page']}
- **Has Next Page**: {'Yes' if pagination['has_next_page'] else 'No'}
- **Has Previous Page**: {'Yes' if pagination['has_previous_page'] else 'No'}

"""
            
            # Display available products
            if data["available_products"]:
                response_text += f"""🛍️ **Available Products ({len(data['available_products'])}):**
{'='*80}
"""
                
                for i, product in enumerate(data["available_products"], 1):
                    response_text += f"""
🛍️ **Product #{i}**
{'-'*60}

🏷️ **Product Information:**
- **Availability ID**: {product.get('availability_id', 'N/A')}
- **Product ID**: {product.get('product_id', 'N/A')}
- **Product RPH**: {product.get('product_rph', 'N/A')}
"""
                    
                    # Hotel rooms information
                    hotel_rooms = product.get('hotel_rooms', [])
                    if hotel_rooms:
                        response_text += f"""
🏨 **Hotel Rooms ({len(hotel_rooms)} available):**
"""
                        for j, room in enumerate(hotel_rooms, 1):
                            response_text += f"""
  **Room #{j}:**
  - **Availability ID**: {room.get('availability_id', 'N/A')}
  - **Hotel ID**: {room.get('hotel_id', 'N/A')}
  - **Room ID**: {room.get('room_id', 'N/A')}
  - **Quantity Available**: {room.get('quantity', 'N/A')}
"""
                            
                            # Amounts information
                            amounts = room.get('amounts', {})
                            if amounts and amounts.get('final_amount'):
                                response_text += f"""  - **Price**: {amounts.get('final_amount', 'N/A')} {amounts.get('currency', '')}
  - **Base Price**: {amounts.get('base_amount', 'N/A')} {amounts.get('currency', '')}
"""
                                if amounts.get('offers_amount') and amounts['offers_amount'] > 0:
                                    response_text += f"  - **Offers Discount**: -{amounts['offers_amount']} {amounts.get('currency', '')}\n"
                                if amounts.get('discounts_amount') and amounts['discounts_amount'] > 0:
                                    response_text += f"  - **Additional Discounts**: -{amounts['discounts_amount']} {amounts.get('currency', '')}\n"
                            
                            if room.get('distance_to_location'):
                                response_text += f"  - **Distance**: {room['distance_to_location']} km\n"
                            if room.get('url'):
                                response_text += f"  - **Booking URL**: Available\n"
                    
                    # Hotel room extras information
                    room_extras = product.get('hotel_room_extras', [])
                    if room_extras:
                        response_text += f"""
🎁 **Room Extras ({len(room_extras)} available):**
"""
                        for j, extra in enumerate(room_extras, 1):
                            response_text += f"""
  **Extra #{j}:**
  - **Extra ID**: {extra.get('extra_id', 'N/A')}
  - **Included**: {'Yes' if extra.get('included') else 'No'}
  - **Availability**: {extra.get('availability', 'N/A')}
"""
                            
                            # Extra amounts
                            extra_amounts = extra.get('extra_amounts', {})
                            if extra_amounts and extra_amounts.get('final_amount'):
                                response_text += f"""  - **Price**: {extra_amounts.get('final_amount', 'N/A')} {extra_amounts.get('currency', '')}
  - **Amount Type**: {extra_amounts.get('amount_type', 'N/A')}
"""
                    
                    response_text += "\n"
            
            # Display unavailable products
            if data["unavailable_products"]:
                response_text += f"""❌ **Unavailable Products ({len(data['unavailable_products'])}):**
{'='*80}
"""
                
                for i, product in enumerate(data["unavailable_products"], 1):
                    cause = product.get('cause', {})
                    response_text += f"""
❌ **Unavailable Product #{i}**
- **Product ID**: {product.get('product_id', 'N/A')}
- **Product RPH**: {product.get('product_rph', 'N/A')}
- **Reason Code**: {cause.get('code', 'N/A')}
- **Reason**: {cause.get('description', 'N/A')}
- **Target**: {cause.get('target', 'N/A')}

"""
            
            # Additional information sections
            if data.get("hotel_details"):
                response_text += f"🏨 **Hotel Details**: {len(data['hotel_details'])} hotel(s) included\n"
            if data.get("room_details"):
                response_text += f"🏠 **Room Details**: {len(data['room_details'])} room(s) included\n"
            if data.get("product_details"):
                response_text += f"📦 **Product Details**: {len(data['product_details'])} product(s) included\n"
            if data.get("extra_details"):
                response_text += f"🎁 **Extra Details**: {len(data['extra_details'])} extra(s) included\n"
            
            # Navigation hints
            if pagination["has_next_page"] or pagination["has_previous_page"]:
                response_text += f"""
🧭 **Navigation:**
"""
                if pagination["has_previous_page"]:
                    response_text += f"- Use page {pagination['current_page'] - 1} to see previous results\n"
                if pagination["has_next_page"]:
                    response_text += f"- Use page {pagination['current_page'] + 1} to see more results\n"
            
            if not data["available_products"] and not data["unavailable_products"]:
                response_text += """
❌ **No Products Found**

No products match your search criteria. Try:
- Adjusting your date ranges
- Changing guest configurations
- Broadening location filters
- Removing specific product type filters
- Checking different hotels or zones
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use availability IDs for basket operations
- Review pricing details for budget planning
- Check extra services for enhanced experiences
- Consider alternative dates if nothing available
- Use pagination for comprehensive results
"""
        else:
            response_text = f"""❌ **Generic Product Availability Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify product distribution parameters
- Check date formats (YYYY-MM-DD)
- Ensure guest specifications are valid
- Verify country and zone codes
- Check pagination parameters
- Review filter combinations
- Verify authentication credentials
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching for generic product availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
