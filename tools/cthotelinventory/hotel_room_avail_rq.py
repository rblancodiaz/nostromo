"""
HotelRoomAvailRQ - Hotel Room Availability Tool

This tool retrieves availability information for hotel rooms
based on specific search criteria including dates, guests, and filters.
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
HOTEL_ROOM_AVAIL_RQ_TOOL = Tool(
    name="hotel_room_avail_rq",
    description="""
    Search for hotel room availability based on dates, guests, and criteria.
    
    This tool provides comprehensive room availability information including:
    - Available room types and rates
    - Pricing details and offers
    - Board types (meal plans)
    - Cancellation policies
    - Special offers and discounts
    - Room amenities and features
    
    Parameters:
    - date_from (required): Check-in date (YYYY-MM-DD format)
    - date_to (required): Check-out date (YYYY-MM-DD format)
    - guests (required): Guest distribution per room
    - hotel_ids (optional): Specific hotel IDs to search
    - room_ids (optional): Specific room IDs to search
    - countries (optional): Country codes to filter
    - zones (optional): Zone codes to filter
    - language (optional): Language code for the request
    - show_details (optional): Include detailed information
    - result_type (optional): Type of results to return
    - order_by (optional): Sort results by criteria
    - page (optional): Page number for pagination
    - num_results (optional): Number of results per page
    
    Returns:
    - Available rooms with pricing
    - Room features and amenities
    - Board types and meal plans
    - Special offers and rates
    - Cancellation policies
    - Availability summary
    
    Example usage:
    "Search for rooms from 2024-01-15 to 2024-01-17 for 2 adults"
    "Find availability in hotel HTL123 for 2 adults and 1 child from March 1st to 5th"
    "Check room availability in Madrid for family of 4 next weekend"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Check-in date in YYYY-MM-DD format",
                "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
            },
            "date_to": {
                "type": "string",
                "description": "Check-out date in YYYY-MM-DD format",
                "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
            },
            "guests": {
                "type": "array",
                "description": "Guest distribution per room",
                "items": {
                    "type": "object",
                    "properties": {
                        "room_number": {
                            "type": "integer",
                            "description": "Room reference number",
                            "minimum": 1
                        },
                        "guests": {
                            "type": "array",
                            "description": "Guests in this room",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "age": {
                                        "type": "integer",
                                        "description": "Guest age",
                                        "minimum": 0,
                                        "maximum": 120
                                    },
                                    "amount": {
                                        "type": "integer",
                                        "description": "Number of guests of this age",
                                        "minimum": 1,
                                        "maximum": 10
                                    }
                                },
                                "required": ["age", "amount"]
                            }
                        }
                    },
                    "required": ["room_number", "guests"]
                },
                "minItems": 1,
                "maxItems": 10
            },
            "hotel_ids": {
                "type": "array",
                "description": "Specific hotel IDs to search",
                "items": {
                    "type": "string"
                },
                "maxItems": 50
            },
            "room_ids": {
                "type": "array",
                "description": "Specific room IDs to search",
                "items": {
                    "type": "string"
                },
                "maxItems": 100
            },
            "countries": {
                "type": "array",
                "description": "Country codes to filter (ISO 3166-1)",
                "items": {
                    "type": "string",
                    "minLength": 2,
                    "maxLength": 2
                },
                "maxItems": 20
            },
            "zones": {
                "type": "array",
                "description": "Zone codes to filter",
                "items": {
                    "type": "string"
                },
                "maxItems": 50
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            },
            "show_details": {
                "type": "boolean",
                "description": "Include detailed hotel and room information",
                "default": True
            },
            "result_type": {
                "type": "string",
                "description": "Type of results to return",
                "enum": ["besthotelprice", "liveprice"],
                "default": "liveprice"
            },
            "order_by": {
                "type": "string",
                "description": "Sort results by criteria",
                "enum": ["id", "hotelid", "roomid", "price", "quantity", "location", "order"],
                "default": "price"
            },
            "order_type": {
                "type": "string",
                "description": "Sort order",
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
            "promo_code": {
                "type": "string",
                "description": "Promotional code to apply"
            },
            "rewards": {
                "type": "boolean",
                "description": "Apply loyalty rewards",
                "default": False
            }
        },
        "required": ["date_from", "date_to", "guests"],
        "additionalProperties": False
    }
)


