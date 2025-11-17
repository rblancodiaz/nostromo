"""
PackageExtraAvailRQ - Package Extra Availability Tool

This tool retrieves availability information for extra services associated with tourism packages.
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
PACKAGE_EXTRA_AVAIL_RQ_TOOL = Tool(
    name="package_extra_avail_rq",
    description="""
    Retrieve availability information for extra services associated with tourism packages.
    
    This tool allows checking availability for additional services and extras that can be added
    to tourism packages. These extras can include things like spa services, excursions,
    transportation, special amenities, or other add-on services.
    
    Parameters:
    - package_availability_ids (required): List of package availability IDs to check extras for
    - basket_id (optional): Basket ID for context if working with a booking session
    - origin (optional): Booking origin identifier
    - client_location (optional): Client location information
    - client_device (optional): Client device type (desktop/mobile/tablet)
    
    Returns:
    - Available package extras with pricing and details
    - Availability information and restrictions
    - Service descriptions and inclusions
    - Pricing information for each extra service
    - Release and minimum stay requirements
    
    Example usage:
    "Check available extras for this vacation package"
    "What additional services can I add to this package?"
    "Show spa services available for this hotel package"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "package_availability_ids": {
                "type": "array",
                "description": "List of package availability IDs to check extras for",
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100
                },
                "minItems": 1,
                "maxItems": 50
            },
            "basket_id": {
                "type": "string",
                "description": "Basket ID for context if working with a booking session",
                "minLength": 1,
                "maxLength": 100
            },
            "origin": {
                "type": "string",
                "description": "Booking origin identifier",
                "maxLength": 100
            },
            "tracking": {
                "type": "object",
                "description": "Tracking information for the booking origin",
                "properties": {
                    "origin": {
                        "type": "string",
                        "enum": ["googlehpa", "trivago", "trivagocpa", "tripadvisor"],
                        "description": "Tracking origin"
                    },
                    "code": {
                        "type": "string",
                        "description": "Tracking code"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Tracking locale"
                    }
                },
                "required": ["origin", "code"],
                "additionalProperties": False
            },
            "client_location": {
                "type": "object",
                "description": "Client location information",
                "properties": {
                    "country": {
                        "type": "string",
                        "pattern": "^[A-Z]{2}$",
                        "description": "Country code (ISO 3166-1)"
                    },
                    "ip": {
                        "type": "string",
                        "description": "Client IP address"
                    }
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
        "required": ["package_availability_ids"],
        "additionalProperties": False
    }
)


