"""
HotelRateDetailsRQ - Get Hotel Rate Details Tool

This tool retrieves detailed information about hotel rates including
pricing types, discounts, supplements, and rate configurations.
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
HOTEL_RATE_DETAILS_RQ_TOOL = Tool(
    name="hotel_rate_details_rq",
    description="""
    Retrieve comprehensive information about hotel rates and pricing structures.
    
    This tool provides detailed rate information including:
    - Rate names and descriptions
    - Rate types (discount, supplement, value, exchange)
    - Discount types and calculation methods
    - Rate application modes (optional, mandatory)
    - Promotional codes and restrictions
    - Rate visibility settings
    - Media assets and promotional materials
    - Creation dates and ordering
    
    Parameters:
    - hotel_ids (optional): List of hotel identifiers to get rates for
    - rate_ids (optional): List of specific rate identifiers
    - filters (optional): Additional filtering options
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Comprehensive rate details and configurations
    - Pricing structures and calculation methods
    - Application rules and restrictions
    - Marketing materials and media
    
    Example usage:
    "Get all rates for hotel 'HTL123'"
    "Show details for rate 'RATE456' in hotel 'HTL123'"
    "List discount rates for hotels 'HTL123' and 'HTL456'"
    "Get rates with promotional codes for hotel 'HTL789'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to get rates for (optional)",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 50
            },
            "rate_ids": {
                "type": "array",
                "description": "List of specific rate identifiers to retrieve (optional)",
                "items": {
                    "type": "string",
                    "description": "Rate identifier"
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


class HotelRateDetailsRQHandler:
    """Handler for the HotelRateDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_rate_details_rq")
    
    def _format_rate_visibility(self, visibility: Dict[str, Any]) -> Dict[str, Any]:
        """Format rate visibility information for readable output."""
        if not visibility:
            return {}
            
        return {
            "status": visibility.get("Status"),
            "date_published": visibility.get("DatePublished"),
            "time_published_from": visibility.get("TimePublishedFrom"),
            "time_published_to": visibility.get("TimePublishedTo"),
            "visible_countries": visibility.get("Countries", [])
        }
    
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
    
    def _format_rate_detail(self, rate_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format complete rate detail information for readable output."""
        formatted = {
            "hotel_id": rate_detail.get("HotelId"),
            "rate_id": rate_detail.get("HotelRateId"),
            "rate_name": rate_detail.get("HotelRateName"),
            "rate_description": rate_detail.get("HotelRateDescription"),
            "order": rate_detail.get("Order", 0),
            "rate_type": rate_detail.get("Type"),
            "discount_type": rate_detail.get("TypeDiscount"),
            "value": rate_detail.get("Value"),
            "rate_application": rate_detail.get("HotelRateApplication"),
            "creation_date": rate_detail.get("CreationDate")
        }
        
        # Format promotional code
        promo_code = rate_detail.get("PromoCode")
        if promo_code:
            formatted["promo_code"] = promo_code
        
        # Format visibility details
        visibility = rate_detail.get("RateVisibility", {})
        if visibility:
            formatted["visibility"] = self._format_rate_visibility(visibility)
        
        # Format media
        media = rate_detail.get("Media", [])
        if media:
            formatted["media"] = self._format_media(media)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel rate details request.
        
        Args:
            arguments: Tool arguments containing hotel/rate IDs and filters
            
        Returns:
            Dictionary containing the hotel rate details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids")
            rate_ids = arguments.get("rate_ids")
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
            
            # Validate and sanitize rate IDs if provided
            sanitized_rate_ids = None
            if rate_ids:
                if not isinstance(rate_ids, list):
                    raise ValidationError("rate_ids must be a list")
                
                sanitized_rate_ids = []
                for rate_id in rate_ids:
                    if not isinstance(rate_id, str) or not rate_id.strip():
                        raise ValidationError(f"Invalid rate ID: {rate_id}")
                    sanitized_rate_ids.append(sanitize_string(rate_id.strip()))
            
            self.logger.info(
                "Retrieving hotel rate details",
                hotel_count=len(sanitized_hotel_ids) if sanitized_hotel_ids else "all",
                rate_count=len(sanitized_rate_ids) if sanitized_rate_ids else "all",
                language=language,
                has_filters=bool(filters)
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            
            if sanitized_rate_ids:
                request_payload["RateId"] = sanitized_rate_ids
            
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
                
                # Make the hotel rate details request
                response = await client.post("/HotelRateDetailsRQ", request_payload)
            
            # Extract rate details from response
            rate_details_raw = response.get("HotelRateDetail", [])
            
            # Format rate details
            formatted_rates = []
            for rate_detail in rate_details_raw:
                formatted_rates.append(self._format_rate_detail(rate_detail))
            
            # Log successful operation
            self.logger.info(
                "Hotel rate details retrieved successfully",
                rate_count=len(formatted_rates),
                found_rates=len(rate_details_raw),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "rate_details": formatted_rates,
                "requested_hotel_ids": sanitized_hotel_ids,
                "requested_rate_ids": sanitized_rate_ids,
                "filters_applied": filters,
                "found_count": len(formatted_rates),
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "rates_found": len(formatted_rates),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {len(formatted_rates)} rate(s)"
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
handler = HotelRateDetailsRQHandler()


async def call_hotel_rate_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelRateDetailsRQ endpoint.
    
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
            
            response_text = f"""💲 **Hotel Rate Details**

✅ **Summary:**
- **Rates Found**: {summary['rates_found']}
- **Language**: {summary['language'].upper()}

"""
            
            # Display details for each rate
            for i, rate in enumerate(data["rate_details"], 1):
                response_text += f"""
{'='*70}
💲 **Rate #{i}: {rate.get('rate_name', 'Unnamed Rate')}**
{'='*70}

🏷️ **Basic Information:**
- **Rate ID**: {rate.get('rate_id', 'N/A')}
- **Hotel ID**: {rate.get('hotel_id', 'N/A')}
- **Name**: {rate.get('rate_name', 'N/A')}
- **Description**: {rate.get('rate_description', 'N/A')[:200]}{'...' if len(rate.get('rate_description', '')) > 200 else ''}
- **Creation Date**: {rate.get('creation_date', 'N/A')}
- **Order**: {rate.get('order', 'N/A')}
"""
                
                # Show rate type and configuration
                response_text += f"""
⚙️ **Rate Configuration:**
- **Type**: {rate.get('rate_type', 'N/A').title()}
- **Discount Type**: {rate.get('discount_type', 'N/A').replace('_', ' ').title()}
- **Application**: {rate.get('rate_application', 'N/A').title()}
"""
                
                if rate.get('value') is not None:
                    response_text += f"- **Value**: {rate['value']}\n"
                
                # Show promotional code if available
                promo_code = rate.get('promo_code')
                if promo_code:
                    response_text += f"""
🎫 **Promotional Code:**
- **Code**: {promo_code}
"""
                
                # Show visibility settings
                visibility = rate.get('visibility', {})
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
                media = rate.get('media', [])
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
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Hotel Rate Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel and rate IDs exist and are accessible
- Check your authentication credentials
- Ensure you have permission to view rate details
- Verify the filter parameters are correctly formatted
- Check promotional codes are valid
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving hotel rate details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
