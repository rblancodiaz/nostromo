"""
HotelRoomExtraAvailRQ - Hotel Room Extra Availability Tool

This tool retrieves availability information for hotel room extras/supplements
based on specific room availability IDs or basket context.
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
HOTEL_ROOM_EXTRA_AVAIL_RQ_TOOL = Tool(
    name="hotel_room_extra_avail_rq",
    description="""
    Retrieve availability information for hotel room extras and supplements.
    
    This tool provides information about additional services and supplements available for hotel rooms including:
    - Extra service availability and pricing
    - Supplement details and restrictions
    - Billing types and calculation methods
    - Release times and minimum stay requirements
    - Included vs. paid extras
    - Visibility rules
    
    Parameters:
    - room_availability_ids (required): List of room availability IDs to get extras for
    - basket_id (optional): Basket ID for context
    - language (optional): Language code for the request
    - origin (optional): Origin of the request
    - client_location (optional): Client location information
    - client_device (optional): Client device type
    
    Returns:
    - Available room extras with pricing
    - Extra service details and restrictions
    - Billing and calculation information
    - Availability dates and quantities
    - Release and minimum stay requirements
    - Not available extras with reasons
    
    Example usage:
    "Get available extras for room availability ID 'AVAIL123'"
    "Show me supplements for room availabilities 'AVAIL456' and 'AVAIL789'"
    "Check what extras are available for my selected rooms"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "room_availability_ids": {
                "type": "array",
                "description": "List of room availability IDs to get extras for",
                "items": {
                    "type": "string",
                    "description": "Room availability identifier"
                },
                "minItems": 1,
                "maxItems": 50
            },
            "basket_id": {
                "type": "string",
                "description": "Basket ID for context"
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            },
            "origin": {
                "type": "string",
                "description": "Origin of the request"
            },
            "client_location": {
                "type": "object",
                "description": "Client location information",
                "properties": {
                    "country": {
                        "type": "string",
                        "description": "Client country code"
                    },
                    "ip": {
                        "type": "string",
                        "description": "Client IP address"
                    }
                }
            },
            "client_device": {
                "type": "string",
                "description": "Client device type",
                "enum": ["desktop", "mobile", "tablet"],
                "default": "desktop"
            }
        },
        "required": ["room_availability_ids"],
        "additionalProperties": False
    }
)


