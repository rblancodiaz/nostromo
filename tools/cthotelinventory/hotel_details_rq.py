"""
HotelDetailsRQ - Get Hotel Details Tool

This tool retrieves comprehensive detailed information about specific hotels
in the Neobookings system.
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
HOTEL_DETAILS_RQ_TOOL = Tool(
    name="hotel_details_rq",
    description="""
    Retrieve comprehensive detailed information about specific hotels.
    
    This tool provides complete hotel information including:
    - Basic hotel information (name, description, location)
    - Contact information and social media
    - Hotel amenities and services
    - Guest types and age restrictions
    - Media gallery (photos, videos)
    - Payment and billing configuration
    - Booking conditions and policies
    - SEO and marketing settings
    - Loyalty programs and rewards
    
    Parameters:
    - hotel_ids (required): List of hotel identifiers to get details for
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Complete hotel profile information
    - Location and contact details
    - Amenities and service listings
    - Policies and terms
    - Configuration settings
    
    Example usage:
    "Get detailed information for hotel 'HTL123'"
    "Show me complete details for hotels 'HTL123' and 'HTL456'"
    "Retrieve full hotel profile for 'HTL789'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to get details for",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "minItems": 1,
                "maxItems": 20
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["hotel_ids"],
        "additionalProperties": False
    }
)


