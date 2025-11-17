"""
HotelOfferDetailsRQ - Get Hotel Offer Details Tool

This tool retrieves detailed information about hotel offers including
discounts, supplements, promotional codes, and special campaigns.
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
HOTEL_OFFER_DETAILS_RQ_TOOL = Tool(
    name="hotel_offer_details_rq",
    description="""
    Retrieve comprehensive information about hotel offers, promotions, and special deals.
    
    This tool provides detailed offer information including:
    - Offer descriptions and names
    - Discount types and values (percentage, fixed amount, free nights)
    - Promotional codes and activation conditions
    - Offer visibility settings and restrictions
    - Valid date ranges and activation periods
    - Media assets and promotional materials
    - Target markets and device restrictions
    
    Parameters:
    - hotel_ids (optional): List of hotel identifiers to get offers for
    - offer_ids (optional): List of specific offer identifiers
    - filters (optional): Additional filtering options
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Comprehensive offer details and configurations
    - Promotional terms and conditions
    - Activation requirements and restrictions
    - Marketing materials and media
    
    Example usage:
    "Get all active offers for hotel 'HTL123'"
    "Show details for offer 'OFF456' in hotel 'HTL123'"
    "List promotional campaigns for hotels 'HTL123' and 'HTL456'"
    "Get offers with promotional codes for hotel 'HTL789'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to get offers for (optional)",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 50
            },
            "offer_ids": {
                "type": "array",
                "description": "List of specific offer identifiers to retrieve (optional)",
                "items": {
                    "type": "string",
                    "description": "Offer identifier"
                },
                "maxItems": 100
            },
            "filters": {
                "type": "object",
                "description": "Additional filtering options",
                "properties": {
                    "promo_codes": {
                        "type": "array",
                        "description": "Filter by promotional codes",
                        "items": {
                            "type": "string"
                        }
                    },
                    "exclude_offer_types": {
                        "type": "array",
                        "description": "Exclude specific offer types",
                        "items": {
                            "type": "string",
                            "enum": ["promocode", "callout", "notice", "supplement", "discount"]
                        }
                    },
                    "client_location": {
                        "type": "object",
                        "description": "Client location filtering",
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
                        "enum": ["desktop", "mobile", "tablet"]
                    }
                }
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


class HotelOfferDetailsRQHandler:
    """Handler for the HotelOfferDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_offer_details_rq")
    
    def _format_offer_activation(self, activation: Dict[str, Any]) -> Dict[str, Any]:
        """Format offer activation information for readable output."""
        if not activation:
            return {}
            
        formatted = {
            "from_date": activation.get("From"),
            "to_date": activation.get("To"),
            "admins_only": activation.get("Admins", False)
        }
        
        # Format limit information
        limit = activation.get("Limit", {})
        if limit:
            formatted["limit"] = {
                "limit_value": limit.get("Limit"),
                "limit_type": limit.get("LimitType")
            }
        
        return formatted
    
    def _format_offer_visibility(self, visibility: Dict[str, Any]) -> Dict[str, Any]:
        """Format offer visibility information for readable output."""
        if not visibility:
            return {}
            
        formatted = {
            "status": visibility.get("Status"),
            "date_published": visibility.get("DatePublished"),
            "time_published_from": visibility.get("TimePublishedFrom"),
            "time_published_to": visibility.get("TimePublishedTo")
        }
        
        # Format visible countries
        countries = visibility.get("Countries", [])
        if countries:
            formatted["visible_countries"] = countries
        
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
    
    def _format_offer_detail(self, offer_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format complete offer detail information for readable output."""
        formatted = {
            "offer_id": offer_detail.get("HotelOfferId"),
            "offer_name": offer_detail.get("HotelOfferName"),
            "offer_description": offer_detail.get("HotelOfferDescription"),
            "creation_date": offer_detail.get("CreationDate"),
            "order": offer_detail.get("Order", 0),
            "offer_type": offer_detail.get("Type"),
            "discount_type": offer_detail.get("TypeDiscount"),
            "value": offer_detail.get("Value"),
            "hidden": offer_detail.get("Hidden", False),
            "hidden_not_applied": offer_detail.get("HiddenNotApplied", False),
            "rewards": offer_detail.get("Rewards", False)
        }
        
        # Format chain and hotel IDs
        chain_id = offer_detail.get("ChainId")
        if chain_id:
            formatted["chain_id"] = chain_id
        
        hotel_ids = offer_detail.get("HotelId", [])
        if hotel_ids:
            formatted["hotel_ids"] = hotel_ids
        
        # Format promotional codes
        promo_code = offer_detail.get("PromoCode")
        if promo_code:
            formatted["promo_code"] = promo_code
        
        promo_codes = offer_detail.get("PromoCodes", [])
        if promo_codes:
            formatted["promo_codes"] = promo_codes
        
        # Format activation details
        activation = offer_detail.get("OfferActivation", {})
        if activation:
            formatted["activation"] = self._format_offer_activation(activation)
        
        # Format visibility details
        visibility = offer_detail.get("OfferVisibility", {})
        if visibility:
            formatted["visibility"] = self._format_offer_visibility(visibility)
        
        # Format media
        media = offer_detail.get("Media", [])
        if media:
            formatted["media"] = self._format_media(media)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel offer details request.
        
        Args:
            arguments: Tool arguments containing hotel/offer IDs and filters
            
        Returns:
            Dictionary containing the hotel offer details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids")
            offer_ids = arguments.get("offer_ids")
            filters = arguments.get("filters", {})
            language = arguments.get("language", "es")
            
            # Validate and sanitize hotel IDs if provided
            sanitized_hotel_ids = None
            if hotel_ids:
                if not isinstance(hotel_ids, list):
                    raise ValidationError("hotel_ids must be a list")
                
                sanitized_hotel_ids = []
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            # Validate and sanitize offer IDs if provided
            sanitized_offer_ids = None
            if offer_ids:
                if not isinstance(offer_ids, list):
                    raise ValidationError("offer_ids must be a list")
                
                sanitized_offer_ids = []
                for offer_id in offer_ids:
                    if not isinstance(offer_id, str) or not offer_id.strip():
                        raise ValidationError(f"Invalid offer ID: {offer_id}")
                    sanitized_offer_ids.append(sanitize_string(offer_id.strip()))
            
            self.logger.info(
                "Retrieving hotel offer details",
                hotel_count=len(sanitized_hotel_ids) if sanitized_hotel_ids else "all",
                offer_count=len(sanitized_offer_ids) if sanitized_offer_ids else "all",
                language=language,
                has_filters=bool(filters)
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            
            if sanitized_offer_ids:
                request_payload["OfferId"] = sanitized_offer_ids
            
            # Add filters if provided
            if filters:
                filter_by = {}
                
                # Add promotional code filters
                promo_codes = filters.get("promo_codes")
                if promo_codes and isinstance(promo_codes, list):
                    sanitized_promo_codes = []
                    for code in promo_codes:
                        if isinstance(code, str) and code.strip():
                            sanitized_promo_codes.append(sanitize_string(code.strip()))
                    if sanitized_promo_codes:
                        filter_by["PromoCode"] = sanitized_promo_codes
                
                # Add offer type exclusions
                exclude_types = filters.get("exclude_offer_types")
                if exclude_types and isinstance(exclude_types, list):
                    valid_types = ["promocode", "callout", "notice", "supplement", "discount"]
                    sanitized_exclude_types = []
                    for offer_type in exclude_types:
                        if offer_type in valid_types:
                            sanitized_exclude_types.append(offer_type)
                    if sanitized_exclude_types:
                        filter_by["ExcludeOfferType"] = sanitized_exclude_types
                
                # Add client location filters
                client_location = filters.get("client_location")
                if client_location and isinstance(client_location, dict):
                    location_obj = {}
                    if "country" in client_location and client_location["country"]:
                        location_obj["Country"] = sanitize_string(client_location["country"])
                    if "ip" in client_location and client_location["ip"]:
                        location_obj["Ip"] = sanitize_string(client_location["ip"])
                    if location_obj:
                        filter_by["ClientLocation"] = location_obj
                
                # Add client device filter
                client_device = filters.get("client_device")
                if client_device and client_device in ["desktop", "mobile", "tablet"]:
                    filter_by["ClientDevice"] = client_device
                
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
                
                # Make the hotel offer details request
                response = await client.post("/HotelOfferDetailsRQ", request_payload)
            
            # Extract offer details from response
            offer_details_raw = response.get("HotelOfferDetail", [])
            
            # Format offer details
            formatted_offers = []
            for offer_detail in offer_details_raw:
                formatted_offers.append(self._format_offer_detail(offer_detail))
            
            # Log successful operation
            self.logger.info(
                "Hotel offer details retrieved successfully",
                offer_count=len(formatted_offers),
                found_offers=len(offer_details_raw),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "offer_details": formatted_offers,
                "requested_hotel_ids": sanitized_hotel_ids,
                "requested_offer_ids": sanitized_offer_ids,
                "filters_applied": filters,
                "found_count": len(formatted_offers),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "offers_found": len(formatted_offers),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {len(formatted_offers)} offer(s)"
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
handler = HotelOfferDetailsRQHandler()


async def call_hotel_offer_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelOfferDetailsRQ endpoint.
    
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
            
            response_text = f"""🎯 **Hotel Offers Details**

✅ **Summary:**
- **Offers Found**: {summary['offers_found']}
- **Language**: {summary['language'].upper()}

"""
            
            # Display details for each offer
            for i, offer in enumerate(data["offer_details"], 1):
                response_text += f"""
{'='*70}
🎯 **Offer #{i}: {offer.get('offer_name', 'Unnamed Offer')}**
{'='*70}

🏷️ **Basic Information:**
- **Offer ID**: {offer.get('offer_id', 'N/A')}
- **Name**: {offer.get('offer_name', 'N/A')}
- **Description**: {offer.get('offer_description', 'N/A')[:200]}{'...' if len(offer.get('offer_description', '')) > 200 else ''}
- **Creation Date**: {offer.get('creation_date', 'N/A')}
- **Order**: {offer.get('order', 'N/A')}
"""
                
                # Show offer type and discount information
                response_text += f"""
💰 **Offer Configuration:**
- **Type**: {offer.get('offer_type', 'N/A').title()}
- **Discount Type**: {offer.get('discount_type', 'N/A').replace('_', ' ').title()}
"""
                
                if offer.get('value') is not None:
                    response_text += f"- **Value**: {offer['value']}\n"
                
                # Show visibility and status
                response_text += f"""
🔍 **Status & Visibility:**
- **Hidden**: {'Yes' if offer.get('hidden') else 'No'}
- **Hidden When Not Applied**: {'Yes' if offer.get('hidden_not_applied') else 'No'}
- **Rewards Program**: {'Yes' if offer.get('rewards') else 'No'}
"""
                
                # Show chain and hotel information
                if offer.get('chain_id'):
                    response_text += f"- **Chain ID**: {offer['chain_id']}\n"
                
                hotel_ids = offer.get('hotel_ids', [])
                if hotel_ids:
                    response_text += f"- **Applicable Hotels**: {', '.join(hotel_ids[:5])}"
                    if len(hotel_ids) > 5:
                        response_text += f" (and {len(hotel_ids) - 5} more)"
                    response_text += "\n"
                
                # Show promotional codes
                promo_code = offer.get('promo_code')
                promo_codes = offer.get('promo_codes', [])
                
                if promo_code or promo_codes:
                    response_text += f"""
🎫 **Promotional Codes:**
"""
                    if promo_code:
                        response_text += f"- **Primary Code**: {promo_code}\n"
                    if promo_codes:
                        response_text += f"- **Available Codes**: {', '.join(promo_codes[:10])}"
                        if len(promo_codes) > 10:
                            response_text += f" (and {len(promo_codes) - 10} more)"
                        response_text += "\n"
                
                # Show activation details
                activation = offer.get('activation', {})
                if activation and any(activation.values()):
                    response_text += f"""
📅 **Activation Details:**
"""
                    if activation.get('from_date'):
                        response_text += f"- **Active From**: {activation['from_date']}\n"
                    if activation.get('to_date'):
                        response_text += f"- **Active Until**: {activation['to_date']}\n"
                    if activation.get('admins_only'):
                        response_text += f"- **Admin Only**: Yes\n"
                    
                    limit = activation.get('limit', {})
                    if limit and any(limit.values()):
                        response_text += f"- **Usage Limit**: {limit.get('limit_value', 'N/A')} ({limit.get('limit_type', 'N/A')})\n"
                
                # Show visibility details
                visibility = offer.get('visibility', {})
                if visibility and any(visibility.values()):
                    response_text += f"""
👁️ **Visibility Settings:**
"""
                    if visibility.get('status'):
                        response_text += f"- **Status**: {visibility['status']}\n"
                    if visibility.get('date_published'):
                        response_text += f"- **Published Date**: {visibility['date_published']}\n"
                    if visibility.get('time_published_from') or visibility.get('time_published_to'):
                        response_text += f"- **Published Hours**: {visibility.get('time_published_from', 'N/A')} - {visibility.get('time_published_to', 'N/A')}\n"
                    
                    countries = visibility.get('visible_countries', [])
                    if countries:
                        response_text += f"- **Visible Countries**: {', '.join(countries[:10])}"
                        if len(countries) > 10:
                            response_text += f" (and {len(countries) - 10} more)"
                        response_text += "\n"
                
                # Show media
                media = offer.get('media', [])
                if media:
                    response_text += f"""
📸 **Media Gallery**: {len(media)} item(s)
"""
                    for media_item in media[:3]:  # Show first 3 media items
                        response_text += f"- {media_item['type'].title()}: {media_item.get('caption', 'No caption')}"
                        if media_item.get('is_main'):
                            response_text += " 🌟 (Main)"
                        response_text += "\n"
                    if len(media) > 3:
                        response_text += f"... and {len(media) - 3} more media items\n"
            
            # Show filters applied if any
            filters_applied = data.get("filters_applied", {})
            if filters_applied:
                response_text += f"""

🔍 **Filters Applied:**
"""
                if filters_applied.get('promo_codes'):
                    response_text += f"- **Promotional Codes**: {', '.join(filters_applied['promo_codes'])}\n"
                if filters_applied.get('exclude_offer_types'):
                    response_text += f"- **Excluded Types**: {', '.join(filters_applied['exclude_offer_types'])}\n"
                if filters_applied.get('client_location'):
                    location = filters_applied['client_location']
                    response_text += f"- **Client Location**: {location.get('country', 'N/A')} (IP: {location.get('ip', 'N/A')})\n"
                if filters_applied.get('client_device'):
                    response_text += f"- **Client Device**: {filters_applied['client_device'].title()}\n"
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Hotel Offer Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel and offer IDs exist and are accessible
- Check your authentication credentials
- Ensure you have permission to view offer details
- Verify the filter parameters are correctly formatted
- Check promotional codes are valid
- Ensure client location and device filters are supported
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving hotel offer details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