class HotelRoomExtraAvailRQHandler:
    """Handler for the HotelRoomExtraAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_room_extra_avail_rq")
    
    def _format_extra_amounts(self, amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Format extra amounts information for readable output."""
        if not amounts:
            return {}
            
        return {
            "amount_type": amounts.get("ExtraAmountType"),
            "currency": amounts.get("Currency"),
            "final_amount": amounts.get("AmountFinal"),
            "base_amount": amounts.get("AmountBase"),
            "taxes": amounts.get("AmountTaxes"),
            "before_amount": amounts.get("AmountBefore"),
            "before_inventory": amounts.get("AmountBeforeInventory"),
            "before_max": amounts.get("AmountBeforeMax"),
            "offers": amounts.get("AmountOffers"),
            "discounts": amounts.get("AmountDiscounts")
        }
    
    def _format_room_extra_avail(self, extra_avail: Dict[str, Any]) -> Dict[str, Any]:
        """Format room extra availability information for readable output."""
        formatted = {
            "extra_availability_id": extra_avail.get("HotelRoomExtraAvailabilityId"),
            "room_availability_id": extra_avail.get("HotelRoomAvailabilityId"),
            "extra_id": extra_avail.get("HotelRoomExtraId"),
            "included": extra_avail.get("Included", False),
            "release": extra_avail.get("Release"),
            "min_stay": extra_avail.get("MinStay"),
            "availability": extra_avail.get("Availability"),
            "date_for_extra": extra_avail.get("DateForExtra"),
            "amount_extra": extra_avail.get("AmountExtra"),
            "visibility": extra_avail.get("Visibility")
        }
        
        # Format amounts
        amounts = extra_avail.get("HotelRoomExtraAmounts", {})
        if amounts:
            formatted["amounts"] = self._format_extra_amounts(amounts)
        
        return formatted
    
    def _format_room_extra_not_avail(self, extra_not_avail: Dict[str, Any]) -> Dict[str, Any]:
        """Format room extra not available information for readable output."""
        formatted = {
            "room_availability_id": extra_not_avail.get("HotelRoomAvailabilityId"),
            "extra_id": extra_not_avail.get("HotelRoomExtraId"),
            "amount_type": extra_not_avail.get("ExtraAmountType"),
            "release": extra_not_avail.get("Release"),
            "min_stay": extra_not_avail.get("MinStay"),
            "visibility": extra_not_avail.get("Visibility")
        }
        
        # Format cause
        cause = extra_not_avail.get("Cause", {})
        if cause:
            formatted["cause"] = {
                "code": cause.get("Code"),
                "description": cause.get("Description"),
                "target": cause.get("Target")
            }
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel room extra availability request.
        
        Args:
            arguments: Tool arguments containing room availability IDs
            
        Returns:
            Dictionary containing the room extra availability results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            room_availability_ids = arguments.get("room_availability_ids", [])
            basket_id = arguments.get("basket_id")
            language = arguments.get("language", "es")
            origin = arguments.get("origin")
            client_location = arguments.get("client_location", {})
            client_device = arguments.get("client_device", "desktop")
            
            # Validate required fields
            if not room_availability_ids:
                raise ValidationError("At least one room availability ID is required")
            
            if not isinstance(room_availability_ids, list):
                raise ValidationError("room_availability_ids must be a list")
            
            # Sanitize availability IDs
            sanitized_availability_ids = []
            for availability_id in room_availability_ids:
                if not isinstance(availability_id, str) or not availability_id.strip():
                    raise ValidationError(f"Invalid room availability ID: {availability_id}")
                sanitized_availability_ids.append(sanitize_string(availability_id.strip()))
            
            self.logger.info(
                "Retrieving room extra availability",
                availability_count=len(sanitized_availability_ids),
                basket_id=basket_id,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload["HotelRoomAvailabilityId"] = sanitized_availability_ids
            
            # Add optional parameters
            if basket_id:
                request_payload["BasketId"] = sanitize_string(basket_id)
            if origin:
                request_payload["Origin"] = sanitize_string(origin)
            if client_device:
                request_payload["ClientDevice"] = client_device
            
            # Add client location if provided
            if client_location:
                formatted_location = {}
                if client_location.get("country"):
                    formatted_location["Country"] = client_location["country"]
                if client_location.get("ip"):
                    formatted_location["Ip"] = client_location["ip"]
                if formatted_location:
                    request_payload["ClientLocation"] = formatted_location
            
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
                
                # Make the room extra availability request
                response = await client.post("/HotelRoomExtraAvailRQ", request_payload)
            
            # Extract extra availability data from response
            available_extras = []
            extras_avail_raw = response.get("HotelRoomExtraAvail", [])
            for extra_avail in extras_avail_raw:
                available_extras.append(self._format_room_extra_avail(extra_avail))
            
            # Extract not available extras
            not_available_extras = []
            extras_not_avail_raw = response.get("HotelRoomExtraNotAvail", [])
            for extra_not_avail in extras_not_avail_raw:
                not_available_extras.append(self._format_room_extra_not_avail(extra_not_avail))
            
            # Log successful operation
            self.logger.info(
                "Room extra availability retrieved successfully",
                available_count=len(available_extras),
                not_available_count=len(not_available_extras),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "room_availability_ids": sanitized_availability_ids,
                    "basket_id": basket_id,
                    "origin": origin,
                    "client_device": client_device,
                    "client_location": client_location
                },
                "available_extras": available_extras,
                "not_available_extras": not_available_extras,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_available": len(available_extras),
                    "total_not_available": len(not_available_extras),
                    "requested_rooms": len(sanitized_availability_ids),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(available_extras)} available extra(s) for {len(sanitized_availability_ids)} room(s)"
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
handler = HotelRoomExtraAvailRQHandler()