class HotelDetailsRQHandler:
    """Handler for the HotelDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_details_rq")
    
    def _format_location(self, location: Dict[str, Any]) -> Dict[str, Any]:
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
        
        # Format state and country
        state = location.get("State", {})
        if state:
            formatted["state"] = {
                "code": state.get("Code"),
                "name": state.get("Name")
            }
        
        country = location.get("Country", {})
        if country:
            formatted["country"] = {
                "code": country.get("Code"),
                "name": country.get("Name")
            }
        
        return formatted
    
    def _format_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Format hotel contact information for readable output."""
        if not contact:
            return {}
            
        formatted = {
            "phone": contact.get("Phone"),
            "fax": contact.get("Fax"),
            "email": contact.get("Email"),
            "cif": contact.get("CIF"),
            "url": contact.get("Url"),
            "url_steps": contact.get("UrlSteps")
        }
        
        # Format social media
        social_media = contact.get("SocialMedia", {})
        if social_media:
            formatted["social_media"] = {
                "facebook": social_media.get("Facebook"),
                "twitter": social_media.get("Twitter"),
                "instagram": social_media.get("Instagram"),
                "youtube": social_media.get("Youtube"),
                "tripadvisor": social_media.get("TripAdvisor"),
                "whatsapp": social_media.get("Whatsapp")
            }
        
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
    
    def _format_config_steps(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Format configuration steps information for readable output."""
        if not config:
            return {}
            
        formatted = {
            "free_babies": config.get("FreeBabies", False),
            "allow_modifications": config.get("AllowModifications", False),
            "allow_card_modification": config.get("AllowCardModification", False),
            "allow_room_upgrade": config.get("AllowRoomUpgrade"),
            "show_capacity": config.get("ShowCapacity", False),
            "show_offers_on_mobile": config.get("ShowOffersOnMobile", False),
            "show_extras_on_mobile": config.get("ShowExtrasOnMobile", False),
            "maximum_per_room_type": config.get("MaximumPerRoomType"),
            "modification_allowed_type": config.get("ModificationAllowedType"),
            "cancellation_allowed_type": config.get("CancellationAllowedType")
        }
        
        # Format check-in/check-out times
        checkin = config.get("CheckIn", {})
        if checkin:
            formatted["checkin"] = {
                "from": checkin.get("From"),
                "to": checkin.get("To")
            }
        
        checkout = config.get("CheckOut", {})
        if checkout:
            formatted["checkout"] = {
                "from": checkout.get("From"),
                "to": checkout.get("To")
            }
        
        return formatted
    
    def _format_payment_config(self, payment_config: Dict[str, Any]) -> Dict[str, Any]:
        """Format payment configuration information for readable output."""
        if not payment_config:
            return {}
            
        return {
            "plan_type": payment_config.get("NeoPaymentsPlanType"),
            "manual_charges_web": payment_config.get("ManualChargesWeb", False),
            "manual_charges_channel": payment_config.get("ManualChargesChannel", False),
            "manual_returns_web": payment_config.get("ManualReturnsWeb", False),
            "manual_returns_channel": payment_config.get("ManualReturnsChannel", False),
            "auto_tokenize_web": payment_config.get("AutoTokenizeWeb", False),
            "auto_tokenize_channel": payment_config.get("AutoTokenizeChannel", False),
            "auto_payment_web": payment_config.get("AutoPaymentWeb", False),
            "auto_payment_channel": payment_config.get("AutoPaymentChannel", False),
            "pay_by_link": payment_config.get("PayByLink", False)
        }
    
    def _format_accepted_cards(self, cards: Dict[str, Any]) -> Dict[str, Any]:
        """Format accepted cards information for readable output."""
        if not cards:
            return {}
            
        return {
            "cvv_required": cards.get("Cvv", False),
            "american_express": cards.get("AmericanExpress", False),
            "mastercard": cards.get("MasterCard", False),
            "visa": cards.get("Visa", False),
            "diners": cards.get("Diners", False),
            "apple_pay": cards.get("ApplePay", False),
            "google_pay": cards.get("GooglePay", False)
        }
    
    def _format_hotel_detail(self, hotel_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format complete hotel detail information for readable output."""
        formatted = {
            "hotel_id": hotel_detail.get("HotelId"),
            "hotel_hash": hotel_detail.get("HotelHash"),
            "hotel_name": hotel_detail.get("HotelName"),
            "hotel_description": hotel_detail.get("HotelDescription"),
            "logo": hotel_detail.get("Logo"),
            "currency": hotel_detail.get("Currency"),
            "opening_date": hotel_detail.get("OpeningDate"),
            "closing_date": hotel_detail.get("ClosingDate"),
            "reopening_date": hotel_detail.get("ReopeningDate"),
            "first_day_with_price": hotel_detail.get("FirstDayWithPrice"),
            "hotel_mode": hotel_detail.get("HotelMode"),
            "hotel_view": hotel_detail.get("HotelView"),
            "timezone": hotel_detail.get("TimeZone")
        }
        
        # Format location
        location = hotel_detail.get("HotelLocation", {})
        if location:
            formatted["location"] = self._format_location(location)
        
        # Format contact
        contact = hotel_detail.get("HotelContact", {})
        if contact:
            formatted["contact"] = self._format_contact(contact)
        
        # Format guest types
        guest_types = hotel_detail.get("HotelGuestType", [])
        if guest_types:
            formatted["guest_types"] = self._format_guest_types(guest_types)
        
        # Format amenities
        amenities = hotel_detail.get("HotelAmenity", [])
        if amenities:
            formatted["amenities"] = self._format_amenities(amenities)
        
        # Format media
        media = hotel_detail.get("Media", [])
        if media:
            formatted["media"] = self._format_media(media)
        
        # Format configuration
        config_steps = hotel_detail.get("ConfigSteps", {})
        if config_steps:
            formatted["config_steps"] = self._format_config_steps(config_steps)
        
        # Format payment configuration
        payment_config = hotel_detail.get("HotelPaymentConfig", {})
        if payment_config:
            formatted["payment_config"] = self._format_payment_config(payment_config)
        
        # Format accepted cards
        accepted_cards = hotel_detail.get("HotelAcceptedCards", {})
        if accepted_cards:
            formatted["accepted_cards"] = self._format_accepted_cards(accepted_cards)
        
        # Add policies and conditions
        formatted["booking_conditions"] = hotel_detail.get("BookingConditions")
        formatted["booking_cancellation_policy"] = hotel_detail.get("BookingCancellationPolicy")
        formatted["privacy_policy"] = hotel_detail.get("PrivacyPolicy")
        
        # Format languages
        languages = hotel_detail.get("Language", [])
        if languages:
            formatted["languages"] = []
            for lang in languages:
                formatted["languages"].append({
                    "code": lang.get("Code"),
                    "native": lang.get("Native", False)
                })
        
        # Format hotel types and categories
        hotel_types = hotel_detail.get("HotelType", [])
        if hotel_types:
            formatted["hotel_types"] = []
            for hotel_type in hotel_types:
                formatted["hotel_types"].append({
                    "code": hotel_type.get("Code"),
                    "name": hotel_type.get("Name")
                })
        
        categories = hotel_detail.get("HotelCategory", [])
        if categories:
            formatted["categories"] = []
            for category in categories:
                formatted["categories"].append({
                    "code": category.get("Code"),
                    "name": category.get("Name")
                })
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel details request.
        
        Args:
            arguments: Tool arguments containing hotel IDs
            
        Returns:
            Dictionary containing the hotel details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids", [])
            language = arguments.get("language", "es")
            
            # Validate hotel IDs
            if not hotel_ids:
                raise ValidationError("At least one hotel ID is required")
            
            if not isinstance(hotel_ids, list):
                raise ValidationError("hotel_ids must be a list")
            
            # Sanitize hotel IDs
            sanitized_hotel_ids = []
            for hotel_id in hotel_ids:
                if not isinstance(hotel_id, str) or not hotel_id.strip():
                    raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            self.logger.info(
                "Retrieving hotel details",
                hotel_count=len(sanitized_hotel_ids),
                hotel_ids=sanitized_hotel_ids,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
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
                
                # Make the hotel details request
                response = await client.post("/HotelDetailsRQ", request_payload)
            
            # Extract hotel details from response
            hotel_details_raw = response.get("HotelDetail", [])
            
            # Format hotel details
            formatted_hotels = []
            for hotel_detail in hotel_details_raw:
                formatted_hotels.append(self._format_hotel_detail(hotel_detail))
            
            # Log successful operation
            self.logger.info(
                "Hotel details retrieved successfully",
                hotel_count=len(formatted_hotels),
                found_hotels=len(hotel_details_raw),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "hotel_details": formatted_hotels,
                "requested_hotel_ids": sanitized_hotel_ids,
                "found_count": len(formatted_hotels),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "requested_count": len(sanitized_hotel_ids),
                    "found_count": len(formatted_hotels),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {len(formatted_hotels)} hotel(s)"
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
handler = HotelDetailsRQHandler()


async def call_hotel_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelDetailsRQ endpoint.
    
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
            
            response_text = f"""🏨 **Hotel Details Retrieved**

✅ **Summary:**
- **Requested**: {summary['requested_count']} hotel(s)
- **Found**: {summary['found_count']} hotel(s)
- **Language**: {summary['language'].upper()}

"""
            
            # Display details for each hotel
            for i, hotel in enumerate(data["hotel_details"], 1):
                response_text += f"""
{'='*70}
🏨 **Hotel #{i}: {hotel.get('hotel_name', 'Unknown Hotel')}**
{'='*70}

🏷️ **Basic Information:**
- **Hotel ID**: {hotel.get('hotel_id', 'N/A')}
- **Name**: {hotel.get('hotel_name', 'N/A')}
- **Description**: {hotel.get('hotel_description', 'N/A')[:200]}{'...' if len(hotel.get('hotel_description', '')) > 200 else ''}
- **Currency**: {hotel.get('currency', 'N/A')}
- **Mode**: {hotel.get('hotel_mode', 'N/A').title()}
- **View**: {hotel.get('hotel_view', 'N/A').title()}
- **Timezone**: {hotel.get('timezone', 'N/A')}
"""
                
                # Location information
                location = hotel.get('location', {})
                if location and any(location.values()):
                    response_text += f"""
📍 **Location:**
- **Address**: {location.get('address', 'N/A')}
- **City**: {location.get('city', 'N/A')}
- **Postal Code**: {location.get('postal_code', 'N/A')}
- **Coordinates**: {location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}
"""
                    
                    country = location.get('country', {})
                    state = location.get('state', {})
                    if country:
                        response_text += f"- **Country**: {country.get('name', 'N/A')} ({country.get('code', 'N/A')})\n"
                    if state:
                        response_text += f"- **State**: {state.get('name', 'N/A')} ({state.get('code', 'N/A')})\n"
                
                # Contact information
                contact = hotel.get('contact', {})
                if contact and any(contact.values()):
                    response_text += f"""
📞 **Contact Information:**
- **Phone**: {contact.get('phone', 'N/A')}
- **Email**: {contact.get('email', 'N/A')}
- **Website**: {contact.get('url', 'N/A')}
- **CIF**: {contact.get('cif', 'N/A')}
"""
                    
                    social_media = contact.get('social_media', {})
                    if social_media and any(social_media.values()):
                        response_text += f"""
📱 **Social Media:**
"""
                        for platform, url in social_media.items():
                            if url:
                                response_text += f"- **{platform.title()}**: {url}\n"
                
                # Guest types
                guest_types = hotel.get('guest_types', [])
                if guest_types:
                    response_text += f"""
👥 **Guest Types:**
"""
                    for guest_type in guest_types:
                        response_text += f"- **{guest_type['type'].upper()}**: Ages {guest_type['min_age']}-{guest_type['max_age']}\n"
                
                # Hotel types and categories
                hotel_types = hotel.get('hotel_types', [])
                if hotel_types:
                    response_text += f"""
🏷️ **Hotel Types**: {', '.join([ht['name'] for ht in hotel_types])}
"""
                
                categories = hotel.get('categories', [])
                if categories:
                    response_text += f"""🌟 **Categories**: {', '.join([cat['name'] for cat in categories])}
"""
                
                # Amenities
                amenities = hotel.get('amenities', [])
                if amenities:
                    response_text += f"""
🎯 **Amenities** ({len(amenities)} available):
"""
                    for amenity in amenities[:10]:  # Show first 10 amenities
                        response_text += f"- {amenity['name']}\n"
                    if len(amenities) > 10:
                        response_text += f"... and {len(amenities) - 10} more amenities\n"
                
                # Configuration
                config = hotel.get('config_steps', {})
                if config and any(config.values()):
                    response_text += f"""
⚙️ **Configuration:**
- **Free Babies**: {'Yes' if config.get('free_babies') else 'No'}
- **Allow Modifications**: {'Yes' if config.get('allow_modifications') else 'No'}
- **Room Upgrades**: {config.get('allow_room_upgrade', 'N/A').title()}
- **Show Capacity**: {'Yes' if config.get('show_capacity') else 'No'}
"""
                    
                    checkin = config.get('checkin', {})
                    checkout = config.get('checkout', {})
                    if checkin:
                        response_text += f"- **Check-in**: {checkin.get('from', 'N/A')} - {checkin.get('to', 'N/A')}\n"
                    if checkout:
                        response_text += f"- **Check-out**: {checkout.get('from', 'N/A')} - {checkout.get('to', 'N/A')}\n"
                
                # Payment information
                payment_config = hotel.get('payment_config', {})
                if payment_config and any(payment_config.values()):
                    response_text += f"""
💳 **Payment Configuration:**
- **Plan Type**: {payment_config.get('plan_type', 'N/A')}
- **Manual Charges (Web)**: {'Yes' if payment_config.get('manual_charges_web') else 'No'}
- **Auto Payment (Web)**: {'Yes' if payment_config.get('auto_payment_web') else 'No'}
- **Pay by Link**: {'Yes' if payment_config.get('pay_by_link') else 'No'}
"""
                
                # Accepted cards
                accepted_cards = hotel.get('accepted_cards', {})
                if accepted_cards and any(accepted_cards.values()):
                    response_text += f"""
💳 **Accepted Cards:**
- **Visa**: {'Yes' if accepted_cards.get('visa') else 'No'}
- **MasterCard**: {'Yes' if accepted_cards.get('mastercard') else 'No'}
- **American Express**: {'Yes' if accepted_cards.get('american_express') else 'No'}
- **Apple Pay**: {'Yes' if accepted_cards.get('apple_pay') else 'No'}
- **Google Pay**: {'Yes' if accepted_cards.get('google_pay') else 'No'}
"""
                
                # Media
                media = hotel.get('media', [])
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
                
                # Dates
                response_text += f"""
📅 **Important Dates:**
- **Opening Date**: {hotel.get('opening_date', 'N/A')}
- **Closing Date**: {hotel.get('closing_date', 'N/A')}
- **Reopening Date**: {hotel.get('reopening_date', 'N/A')}
- **First Day with Price**: {hotel.get('first_day_with_price', 'N/A')}
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Hotel Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel IDs exist and are accessible
- Check your authentication credentials
- Ensure you have permission to view these hotel details
- Verify the hotel ID formats are correct
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving hotel details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
