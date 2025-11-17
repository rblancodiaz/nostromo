"""
BasketSummaryRQ - Get Basket Summary Tool

This tool retrieves a detailed summary of a shopping basket including all products,
pricing, and breakdown information from the Neobookings system.
"""

import json
from typing import Dict, Any
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
BASKET_SUMMARY_RQ_TOOL = Tool(
    name="basket_summary_rq",
    description="""
    Retrieve a detailed summary of a shopping basket from the Neobookings system.
    
    This tool provides comprehensive information about a basket including:
    - All products and services in the basket
    - Detailed pricing breakdown
    - Guest information
    - Board and rate details
    - Offers and extras applied
    - Cancellation policies
    - Payment schedules
    
    Parameters:
    - basket_id (required): Identifier of the basket to summarize
    - call_center_properties (optional): Call center specific properties
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Complete basket summary with all details
    - Pricing breakdown and totals
    - Product and service information
    - Policies and terms
    
    Example usage:
    "Show me the summary of basket 'BASKET123'"
    "Get detailed breakdown of my basket"
    "View basket contents and pricing"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "basket_id": {
                "type": "string",
                "description": "Identifier of the basket to summarize",
                "minLength": 1
            },
            "call_center_properties": {
                "type": "object",
                "description": "Call center specific properties",
                "properties": {
                    "ignore_release": {"type": "boolean"},
                    "ignore_min_stay": {"type": "boolean"},
                    "ignore_availability": {"type": "boolean"},
                    "override_price": {"type": "number"},
                    "override_deposit": {"type": "number"},
                    "override_discount": {"type": "number"},
                    "ignore_required_extra": {"type": "boolean"},
                    "ignore_required_fields": {"type": "boolean"},
                    "override_country": {"type": "string"},
                    "override_inbound_method": {
                        "type": "string",
                        "enum": ["inbound", "outbound", "email", "whatsapp", "walkin"]
                    }
                },
                "additionalProperties": False
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["basket_id"],
        "additionalProperties": False
    }
)


class BasketSummaryRQHandler:
    """Handler for the BasketSummaryRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_summary_rq")
    
    def _format_amount(self, amount: float, currency: str = "EUR") -> str:
        """Format amount with currency."""
        return f"{amount:.2f} {currency}"
    
    def _extract_room_summary(self, room_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format room summary information."""
        basic_detail = room_summary.get("HotelRoomBasicDetail", {})
        amounts = room_summary.get("AmountsDetail", {})
        
        return {
            "availability_id": room_summary.get("HotelRoomAvailabilityId"),
            "arrival_date": room_summary.get("ArrivalDate"),
            "departure_date": room_summary.get("DepartureDate"),
            "hotel_name": basic_detail.get("HotelName"),
            "room_name": basic_detail.get("HotelRoomName"),
            "room_description": basic_detail.get("HotelRoomDescription"),
            "amounts": amounts
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the basket summary request.
        
        Args:
            arguments: Tool arguments containing basket ID
            
        Returns:
            Dictionary containing the complete basket summary
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            basket_id = sanitize_string(arguments["basket_id"])
            language = arguments.get("language", "es")
            
            self.logger.info(
                "Retrieving basket summary",
                basket_id=basket_id,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                **request_data,
                "BasketId": basket_id
            }
            
            # Add optional call center properties
            if arguments.get("call_center_properties"):
                cc_props = arguments["call_center_properties"]
                formatted_props = {}
                
                field_mapping = {
                    "ignore_release": "IgnoreRelease",
                    "ignore_min_stay": "IgnoreMinStay", 
                    "ignore_availability": "IgnoreAvailability",
                    "override_price": "OverridePrice",
                    "override_deposit": "OverrideDeposit",
                    "override_discount": "OverrideDiscount",
                    "ignore_required_extra": "IgnoreRequiredExtra",
                    "ignore_required_fields": "IgnoreRequiredFields",
                    "override_country": "OverrideCountry",
                    "override_inbound_method": "OverrideInboundMethod"
                }
                
                for key, value in cc_props.items():
                    if key in field_mapping and value is not None:
                        formatted_props[field_mapping[key]] = value
                        
                if formatted_props:
                    request_payload["CallCenterProperties"] = formatted_props
            
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
                
                # Make the basket summary request
                response = await client.post("/BasketSummaryRQ", request_payload)
            
            # Extract summary details from response
            basket_detail = response.get("BasketDetail", {})
            amounts_detail = response.get("AmountsDetail", {})
            hotel_room_summaries = response.get("HotelRoomSummaryDetail", [])
            hotel_guest_summaries = response.get("HotelGuestSummaryDetail", [])
            hotel_board_summaries = response.get("HotelBoardSummaryDetail", [])
            hotel_rate_summaries = response.get("HotelRateSummaryDetail", [])
            hotel_offer_summaries = response.get("HotelOfferSummaryDetail", [])
            hotel_extra_summaries = response.get("HotelExtraSummaryDetail", [])
            booking_cancel_penalties = response.get("BookingCancelPenalty", [])
            scheduled_payments = response.get("ScheduledPayment", [])
            package_summaries = response.get("PackageSummaryDetail", [])
            generic_product_summaries = response.get("GenericProductSummaryDetail", [])
            
            # Process room summaries
            rooms_info = []
            for room in hotel_room_summaries:
                rooms_info.append(self._extract_room_summary(room))
            
            # Log successful operation
            self.logger.info(
                "Basket summary retrieved successfully",
                basket_id=basket_id,
                basket_status=basket_detail.get("BasketStatus"),
                total_amount=amounts_detail.get("AmountFinal"),
                rooms_count=len(hotel_room_summaries),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "basket_id": basket_id,
                "basket_detail": basket_detail,
                "amounts_detail": amounts_detail,
                "rooms_summary": rooms_info,
                "guests_count": len(hotel_guest_summaries),
                "boards_count": len(hotel_board_summaries),
                "rates_count": len(hotel_rate_summaries),
                "offers_count": len(hotel_offer_summaries),
                "extras_count": len(hotel_extra_summaries),
                "packages_count": len(package_summaries),
                "generic_products_count": len(generic_product_summaries),
                "cancel_penalties_count": len(booking_cancel_penalties),
                "scheduled_payments_count": len(scheduled_payments),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "raw_response": {
                    "hotel_guest_summaries": hotel_guest_summaries,
                    "hotel_board_summaries": hotel_board_summaries,
                    "hotel_rate_summaries": hotel_rate_summaries,
                    "hotel_offer_summaries": hotel_offer_summaries,
                    "hotel_extra_summaries": hotel_extra_summaries,
                    "booking_cancel_penalties": booking_cancel_penalties,
                    "scheduled_payments": scheduled_payments,
                    "package_summaries": package_summaries,
                    "generic_product_summaries": generic_product_summaries
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message="Basket summary retrieved successfully"
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
handler = BasketSummaryRQHandler()


async def call_basket_summary_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketSummaryRQ endpoint.
    
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
            basket_detail = data["basket_detail"]
            amounts_detail = data["amounts_detail"]
            rooms_summary = data["rooms_summary"]
            
            currency = amounts_detail.get("Currency", "EUR")
            
            response_text = f"""📋 **Basket Summary**

✅ **Basket Information:**
- **Basket ID**: {data['basket_id']}
- **Status**: {basket_detail.get('BasketStatus', 'Unknown')}
- **Budget ID**: {basket_detail.get('BudgetId', 'Not assigned')}
- **Order ID**: {basket_detail.get('OrderId', 'Not assigned')}

💰 **Pricing Summary:**
- **Final Amount**: {amounts_detail.get('AmountFinal', 0):.2f} {currency}
- **Total Amount**: {amounts_detail.get('AmountTotal', 0):.2f} {currency}
- **Base Amount**: {amounts_detail.get('AmountBase', 0):.2f} {currency}
- **Taxes**: {amounts_detail.get('AmountTaxes', 0):.2f} {currency}
- **Tourist Tax**: {amounts_detail.get('AmountTouristTax', 0):.2f} {currency}
"""
            
            # Add discount and offer information if available
            if amounts_detail.get('AmountOffers', 0) > 0:
                response_text += f"- **Offers Discount**: -{amounts_detail.get('AmountOffers', 0):.2f} {currency}\n"
            if amounts_detail.get('AmountDiscounts', 0) > 0:
                response_text += f"- **Additional Discounts**: -{amounts_detail.get('AmountDiscounts', 0):.2f} {currency}\n"
            if amounts_detail.get('AmountExtras', 0) > 0:
                response_text += f"- **Extras**: {amounts_detail.get('AmountExtras', 0):.2f} {currency}\n"
            
            # Add room information
            response_text += f"\n🏨 **Rooms Summary** ({len(rooms_summary)} rooms):\n"
            for i, room in enumerate(rooms_summary, 1):
                response_text += f"\n**Room {i}:**\n"
                response_text += f"- **Hotel**: {room.get('hotel_name', 'N/A')}\n"
                response_text += f"- **Room**: {room.get('room_name', 'N/A')}\n"
                response_text += f"- **Check-in**: {room.get('arrival_date', 'N/A')}\n"
                response_text += f"- **Check-out**: {room.get('departure_date', 'N/A')}\n"
                
                room_amounts = room.get('amounts', {})
                if room_amounts.get('AmountFinal'):
                    response_text += f"- **Room Price**: {room_amounts.get('AmountFinal', 0):.2f} {room_amounts.get('Currency', currency)}\n"
            
            # Add component counts
            response_text += f"\n📦 **Content Summary:**\n"
            response_text += f"- **Guests**: {data['guests_count']}\n"
            response_text += f"- **Board Types**: {data['boards_count']}\n"
            response_text += f"- **Rate Types**: {data['rates_count']}\n"
            response_text += f"- **Offers Applied**: {data['offers_count']}\n"
            response_text += f"- **Extras**: {data['extras_count']}\n"
            response_text += f"- **Packages**: {data['packages_count']}\n"
            response_text += f"- **Generic Products**: {data['generic_products_count']}\n"
            
            # Add policy information
            if data['cancel_penalties_count'] > 0:
                response_text += f"- **Cancellation Policies**: {data['cancel_penalties_count']} terms\n"
            if data['scheduled_payments_count'] > 0:
                response_text += f"- **Payment Schedule**: {data['scheduled_payments_count']} payments\n"
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **Next Steps:**
- Review all details carefully
- Use `basket_lock_rq` to lock basket before confirmation
- Use `basket_confirm_rq` to complete the reservation
- Use `basket_add_product_rq` or `basket_del_product_rq` to modify contents

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Basket Summary**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the basket ID exists and is accessible
- Check your authentication credentials
- Ensure the basket has not been deleted
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving the basket summary:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