async def call_hotel_room_extra_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelRoomExtraAvailRQ endpoint.
    
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
            search_criteria = data["search_criteria"]
            
            response_text = f"""🎯 **Hotel Room Extra Availability Results**

✅ **Search Summary:**
- **Room Availabilities**: {summary['requested_rooms']}
- **Available Extras**: {summary['total_available']}
- **Not Available**: {summary['total_not_available']}
- **Language**: {summary['language'].upper()}

🔍 **Search Context:**
- **Basket ID**: {search_criteria.get('basket_id', 'N/A')}
- **Origin**: {search_criteria.get('origin', 'N/A')}
- **Client Device**: {search_criteria.get('client_device', 'N/A')}
"""
            
            # Display client location if provided
            client_location = search_criteria.get('client_location', {})
            if client_location:
                response_text += f"""- **Client Location**: {client_location.get('country', 'N/A')} ({client_location.get('ip', 'N/A')})
"""
            
            # Display available extras
            if data["available_extras"]:
                response_text += f"""
{'='*70}
🎁 **AVAILABLE EXTRAS** ({len(data["available_extras"])})
{'='*70}
"""
                
                # Group extras by room availability ID
                extras_by_room = {}
                for extra in data["available_extras"]:
                    room_id = extra.get("room_availability_id", "Unknown")
                    if room_id not in extras_by_room:
                        extras_by_room[room_id] = []
                    extras_by_room[room_id].append(extra)
                
                for room_id, extras in extras_by_room.items():
                    response_text += f"""
🏠 **Room Availability: {room_id}** ({len(extras)} extras)
"""
                    
                    for i, extra in enumerate(extras, 1):
                        amounts = extra.get("amounts", {})
                        final_amount = amounts.get("final_amount", 0)
                        currency = amounts.get("currency", "EUR")
                        amount_type = amounts.get("amount_type", "N/A")
                        
                        response_text += f"""
  🎯 **Extra #{i}**
  - **Extra ID**: {extra.get('extra_id', 'N/A')}
  - **Availability ID**: {extra.get('extra_availability_id', 'N/A')}
  - **Included**: {'Yes' if extra.get('included') else 'No'}
  - **💰 Price**: {final_amount:.2f} {currency} ({amount_type})
  - **Availability**: {extra.get('availability', 'N/A')} units
  - **Release**: {extra.get('release', 'N/A')} days
  - **Min Stay**: {extra.get('min_stay', 'N/A')} nights
  - **Visibility**: {extra.get('visibility', 'N/A')}
"""
                        
                        # Show price breakdown if available
                        if amounts:
                            base_amount = amounts.get("base_amount")
                            taxes = amounts.get("taxes")
                            offers = amounts.get("offers")
                            discounts = amounts.get("discounts")
                            
                            if any([base_amount, taxes, offers, discounts]):
                                response_text += f"  **Price Breakdown**:\n"
                                if base_amount and base_amount != final_amount:
                                    response_text += f"  - Base: {base_amount:.2f} {currency}\n"
                                if taxes:
                                    response_text += f"  - Taxes: {taxes:.2f} {currency}\n"
                                if offers:
                                    response_text += f"  - Offers: -{offers:.2f} {currency}\n"
                                if discounts:
                                    response_text += f"  - Discounts: -{discounts:.2f} {currency}\n"
                        
                        # Show date and amount info
                        date_for_extra = extra.get("date_for_extra")
                        amount_extra = extra.get("amount_extra")
                        if date_for_extra or amount_extra:
                            response_text += f"  **Additional Info**:\n"
                            if date_for_extra:
                                response_text += f"  - Date: {date_for_extra}\n"
                            if amount_extra:
                                response_text += f"  - Amount: {amount_extra}\n"
                        
                        response_text += "\n"
            
            # Display not available extras
            if data["not_available_extras"]:
                response_text += f"""
{'='*70}
❌ **NOT AVAILABLE EXTRAS** ({len(data["not_available_extras"])})
{'='*70}
"""
                
                # Group not available extras by room availability ID
                not_avail_by_room = {}
                for extra in data["not_available_extras"]:
                    room_id = extra.get("room_availability_id", "Unknown")
                    if room_id not in not_avail_by_room:
                        not_avail_by_room[room_id] = []
                    not_avail_by_room[room_id].append(extra)
                
                for room_id, extras in not_avail_by_room.items():
                    response_text += f"""
🏠 **Room Availability: {room_id}** ({len(extras)} not available)
"""
                    
                    for i, extra in enumerate(extras, 1):
                        cause = extra.get("cause", {})
                        
                        response_text += f"""
  ❌ **Extra #{i}**
  - **Extra ID**: {extra.get('extra_id', 'N/A')}
  - **Amount Type**: {extra.get('amount_type', 'N/A')}
  - **Release**: {extra.get('release', 'N/A')} days
  - **Min Stay**: {extra.get('min_stay', 'N/A')} nights
  - **Visibility**: {extra.get('visibility', 'N/A')}
"""
                        
                        if cause:
                            response_text += f"""  **Reason Not Available**:
  - **Code**: {cause.get('code', 'N/A')}
  - **Description**: {cause.get('description', 'N/A')}
  - **Target**: {cause.get('target', 'N/A')}
"""
                        
                        response_text += "\n"
                
                # Summary of reasons
                response_text += f"""
**Common reasons for unavailability:**
"""
                
                # Count causes
                causes = {}
                for extra in data["not_available_extras"]:
                    cause = extra.get("cause", {})
                    cause_desc = cause.get("description", "Unknown reason")
                    causes[cause_desc] = causes.get(cause_desc, 0) + 1
                
                for cause, count in list(causes.items())[:5]:
                    response_text += f"- **{cause}**: {count} extra(s)\n"
            
            # Display room availability IDs processed
            response_text += f"""
{'='*70}
📋 **PROCESSED ROOM AVAILABILITIES**
{'='*70}
"""
            
            for i, room_id in enumerate(search_criteria["room_availability_ids"], 1):
                # Count extras for this room
                available_count = len([e for e in data["available_extras"] if e.get("room_availability_id") == room_id])
                not_available_count = len([e for e in data["not_available_extras"] if e.get("room_availability_id") == room_id])
                
                response_text += f"""
🏠 **Room #{i}: {room_id}**
- **Available Extras**: {available_count}
- **Not Available**: {not_available_count}
- **Total Extras**: {available_count + not_available_count}
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Next Steps:**
- Use extra availability IDs to add extras to your basket
- Check included vs. paid extras
- Review release times and minimum stay requirements
- Consider visibility rules for your booking context
- Contact hotel for custom extra requests
"""
        else:
            response_text = f"""❌ **Room Extra Availability Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the room availability IDs are valid and active
- Check your authentication credentials
- Ensure the rooms still have availability
- Verify the basket ID if provided
- Try requesting fewer room availabilities at once
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving room extra availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