class PackageExtraAvailRQHandler:
    """Handler for the PackageExtraAvailRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="package_extra_avail_rq")
    
    def _validate_package_availability_ids(self, ids: List[str]) -> List[str]:
        """Validate and sanitize package availability IDs."""
        if not ids:
            raise ValidationError("Package availability IDs are required")
        
        if len(ids) > 50:
            raise ValidationError("Maximum 50 package availability IDs allowed")
        
        validated_ids = []
        for i, availability_id in enumerate(ids):
            if not isinstance(availability_id, str) or not availability_id.strip():
                raise ValidationError(f"Package availability ID {i+1}: must be a non-empty string")
            
            sanitized_id = sanitize_string(availability_id.strip())
            if not sanitized_id:
                raise ValidationError(f"Package availability ID {i+1}: invalid format after sanitization")
            
            if len(sanitized_id) > 100:
                raise ValidationError(f"Package availability ID {i+1}: maximum 100 characters allowed")
            
            validated_ids.append(sanitized_id)
        
        return validated_ids
    
    def _format_package_extra_availability(self, extras: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format package extra availability information for readable output."""
        formatted_extras = []
        
        for extra in extras:
            formatted_extra = {
                "availability_id": extra.get("PackageExtraAvailabilityId"),
                "package_availability_id": extra.get("PackageAvailabilityId"),
                "extra_id": extra.get("PackageExtraId"),
                "release": extra.get("Release"),
                "min_stay": extra.get("MinStay"),
                "availability": extra.get("Availability"),
                "date_for_extra": extra.get("DateForExtra"),
                "amounts": {}
            }
            
            # Format amounts detail
            amounts = extra.get("PackageExtraAmounts", {})
            if amounts:
                formatted_extra["amounts"] = {
                    "extra_amount_type": amounts.get("ExtraAmountType"),
                    "currency": amounts.get("Currency"),
                    "final_amount": amounts.get("AmountFinal"),
                    "base_amount": amounts.get("AmountBase"),
                    "taxes_amount": amounts.get("AmountTaxes"),
                    "amount_before": amounts.get("AmountBefore"),
                    "amount_before_inventory": amounts.get("AmountBeforeInventory"),
                    "amount_before_max": amounts.get("AmountBeforeMax"),
                    "offers_amount": amounts.get("AmountOffers"),
                    "discounts_amount": amounts.get("AmountDiscounts")
                }
            
            formatted_extras.append(formatted_extra)
        
        return formatted_extras
    
    def _format_package_extra_not_available(self, extras: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format package extra not available information."""
        formatted_extras = []
        
        for extra in extras:
            formatted_extra = {
                "package_availability_id": extra.get("PackageAvailabilityId"),
                "extra_id": extra.get("PackageExtraId"),
                "extra_amount_type": extra.get("ExtraAmountType"),
                "release": extra.get("Release"),
                "min_stay": extra.get("MinStay"),
                "cause": {}
            }
            
            # Format cause information
            cause = extra.get("Cause", {})
            if cause:
                formatted_extra["cause"] = {
                    "code": cause.get("Code"),
                    "description": cause.get("Description"),
                    "target": cause.get("Target")
                }
            
            formatted_extras.append(formatted_extra)
        
        return formatted_extras
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the package extra availability request.
        
        Args:
            arguments: Tool arguments containing package availability IDs and options
            
        Returns:
            Dictionary containing the package extra availability results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            package_availability_ids = arguments.get("package_availability_ids", [])
            basket_id = arguments.get("basket_id")
            origin = arguments.get("origin")
            tracking = arguments.get("tracking", {})
            client_location = arguments.get("client_location", {})
            client_device = arguments.get("client_device", "desktop")
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_package_ids = self._validate_package_availability_ids(package_availability_ids)
            
            if basket_id and (not isinstance(basket_id, str) or len(basket_id.strip()) == 0):
                raise ValidationError("Basket ID must be a non-empty string if provided")
            
            if origin and (not isinstance(origin, str) or len(origin.strip()) == 0):
                raise ValidationError("Origin must be a non-empty string if provided")
            
            self.logger.info(
                "Requesting package extra availability",
                package_availability_ids_count=len(validated_package_ids),
                has_basket_id=bool(basket_id),
                has_origin=bool(origin),
                client_device=client_device,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "PackageAvailabilityId": validated_package_ids
            }
            
            # Add optional parameters
            if basket_id:
                request_payload["BasketId"] = sanitize_string(basket_id.strip())
            if origin:
                request_payload["Origin"] = sanitize_string(origin.strip())
            if tracking:
                request_payload["Tracking"] = tracking
            if client_location:
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
                
                # Make the package extra availability request
                response = await client.post("/PackageExtraAvailRQ", request_payload)
            
            # Extract data from response
            package_extra_avail = response.get("PackageExtraAvail", [])
            package_extra_not_avail = response.get("PackageExtraNotAvail", [])
            api_response = response.get("Response", {})
            
            # Format results
            formatted_extra_avail = self._format_package_extra_availability(package_extra_avail)
            formatted_extra_not_avail = self._format_package_extra_not_available(package_extra_not_avail)
            
            # Log successful operation
            self.logger.info(
                "Package extra availability request completed",
                extras_available=len(formatted_extra_avail),
                extras_not_available=len(formatted_extra_not_avail),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "package_availability_ids": validated_package_ids,
                    "basket_id": basket_id,
                    "origin": origin,
                    "client_device": client_device
                },
                "extras_available": formatted_extra_avail,
                "extras_not_available": formatted_extra_not_avail,
                "summary": {
                    "total_extras_available": len(formatted_extra_avail),
                    "total_extras_not_available": len(formatted_extra_not_avail),
                    "packages_checked": len(validated_package_ids)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found {len(formatted_extra_avail)} available package extras"
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
handler = PackageExtraAvailRQHandler()


async def call_package_extra_avail_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the PackageExtraAvailRQ endpoint.
    
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
            extras_available = data["extras_available"]
            extras_not_available = data["extras_not_available"]
            summary = data["summary"]
            search_criteria = data["search_criteria"]
            
            response_text = f"""🎁 **Package Extra Availability Results**

📊 **Search Summary:**
- **Total Extras Available**: {summary['total_extras_available']}
- **Extras Not Available**: {summary['total_extras_not_available']}
- **Packages Checked**: {summary['packages_checked']}

🔍 **Search Criteria:**
- **Package Availability IDs**: {len(search_criteria['package_availability_ids'])} package(s)
- **Basket ID**: {search_criteria.get('basket_id', 'Not specified')}
- **Origin**: {search_criteria.get('origin', 'Not specified')}
- **Client Device**: {search_criteria.get('client_device', 'desktop')}

"""
            
            if extras_available:
                response_text += f"""✅ **Available Package Extras ({len(extras_available)}):**
{'='*80}
"""
                
                for i, extra in enumerate(extras_available, 1):
                    amounts = extra.get('amounts', {})
                    response_text += f"""
🎁 **Extra Service #{i}**
{'-'*60}

🏷️ **Service Information:**
- **Availability ID**: {extra['availability_id']}
- **Package Availability ID**: {extra['package_availability_id']}
- **Extra Service ID**: {extra['extra_id']}
- **Release Days**: {extra.get('release', 'N/A')} day(s)
- **Minimum Stay**: {extra.get('min_stay', 'N/A')} night(s)
- **Availability**: {extra.get('availability', 'N/A')} unit(s)
"""
                    
                    if extra.get('date_for_extra'):
                        response_text += f"- **Service Date**: {extra['date_for_extra']}\n"
                    
                    # Pricing information
                    if amounts:
                        response_text += f"""
💰 **Pricing Information:**
- **Amount Type**: {amounts.get('extra_amount_type', 'N/A')}
- **Currency**: {amounts.get('currency', 'N/A')}
"""
                        if amounts.get('final_amount') is not None:
                            response_text += f"- **Final Amount**: {amounts['final_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('base_amount') is not None:
                            response_text += f"- **Base Amount**: {amounts['base_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('taxes_amount') is not None:
                            response_text += f"- **Taxes**: {amounts['taxes_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('offers_amount') is not None:
                            response_text += f"- **Offers Discount**: -{amounts['offers_amount']} {amounts.get('currency', '')}\n"
                        if amounts.get('discounts_amount') is not None:
                            response_text += f"- **Additional Discounts**: -{amounts['discounts_amount']} {amounts.get('currency', '')}\n"
                    
                    response_text += "\n"
            
            if extras_not_available:
                response_text += f"""❌ **Package Extras Not Available ({len(extras_not_available)}):**
{'='*80}
"""
                
                for i, extra in enumerate(extras_not_available, 1):
                    cause = extra.get('cause', {})
                    response_text += f"""
❌ **Unavailable Extra #{i}**
{'-'*60}

🏷️ **Service Information:**
- **Package Availability ID**: {extra['package_availability_id']}
- **Extra Service ID**: {extra['extra_id']}
- **Amount Type**: {extra.get('extra_amount_type', 'N/A')}
- **Release Days**: {extra.get('release', 'N/A')} day(s)
- **Minimum Stay**: {extra.get('min_stay', 'N/A')} night(s)

❌ **Unavailability Reason:**
- **Code**: {cause.get('code', 'N/A')}
- **Description**: {cause.get('description', 'No description provided')}
- **Target**: {cause.get('target', 'N/A')}

"""
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Package extras are additional services that can enhance your vacation
- Check availability and pricing before adding to your booking
- Some extras may have minimum stay or advance booking requirements
- Release days indicate how far in advance you need to book
- Amount types show how the extra is charged (per day, per stay, per person, etc.)
- Use basket context for better pricing and availability information
"""
                
        else:
            response_text = f"""❌ **Package Extra Availability Request Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the package availability IDs are valid and exist
- Check that the package IDs come from a successful package availability search
- Ensure the basket ID is valid if provided
- Verify authentication credentials
- Check that the packages actually have extra services available
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while checking package extra availability:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
