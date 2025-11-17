"""
GenericProductExtraAvailRQ - Generic Product Extra Availability Tool

This tool searches for availability of extras/supplements for generic products,
providing pricing and availability information for additional services.
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
GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL = Tool(
    name="generic_product_extra_avail_rq",
    description="""
    Search for availability of extras/supplements for generic products.
    
    This tool retrieves extra services and supplements available for generic products:
    - Extra service availability and pricing
    - Supplement options and restrictions
    - Release and minimum stay requirements
    - Available quantities and dates
    - Pricing structures and billing methods
    
    Parameters:
    - product_availability_ids (required): List of product availability IDs to search extras for
    - basket_id (optional): Basket ID for context and pricing
    - origin (optional): Origin of the reservation for tracking
    - client_country (optional): Country of the client
    - client_ip (optional): IP address of the client
    - client_device (optional): Type of client device
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Available extras with pricing and restrictions
    - Unavailable extras with reasons
    - Release and minimum stay requirements
    - Quantity and date availability
    - Detailed pricing information
    
    Example usage:
    "Get extras for product availability ID AVAIL123"
    "Search extras for multiple product availabilities"
    "Find available supplements with basket context"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "product_availability_ids": {
                "type": "array",
                "description": "List of generic product availability IDs to search extras for",
                "items": {
                    "type": "string",
                    "description": "Generic product availability identifier"
                },
                "minItems": 1,
                "maxItems": 50
            },
            "basket_id": {
                "type": "string",
                "description": "Basket ID for context and pricing calculations",
                "maxLength": 100
            },
            "origin": {
                "type": "string",
                "description": "Origin of the reservation for tracking purposes",
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
        "required": ["product_availability_ids"],
        "additionalProperties": False
    }
)