class HotelRoomAvailRQHandler:
    """Handler for the HotelRoomAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_room_avail_rq")
    
    def _format_guest_distribution(self, guests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format guest distribution for API request."""
        formatted_distribution = []
        
        for room_data in guests:
            room_rph = room_data["room_number"]
            guest_list = []
            
            for guest in room_data["guests"]:
                guest_list.append({
                    "Age": guest["age"],
                    "Amount": guest["amount"]
                })
            
            formatted_distribution.append({
                "HotelRoomRPH": room_rph,
                "DateFrom": "",  # Will be set later
                "DateTo": "",    # Will be set later
                "Guest": guest_list
            })
        
        return formatted_distribution
    
    def _format_amounts_detail(self, amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Format amount details for readable output."""
        if not amounts:
            return {}
            
        return {
            "currency": amounts.get("Currency"),
            "final_amount": amounts.get("AmountFinal"),
            "total_amount": amounts.get("AmountTotal"),
            "base_amount": amounts.get("AmountBase"),
            "taxes": amounts.get("AmountTaxes"),
            "tourist_tax": amounts.get("AmountTouristTax"),
            "offers": amounts.get("AmountOffers"),
            "discounts": amounts.get("AmountDiscounts"),
            "extras": amounts.get("AmountExtras"),
            "deposit": amounts.get("AmountDeposit")
        }
    
    def _format_hotel_room_avail(self, room_avail: Dict[str, Any]) -> Dict[str, Any]:
        """Format room availability information for readable output."""
        formatted = {
            "availability_id": room_avail.get("HotelRoomAvailabilityId"),
            "hotel_id": room_avail.get("HotelId"),
            "hotel_hash": room_avail.get("HotelHash"),
            "room_id": room_avail.get("HotelRoomId"),
            "room_rph": room_avail.get("HotelRoomRPH"),
            "package_id": room_avail.get("PackageId"),
            "product_id": room_avail.get("ProductId"),
            "quantity": room_avail.get("Quantity"),
            "distance_to_location": room_avail.get("DistanceToLocation"),
            "booking_url": room_avail.get("HotelRoomAvailURL")
        }
        
        # Format amounts
        amounts = room_avail.get("AmountsDetail", {})
        if amounts:
            formatted["amounts"] = self._format_amounts_detail(amounts)
        
        # Format rates
        rates = room_avail.get("HotelRateAvail", [])
        if rates:
            formatted["rates"] = []
            for rate in rates:
                rate_detail = rate.get("HotelRateDetail", {})
                formatted["rates"].append({
                    "rate_id": rate_detail.get("HotelRateId"),
                    "rate_name": rate_detail.get("HotelRateName"),
                    "rate_description": rate_detail.get("HotelRateDescription"),
                    "type": rate_detail.get("Type"),
                    "discount_type": rate_detail.get("TypeDiscount"),
                    "value": rate_detail.get("Value"),
                    "promo_code": rate_detail.get("PromoCode"),
                    "dates": rate.get("Date", [])
                })
        
        # Format board types
        boards = room_avail.get("HotelBoardAvail", [])
        if boards:
            formatted["board_types"] = []
            for board in boards:
                board_detail = board.get("HotelBoardDetail", {})
                board_type = board_detail.get("HotelBoardType", {})
                formatted["board_types"].append({
                    "board_id": board_detail.get("HotelBoardId"),
                    "board_name": board_detail.get("HotelBoardName"),
                    "board_description": board_detail.get("HotelBoardDescription"),
                    "board_type_code": board_type.get("Code"),
                    "board_type_name": board_type.get("Name"),
                    "dates": board.get("Date", [])
                })
        
        # Format offers
        offers = room_avail.get("HotelOfferAvail", [])
        if offers:
            formatted["offers"] = []
            for offer in offers:
                offer_detail = offer.get("HotelOfferDetail", {})
                formatted["offers"].append({
                    "offer_id": offer_detail.get("HotelOfferId"),
                    "offer_name": offer_detail.get("HotelOfferName"),
                    "offer_description": offer_detail.get("HotelOfferDescription"),
                    "type": offer_detail.get("Type"),
                    "discount_type": offer_detail.get("TypeDiscount"),
                    "order": offer_detail.get("Order"),
                    "promo_codes": offer_detail.get("PromoCodes", []),
                    "dates": offer.get("Date", [])
                })
        
        # Format cancellation penalties
        penalties = room_avail.get("BookingCancelPenalty", [])
        if penalties:
            formatted["cancellation_policies"] = []
            for penalty in penalties:
                formatted["cancellation_policies"].append({
                    "date_from": penalty.get("DateFrom"),
                    "date_to": penalty.get("DateTo"),
                    "value": penalty.get("Value"),
                    "type": penalty.get("Type"),
                    "name": penalty.get("Name"),
                    "description": penalty.get("Description"),
                    "amounts": self._format_amounts_detail(penalty.get("PenaltyAmountsDetail", {}))
                })
        
        # Format scheduled payments
        payments = room_avail.get("ScheduledPayment", [])
        if payments:
            formatted["scheduled_payments"] = []
            for payment in payments:
                formatted["scheduled_payments"].append({
                    "plan_id": payment.get("PaymentPlanId"),
                    "method": payment.get("PaymentMethod"),
                    "exec_date": payment.get("ExecDate"),
                    "amount_to_pay": payment.get("AmountToPay"),
                    "currency": payment.get("Currency"),
                    "when_pay": payment.get("WhenPay")
                })
        
        # Format type result
        type_result = room_avail.get("TypeResult", [])
        if type_result:
            formatted["type_result"] = type_result
        
        return formatted
    
    def _format_hotel_room_not_avail(self, room_not_avail: Dict[str, Any]) -> Dict[str, Any]:
        """Format room not available information for readable output."""
        formatted = {
            "hotel_id": room_not_avail.get("HotelId"),
            "hotel_hash": room_not_avail.get("HotelHash"),
            "room_id": room_not_avail.get("HotelRoomId"),
            "room_rph": room_not_avail.get("HotelRoomRPH"),
            "package_id": room_not_avail.get("PackageId"),
            "distance_to_location": room_not_avail.get("DistanceToLocation")
        }
        
        # Format cause
        cause = room_not_avail.get("Cause", {})
        if cause:
            formatted["cause"] = {
                "code": cause.get("Code"),
                "description": cause.get("Description"),
                "target": cause.get("Target")
            }
        
        return formatted
    
    def _format_hotel_basic_detail(self, hotel: Dict[str, Any]) -> Dict[str, Any]:
        """Format hotel basic information for readable output."""
        formatted = {
            "hotel_id": hotel.get("HotelId"),
            "hotel_hash": hotel.get("HotelHash"),
            "hotel_name": hotel.get("HotelName"),
            "hotel_description": hotel.get("HotelDescription"),
            "currency": hotel.get("Currency"),
            "rewards": hotel.get("Rewards"),
            "hotel_mode": hotel.get("HotelMode"),
            "hotel_view": hotel.get("HotelView"),
            "timezone": hotel.get("TimeZone"),
            "first_day_with_price": hotel.get("FirstDayWithPrice"),
            "opening_date": hotel.get("OpeningDate"),
            "closing_date": hotel.get("ClosingDate"),
            "reopening_date": hotel.get("ReopeningDate")
        }
        
        # Format location
        location = hotel.get("HotelLocation", {})
        if location:
            formatted["location"] = {
                "address": location.get("Address"),
                "city": location.get("City"),
                "postal_code": location.get("PostalCode"),
                "latitude": location.get("Latitude"),
                "longitude": location.get("Longitude")
            }
            
            # Format zones
            zones = location.get("Zone", [])
            if zones:
                formatted["location"]["zones"] = []
                for zone in zones:
                    formatted["location"]["zones"].append({
                        "code": zone.get("Code"),
                        "name": zone.get("Name")
                    })
        
        # Format guest types
        guest_types = hotel.get("HotelGuestType", [])
        if guest_types:
            formatted["guest_types"] = []
            for guest_type in guest_types:
                formatted["guest_types"].append({
                    "type": guest_type.get("GuestType"),
                    "min_age": guest_type.get("MinAge"),
                    "max_age": guest_type.get("MaxAge")
                })
        
        # Format hotel types
        hotel_types = hotel.get("HotelType", [])
        if hotel_types:
            formatted["hotel_types"] = []
            for hotel_type in hotel_types:
                formatted["hotel_types"].append({
                    "code": hotel_type.get("Code"),
                    "name": hotel_type.get("Name")
                })
        
        return formatted
    
    def _format_hotel_room_basic_detail(self, room: Dict[str, Any]) -> Dict[str, Any]:
        """Format room basic information for readable output."""
        formatted = {
            "hotel_id": room.get("HotelId"),
            "hotel_hash": room.get("HotelHash"),
            "hotel_name": room.get("HotelName"),
            "room_id": room.get("HotelRoomId"),
            "room_name": room.get("HotelRoomName"),
            "room_description": room.get("HotelRoomDescription"),
            "room_area": room.get("HotelRoomArea"),
            "hidden": room.get("Hidden"),
            "order": room.get("Order"),
            "upgrade_class": room.get("UpgradeClass"),
            "upgrade_allowed": room.get("UpgradeAllowed")
        }
        
        # Format room types
        room_types = room.get("HotelRoomType", [])
        if room_types:
            formatted["room_types"] = []
            for room_type in room_types:
                formatted["room_types"].append({
                    "code": room_type.get("Code"),
                    "name": room_type.get("Name")
                })
        
        # Format occupancy
        occupancy = room.get("HotelRoomOccupancy", {})
        if occupancy:
            formatted["occupancy"] = {
                "min": occupancy.get("Min"),
                "max": occupancy.get("Max")
            }
            
            guest_occupancy = occupancy.get("HotelRoomGuestOccupancy", [])
            if guest_occupancy:
                formatted["occupancy"]["guest_restrictions"] = []
                for restriction in guest_occupancy:
                    formatted["occupancy"]["guest_restrictions"].append({
                        "code": restriction.get("Code"),
                        "min_age": restriction.get("MinAge"),
                        "max_age": restriction.get("MaxAge"),
                        "min": restriction.get("Min"),
                        "max": restriction.get("Max")
                    })
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel room availability request.
        
        Args:
            arguments: Tool arguments containing search criteria
            
        Returns:
            Dictionary containing the room availability results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            guests = arguments.get("guests", [])
            hotel_ids = arguments.get("hotel_ids", [])
            room_ids = arguments.get("room_ids", [])
            countries = arguments.get("countries", [])
            zones = arguments.get("zones", [])
            language = arguments.get("language", "es")
            show_details = arguments.get("show_details", True)
            result_type = arguments.get("result_type", "liveprice")
            order_by = arguments.get("order_by", "price")
            order_type = arguments.get("order_type", "asc")
            page = arguments.get("page", 1)
            num_results = arguments.get("num_results", 20)
            promo_code = arguments.get("promo_code")
            rewards = arguments.get("rewards", False)
            
            # Validate required fields
            if not date_from or not date_to:
                raise ValidationError("Check-in and check-out dates are required")
            
            if not guests:
                raise ValidationError("Guest information is required")
            
            # Validate date format and logic
            from datetime import datetime
            try:
                checkin_date = datetime.strptime(date_from, "%Y-%m-%d")
                checkout_date = datetime.strptime(date_to, "%Y-%m-%d")
                if checkout_date <= checkin_date:
                    raise ValidationError("Check-out date must be after check-in date")
            except ValueError:
                raise ValidationError("Invalid date format. Use YYYY-MM-DD")
            
            self.logger.info(
                "Searching room availability",
                date_from=date_from,
                date_to=date_to,
                guest_rooms=len(guests),
                hotel_count=len(hotel_ids),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            # Format guest distribution
            hotel_room_distribution = self._format_guest_distribution(guests)
            for distribution in hotel_room_distribution:
                distribution["DateFrom"] = date_from
                distribution["DateTo"] = date_to
            
            request_payload["HotelRoomDistribution"] = hotel_room_distribution
            
            # Add optional filters
            if countries:
                request_payload["Country"] = countries
            if zones:
                request_payload["Zone"] = zones
            if hotel_ids:
                request_payload["HotelId"] = hotel_ids
            if room_ids:
                request_payload["HotelRoomId"] = room_ids
            
            # Add search options
            request_payload["ResultType"] = result_type
            request_payload["OrderBy"] = order_by
            request_payload["OrderType"] = order_type
            request_payload["Page"] = page
            request_payload["NumResults"] = num_results
            request_payload["ShowHotelBasicDetail"] = show_details
            request_payload["ShowHotelRoomBasicDetail"] = show_details
            request_payload["ShowHotelRoomNotAvailability"] = True
            
            if promo_code:
                request_payload["PromoCode"] = promo_code
            if rewards:
                request_payload["Rewards"] = rewards
            
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
                
                # Make the room availability request
                response = await client.post("/HotelRoomAvailRQ", request_payload)
            
            # Extract availability data from response
            current_page = response.get("CurrentPage", 1)
            total_pages = response.get("TotalPages", 1)
            total_records = response.get("TotalRecords", 0)
            total_groups = response.get("TotalGroups", 0)
            
            # Extract distribution data
            distribution_data = response.get("HotelRoomDistribution", [])
            
            # Extract hotel details
            hotel_details = []
            if show_details:
                hotels_raw = response.get("HotelBasicDetail", [])
                for hotel in hotels_raw:
                    hotel_details.append(self._format_hotel_basic_detail(hotel))
            
            # Extract room details
            room_details = []
            if show_details:
                rooms_raw = response.get("HotelRoomBasicDetail", [])
                for room in rooms_raw:
                    room_details.append(self._format_hotel_room_basic_detail(room))
            
            # Extract available rooms
            available_rooms = []
            rooms_avail_raw = response.get("HotelRoomAvail", [])
            for room_avail in rooms_avail_raw:
                available_rooms.append(self._format_hotel_room_avail(room_avail))
            
            # Extract not available rooms
            not_available_rooms = []
            rooms_not_avail_raw = response.get("HotelRoomNotAvail", [])
            for room_not_avail in rooms_not_avail_raw:
                not_available_rooms.append(self._format_hotel_room_not_avail(room_not_avail))
            
            # Log successful operation
            self.logger.info(
                "Room availability search completed",
                available_count=len(available_rooms),
                not_available_count=len(not_available_rooms),
                total_records=total_records,
                current_page=current_page,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "date_from": date_from,
                    "date_to": date_to,
                    "guests": guests,
                    "hotel_ids": hotel_ids,
                    "room_ids": room_ids,
                    "countries": countries,
                    "zones": zones,
                    "promo_code": promo_code,
                    "rewards": rewards
                },
                "pagination": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "total_records": total_records,
                    "total_groups": total_groups,
                    "page_size": num_results
                },
                "available_rooms": available_rooms,
                "not_available_rooms": not_available_rooms,
                "hotel_details": hotel_details,
                "room_details": room_details,
                "distribution_data": distribution_data,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_available": len(available_rooms),
                    "total_not_available": len(not_available_rooms),
                    "total_hotels": len(hotel_details),
                    "total_room_types": len(room_details),
                    "language": language,
                    "result_type": result_type
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(available_rooms)} available room options"
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
handler = HotelRoomAvailRQHandler()


async def call_hotel_room_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelRoomAvailRQ endpoint.
    
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
            search_criteria = data["search_criteria"]
            
            response_text = f"""🏨 **Hotel Room Availability Search Results**

✅ **Search Summary:**
- **Check-in**: {search_criteria['date_from']}
- **Check-out**: {search_criteria['date_to']}
- **Available Rooms**: {summary['total_available']} options
- **Not Available**: {summary['total_not_available']} rooms
- **Hotels Found**: {summary['total_hotels']}
- **Room Types**: {summary['total_room_types']}
- **Language**: {summary['language'].upper()}

📊 **Pagination:**
- **Page**: {pagination['current_page']} of {pagination['total_pages']}
- **Total Results**: {pagination['total_records']}
- **Results per Page**: {pagination['page_size']}

"""
            
            # Display guest information
            response_text += f"""👥 **Guest Distribution:**
"""
            for i, room_guest in enumerate(search_criteria['guests'], 1):
                response_text += f"- **Room {room_guest['room_number']}**: "
                guest_details = []
                for guest in room_guest['guests']:
                    if guest['amount'] == 1:
                        guest_details.append(f"{guest['amount']} guest age {guest['age']}")
                    else:
                        guest_details.append(f"{guest['amount']} guests age {guest['age']}")
                response_text += ", ".join(guest_details) + "\n"
            
            # Display search filters if any
            filters_applied = []
            if search_criteria.get('hotel_ids'):
                filters_applied.append(f"Hotels: {', '.join(search_criteria['hotel_ids'][:3])}{'...' if len(search_criteria['hotel_ids']) > 3 else ''}")
            if search_criteria.get('countries'):
                filters_applied.append(f"Countries: {', '.join(search_criteria['countries'])}")
            if search_criteria.get('zones'):
                filters_applied.append(f"Zones: {', '.join(search_criteria['zones'][:3])}{'...' if len(search_criteria['zones']) > 3 else ''}")
            if search_criteria.get('promo_code'):
                filters_applied.append(f"Promo Code: {search_criteria['promo_code']}")
            if search_criteria.get('rewards'):
                filters_applied.append("Loyalty Rewards Applied")
            
            if filters_applied:
                response_text += f"""
🔍 **Applied Filters:**
{chr(10).join([f"- {filter_item}" for filter_item in filters_applied])}
"""
            
            # Display available rooms
            if data["available_rooms"]:
                response_text += f"""
{'='*70}
🏨 **AVAILABLE ROOM OPTIONS**
{'='*70}
"""
                
                for i, room in enumerate(data["available_rooms"][:10], 1):  # Show first 10 results
                    amounts = room.get("amounts", {})
                    final_amount = amounts.get("final_amount", 0)
                    currency = amounts.get("currency", "EUR")
                    
                    response_text += f"""
🏠 **Option #{i}**
- **Hotel**: {room.get('hotel_id', 'N/A')}
- **Room**: {room.get('room_id', 'N/A')}
- **Availability ID**: {room.get('availability_id', 'N/A')}
- **Quantity Available**: {room.get('quantity', 'N/A')}
- **💰 Final Price**: {final_amount:.2f} {currency}
"""
                    
                    # Show price breakdown if available
                    if amounts:
                        base_amount = amounts.get("base_amount")
                        taxes = amounts.get("taxes")
                        offers = amounts.get("offers")
                        discounts = amounts.get("discounts")
                        
                        if any([base_amount, taxes, offers, discounts]):
                            response_text += f"  **Price Breakdown**:\n"
                            if base_amount:
                                response_text += f"  - Base Price: {base_amount:.2f} {currency}\n"
                            if taxes:
                                response_text += f"  - Taxes: {taxes:.2f} {currency}\n"
                            if offers:
                                response_text += f"  - Offers: -{offers:.2f} {currency}\n"
                            if discounts:
                                response_text += f"  - Discounts: -{discounts:.2f} {currency}\n"
                    
                    # Show board types
                    board_types = room.get("board_types", [])
                    if board_types:
                        response_text += f"  **🍽️ Meal Plans**:\n"
                        for board in board_types[:3]:  # Show first 3 board types
                            response_text += f"  - {board.get('board_name', 'N/A')}: {board.get('board_description', 'N/A')}\n"
                    
                    # Show special offers
                    offers = room.get("offers", [])
                    if offers:
                        response_text += f"  **🎁 Special Offers**:\n"
                        for offer in offers[:2]:  # Show first 2 offers
                            response_text += f"  - {offer.get('offer_name', 'N/A')}: {offer.get('offer_description', 'N/A')[:100]}...\n"
                    
                    # Show cancellation policy
                    cancellation = room.get("cancellation_policies", [])
                    if cancellation:
                        policy = cancellation[0]  # Show first policy
                        response_text += f"  **📋 Cancellation**: {policy.get('description', 'Check policies')}\n"
                    
                    # Show distance if available
                    distance = room.get("distance_to_location")
                    if distance:
                        response_text += f"  **📍 Distance**: {distance:.2f} km\n"
                    
                    response_text += "\n"
                
                if len(data["available_rooms"]) > 10:
                    response_text += f"""... and {len(data["available_rooms"]) - 10} more available options
                    
**💡 Tip**: Use pagination parameters to see more results or refine your search criteria.
"""
            
            # Display hotel details if available
            if data["hotel_details"]:
                response_text += f"""
{'='*70}
🏨 **HOTEL INFORMATION**
{'='*70}
"""
                
                for hotel in data["hotel_details"][:5]:  # Show first 5 hotels
                    response_text += f"""
🏨 **{hotel.get('hotel_name', 'Unknown Hotel')}**
- **Hotel ID**: {hotel.get('hotel_id', 'N/A')}
- **Description**: {hotel.get('hotel_description', 'N/A')[:150]}{'...' if len(hotel.get('hotel_description', '')) > 150 else ''}
- **Currency**: {hotel.get('currency', 'N/A')}
- **Mode**: {hotel.get('hotel_mode', 'N/A').title()}
"""
                    
                    location = hotel.get("location", {})
                    if location:
                        response_text += f"- **Location**: {location.get('city', 'N/A')}, {location.get('address', 'N/A')}\n"
                    
                    response_text += "\n"
                
                if len(data["hotel_details"]) > 5:
                    response_text += f"""... and {len(data["hotel_details"]) - 5} more hotels
"""
            
            # Display not available rooms summary
            if data["not_available_rooms"]:
                response_text += f"""
{'='*70}
❌ **NOT AVAILABLE ROOMS** ({len(data["not_available_rooms"])})
{'='*70}

**Common reasons for unavailability:**
"""
                
                # Count causes
                causes = {}
                for room in data["not_available_rooms"]:
                    cause = room.get("cause", {})
                    cause_desc = cause.get("description", "Unknown")
                    causes[cause_desc] = causes.get(cause_desc, 0) + 1
                
                for cause, count in list(causes.items())[:5]:
                    response_text += f"- **{cause}**: {count} room(s)\n"
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Next Steps:**
- Use the availability IDs to add rooms to a basket
- Check room details for more information
- Apply filters to refine your search
- Contact hotels directly for special requests
"""
        else:
            response_text = f"""❌ **Room Availability Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify your check-in and check-out dates
- Ensure guest information is correctly formatted
- Check if hotels exist in the specified locations
- Verify date format (YYYY-MM-DD)
- Try adjusting your search criteria
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching room availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