class GenericProductExtraAvailRQHandler:
    """Handler for the GenericProductExtraAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="generic_product_extra_avail_rq")
    
    def _format_extra_amounts(self, amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Format extra amounts information for readable output."""
        if not amounts:
            return {}
        
        return {
            "amount_type": amounts.get("ExtraAmountType"),
            "currency": amounts.get("Currency"),
            "final_amount": amounts.get("AmountFinal"),
            "base_amount": amounts.get("AmountBase"),
            "taxes_amount": amounts.get("AmountTaxes"),
            "before_amount": amounts.get("AmountBefore"),
            "inventory_amount": amounts.get("AmountBeforeInventory"),
            "max_amount": amounts.get("AmountBeforeMax"),
            "offers_amount": amounts.get("AmountOffers"),
            "discounts_amount": amounts.get("AmountDiscounts")
        }
    
    def _format_extra_avail(self, extra_avail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format generic product extra availability information."""
        formatted = []
        for extra in extra_avail:
            formatted_extra = {
                "extra_availability_id": extra.get("GenericProductExtraAvailabilityId"),
                "product_availability_id": extra.get("GenericProductAvailabilityId"),
                "extra_id": extra.get("GenericProductExtraId"),
                "release": extra.get("Release"),
                "min_stay": extra.get("MinStay"),
                "availability": extra.get("Availability"),
                "date_for_extra": extra.get("DateForExtra")
            }
            
            # Format extra amounts
            extra_amounts = extra.get("GenericProductExtraAmounts", {})
            if extra_amounts:
                formatted_extra["amounts"] = self._format_extra_amounts(extra_amounts)
            
            formatted.append(formatted_extra)
        
        return formatted
    
    def _format_extra_not_avail(self, extra_not_avail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format generic product extra not available information."""
        formatted = []
        for extra in extra_not_avail:
            formatted_extra = {
                "product_availability_id": extra.get("GenericProductAvailabilityId"),
                "extra_id": extra.get("GenericProductExtraId"),
                "amount_type": extra.get("ExtraAmountType"),
                "release": extra.get("Release"),
                "min_stay": extra.get("MinStay"),
                "cause": {
                    "code": extra.get("Cause", {}).get("Code"),
                    "description": extra.get("Cause", {}).get("Description"),
                    "target": extra.get("Cause", {}).get("Target")
                }
            }
            
            formatted.append(formatted_extra)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the generic product extra availability request.
        
        Args:
            arguments: Tool arguments containing search criteria
            
        Returns:
            Dictionary containing the extra availability results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            product_availability_ids = arguments.get("product_availability_ids", [])
            basket_id = arguments.get("basket_id")
            origin = arguments.get("origin")
            client_country = arguments.get("client_country")
            client_ip = arguments.get("client_ip")
            client_device = arguments.get("client_device")
            language = arguments.get("language", "es")
            
            # Validate required fields
            if not product_availability_ids:
                raise ValidationError("At least one product availability ID is required")
            
            # Sanitize product availability IDs
            sanitized_availability_ids = []
            for availability_id in product_availability_ids:
                if not isinstance(availability_id, str) or not availability_id.strip():
                    raise ValidationError(f"Invalid product availability ID: {availability_id}")
                sanitized_availability_ids.append(sanitize_string(availability_id.strip()))
            
            # Sanitize optional string inputs
            sanitized_basket_id = None
            if basket_id:
                if not isinstance(basket_id, str) or not basket_id.strip():
                    raise ValidationError(f"Invalid basket ID: {basket_id}")
                sanitized_basket_id = sanitize_string(basket_id.strip())
            
            sanitized_origin = None
            if origin:
                if not isinstance(origin, str) or not origin.strip():
                    raise ValidationError(f"Invalid origin: {origin}")
                sanitized_origin = sanitize_string(origin.strip())
            
            sanitized_client_country = None
            if client_country:
                if not isinstance(client_country, str) or not client_country.strip():
                    raise ValidationError(f"Invalid client country: {client_country}")
                country_code = client_country.strip().upper()
                if len(country_code) != 2:
                    raise ValidationError(f"Client country code must be 2 characters: {client_country}")
                sanitized_client_country = country_code
            
            sanitized_client_ip = None
            if client_ip:
                if not isinstance(client_ip, str) or not client_ip.strip():
                    raise ValidationError(f"Invalid client IP: {client_ip}")
                sanitized_client_ip = sanitize_string(client_ip.strip())
            
            self.logger.info(
                "Searching for generic product extra availability",
                availability_ids_count=len(sanitized_availability_ids),
                basket_id=sanitized_basket_id,
                origin=sanitized_origin,
                client_country=sanitized_client_country,
                client_device=client_device,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            # Add required parameters
            request_payload["GenericProductAvailabilityId"] = sanitized_availability_ids
            
            # Add optional parameters
            if sanitized_basket_id:
                request_payload["BasketId"] = sanitized_basket_id
            if sanitized_origin:
                request_payload["Origin"] = sanitized_origin
            
            # Add client location data if provided
            if sanitized_client_country or sanitized_client_ip:
                client_location = {}
                if sanitized_client_country:
                    client_location["Country"] = sanitized_client_country
                if sanitized_client_ip:
                    client_location["Ip"] = sanitized_client_ip
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
                
                # Make the generic product extra availability request
                response = await client.post("/GenericProductExtraAvailRQ", request_payload)
            
            # Extract extra availability results from response
            extra_avail = response.get("GenericProductExtraAvail", [])
            extra_not_avail = response.get("GenericProductExtraNotAvail", [])
            
            # Format results
            formatted_extra_avail = self._format_extra_avail(extra_avail)
            formatted_extra_not_avail = self._format_extra_not_avail(extra_not_avail)
            
            # Log successful operation
            self.logger.info(
                "Generic product extra availability search completed successfully",
                available_extras=len(formatted_extra_avail),
                unavailable_extras=len(formatted_extra_not_avail),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "available_extras": formatted_extra_avail,
                "unavailable_extras": formatted_extra_not_avail,
                "search_criteria": {
                    "product_availability_ids": sanitized_availability_ids,
                    "basket_id": sanitized_basket_id,
                    "origin": sanitized_origin,
                    "client_country": sanitized_client_country,
                    "client_ip": sanitized_client_ip,
                    "client_device": client_device,
                    "language": language
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_availability_ids": len(sanitized_availability_ids),
                    "available_extras_count": len(formatted_extra_avail),
                    "unavailable_extras_count": len(formatted_extra_not_avail),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(formatted_extra_avail)} available and {len(formatted_extra_not_avail)} unavailable extra(s)"
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
handler = GenericProductExtraAvailRQHandler()


async def call_generic_product_extra_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the GenericProductExtraAvailRQ endpoint.
    
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
            criteria = data["search_criteria"]
            
            response_text = f"""🎁 **Generic Product Extra Availability**

✅ **Search Summary:**
- **Product Availability IDs Searched**: {summary['total_availability_ids']}
- **Available Extras**: {summary['available_extras_count']}
- **Unavailable Extras**: {summary['unavailable_extras_count']}
- **Language**: {summary['language'].upper()}

📋 **Search Criteria:**
- **Product Availability IDs**: {len(criteria['product_availability_ids'])} specified
"""
            if criteria["basket_id"]:
                response_text += f"- **Basket ID**: {criteria['basket_id']}\n"
            if criteria["origin"]:
                response_text += f"- **Origin**: {criteria['origin']}\n"
            if criteria["client_country"]:
                response_text += f"- **Client Country**: {criteria['client_country']}\n"
            if criteria["client_device"]:
                response_text += f"- **Client Device**: {criteria['client_device'].title()}\n"
            
            # Display available extras
            if data["available_extras"]:
                response_text += f"""

🎁 **Available Extras ({len(data['available_extras'])}):**
{'='*80}
"""
                
                for i, extra in enumerate(data["available_extras"], 1):
                    response_text += f"""
🎁 **Extra #{i}**
{'-'*60}

🏷️ **Basic Information:**
- **Extra Availability ID**: {extra.get('extra_availability_id', 'N/A')}
- **Product Availability ID**: {extra.get('product_availability_id', 'N/A')}
- **Extra ID**: {extra.get('extra_id', 'N/A')}
- **Availability**: {extra.get('availability', 'N/A')}
- **Release**: {extra.get('release', 'N/A')} days
- **Minimum Stay**: {extra.get('min_stay', 'N/A')} nights
"""
                    
                    if extra.get('date_for_extra'):
                        response_text += f"- **Date for Extra**: {extra['date_for_extra']}\n"
                    
                    # Pricing information
                    amounts = extra.get('amounts', {})
                    if amounts and amounts.get('final_amount'):
                        response_text += f"""
💰 **Pricing:**
- **Final Price**: {amounts.get('final_amount', 'N/A')} {amounts.get('currency', '')}
- **Base Price**: {amounts.get('base_amount', 'N/A')} {amounts.get('currency', '')}
- **Amount Type**: {amounts.get('amount_type', 'N/A')}
"""
                        if amounts.get('taxes_amount') and amounts['taxes_amount'] > 0:
                            response_text += f"- **Taxes**: {amounts['taxes_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('offers_amount') and amounts['offers_amount'] > 0:
                            response_text += f"- **Offers Discount**: -{amounts['offers_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('discounts_amount') and amounts['discounts_amount'] > 0:
                            response_text += f"- **Additional Discounts**: -{amounts['discounts_amount']} {amounts.get('currency', '')}\n"
                    
                    response_text += "\n"
            
            # Display unavailable extras
            if data["unavailable_extras"]:
                response_text += f"""❌ **Unavailable Extras ({len(data['unavailable_extras'])}):**
{'='*80}
"""
                
                for i, extra in enumerate(data["unavailable_extras"], 1):
                    cause = extra.get('cause', {})
                    response_text += f"""
❌ **Unavailable Extra #{i}**
- **Product Availability ID**: {extra.get('product_availability_id', 'N/A')}
- **Extra ID**: {extra.get('extra_id', 'N/A')}
- **Amount Type**: {extra.get('amount_type', 'N/A')}
- **Release**: {extra.get('release', 'N/A')} days
- **Minimum Stay**: {extra.get('min_stay', 'N/A')} nights
- **Reason Code**: {cause.get('code', 'N/A')}
- **Reason**: {cause.get('description', 'N/A')}
- **Target**: {cause.get('target', 'N/A')}

"""
            
            if not data["available_extras"] and not data["unavailable_extras"]:
                response_text += """
❌ **No Extras Found**

No extra services are available for the specified product availability IDs. This could mean:
- The products don't have additional extras
- Extras are not configured for these products
- All extras are currently unavailable
- The product availability IDs are invalid
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use extra availability IDs for basket operations
- Check release requirements for booking timing
- Review minimum stay constraints
- Consider pricing when selecting extras
- Use basket context for accurate pricing
- Check availability dates for scheduling
- Review amount types for billing understanding
"""
        else:
            response_text = f"""❌ **Generic Product Extra Availability Search Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify product availability IDs are valid and exist
- Check basket ID format if provided
- Ensure client location data is correct
- Verify authentication credentials
- Review API endpoint availability
- Check if products have extras configured
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while searching for generic product extra availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
