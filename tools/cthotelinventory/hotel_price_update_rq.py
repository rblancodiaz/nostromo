"""
HotelPriceUpdateRQ - Update Hotel Prices Tool

This tool updates hotel room pricing information for specific date ranges,
allowing dynamic pricing management across different occupancy scenarios.
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
HOTEL_PRICE_UPDATE_RQ_TOOL = Tool(
    name="hotel_price_update_rq",
    description="""
    Update hotel room pricing information for specific date ranges and occupancy scenarios.
    
    This tool allows updating pricing data including:
    - Base room prices by occupancy
    - Extra adult and child pricing
    - Rate and board specific pricing
    - Per-person accommodation pricing
    - Seasonal and dynamic pricing adjustments
    
    Parameters:
    - price_updates (required): List of price update objects
    - language (optional): Language code for the request (default: "es")
    
    Each price update object should contain:
    - hotel_id (required): Hotel identifier
    - room_id (required): Room identifier
    - date_from (required): Start date (YYYY-MM-DD)
    - date_to (required): End date (YYYY-MM-DD)
    - mode (required): Pricing mode ("pax", "occupancy", "accommodation")
    - partner (required): Partner mapping settings
    - pricing_data (required): Pricing information based on mode
    - rate_id (optional): Specific rate identifier
    - board_id (optional): Specific board identifier
    
    Returns:
    - Update operation success status
    - Processing results and confirmations
    
    Example usage:
    "Update base price to €120 for hotel 'HTL123' room 'RM456' from 2024-03-01 to 2024-03-31"
    "Set per-person price to €80 for 2 adults in hotel 'HTL123' room 'RM456' for next month"
    "Update accommodation price to €200 for hotel 'HTL123' room 'RM456' for weekend dates"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "price_updates": {
                "type": "array",
                "description": "List of price update operations to perform",
                "items": {
                    "type": "object",
                    "properties": {
                        "hotel_id": {
                            "type": "string",
                            "description": "Hotel identifier"
                        },
                        "room_id": {
                            "type": "string",
                            "description": "Room identifier"
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Start date for update period in YYYY-MM-DD format",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "date_to": {
                            "type": "string",
                            "description": "End date for update period in YYYY-MM-DD format",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "mode": {
                            "type": "string",
                            "description": "Pricing mode",
                            "enum": ["pax", "occupancy", "accommodation"]
                        },
                        "partner": {
                            "type": "object",
                            "description": "Partner mapping configuration",
                            "properties": {
                                "use_partner_mapping": {
                                    "type": "boolean",
                                    "description": "Whether to use partner ID mapping"
                                },
                                "partner_mapping_name": {
                                    "type": "string",
                                    "description": "Name of the partner mapping to use"
                                }
                            },
                            "required": ["use_partner_mapping"]
                        },
                        "pricing_data": {
                            "type": "object",
                            "description": "Pricing information based on the selected mode"
                        },
                        "rate_id": {
                            "type": "string",
                            "description": "Specific rate identifier (optional)"
                        },
                        "board_id": {
                            "type": "string",
                            "description": "Specific board identifier (optional)"
                        }
                    },
                    "required": ["hotel_id", "room_id", "date_from", "date_to", "mode", "partner", "pricing_data"]
                },
                "minItems": 1,
                "maxItems": 100
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["price_updates"],
        "additionalProperties": False
    }
)


class HotelPriceUpdateRQHandler:
    """Handler for the HotelPriceUpdateRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_price_update_rq")
    
    def _validate_price_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize a single price update object."""
        # Validate required fields
        required_fields = ["hotel_id", "room_id", "date_from", "date_to", "mode", "partner", "pricing_data"]
        for field in required_fields:
            if field not in update:
                raise ValidationError(f"Missing required field: {field}")
        
        # Sanitize and validate hotel and room IDs
        hotel_id = sanitize_string(update["hotel_id"])
        room_id = sanitize_string(update["room_id"])
        
        if not hotel_id:
            raise ValidationError("hotel_id cannot be empty")
        if not room_id:
            raise ValidationError("room_id cannot be empty")
        
        # Validate and parse dates
        date_from = parse_date(update["date_from"])
        date_to = parse_date(update["date_to"])
        
        # Validate date range
        from datetime import datetime
        date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
        date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
        
        if date_from_obj >= date_to_obj:
            raise ValidationError(f"date_from must be before date_to for hotel {hotel_id} room {room_id}")
        
        # Check date range is not too large (max 1 year)
        date_diff = (date_to_obj - date_from_obj).days
        if date_diff > 365:
            raise ValidationError(f"Date range cannot exceed 365 days for hotel {hotel_id} room {room_id}")
        
        # Validate mode
        mode = update["mode"]
        if mode not in ["pax", "occupancy", "accommodation"]:
            raise ValidationError(f"Invalid mode: {mode}. Must be 'pax', 'occupancy', or 'accommodation'")
        
        # Validate partner configuration
        partner = update["partner"]
        if not isinstance(partner, dict):
            raise ValidationError("partner must be an object")
        
        if "use_partner_mapping" not in partner:
            raise ValidationError("partner.use_partner_mapping is required")
        
        # Build validated update object
        validated_update = {
            "HotelId": hotel_id,
            "RoomId": room_id,
            "DateFrom": date_from,
            "DateTo": date_to,
            "Mode": mode,
            "Partner": {
                "UsePartnerMapping": partner["use_partner_mapping"]
            }
        }
        
        # Add optional partner mapping name
        if "partner_mapping_name" in partner and partner["partner_mapping_name"]:
            validated_update["Partner"]["PartnerMappingName"] = sanitize_string(partner["partner_mapping_name"])
        
        # Validate and add pricing data based on mode
        pricing_data = update["pricing_data"]
        if not isinstance(pricing_data, dict):
            raise ValidationError("pricing_data must be an object")
        
        if mode == "occupancy":
            self._validate_occupancy_pricing(pricing_data, validated_update, hotel_id, room_id)
        elif mode == "pax":
            self._validate_pax_pricing(pricing_data, validated_update, hotel_id, room_id)
        elif mode == "accommodation":
            self._validate_accommodation_pricing(pricing_data, validated_update, hotel_id, room_id)
        
        # Add optional rate and board IDs
        if "rate_id" in update and update["rate_id"]:
            validated_update["RateId"] = sanitize_string(update["rate_id"])
        
        if "board_id" in update and update["board_id"]:
            validated_update["BoardId"] = sanitize_string(update["board_id"])
        
        return validated_update
    
    def _validate_occupancy_pricing(self, pricing_data: Dict[str, Any], validated_update: Dict[str, Any], hotel_id: str, room_id: str):
        """Validate occupancy-based pricing data."""
        if "base_price" not in pricing_data:
            raise ValidationError(f"base_price is required for occupancy mode for hotel {hotel_id} room {room_id}")
        
        base_price = pricing_data["base_price"]
        if not isinstance(base_price, (int, float)) or base_price < 0:
            raise ValidationError(f"base_price must be a non-negative number for hotel {hotel_id} room {room_id}")
        
        occupancy_obj = {"BasePrice": base_price}
        
        # Validate extra adults pricing
        extra_adults_price = pricing_data.get("extra_adults_price")
        if extra_adults_price is not None:
            if not isinstance(extra_adults_price, list):
                raise ValidationError(f"extra_adults_price must be a list for hotel {hotel_id} room {room_id}")
            
            validated_extra_adults = []
            for i, price in enumerate(extra_adults_price):
                if not isinstance(price, (int, float)) or price < 0:
                    raise ValidationError(f"extra_adults_price[{i}] must be a non-negative number for hotel {hotel_id} room {room_id}")
                validated_extra_adults.append(price)
            
            if validated_extra_adults:
                occupancy_obj["ExtraAdultsPrice"] = validated_extra_adults
        
        # Validate extra child pricing
        extra_child_price = pricing_data.get("extra_child_price")
        if extra_child_price is not None:
            if not isinstance(extra_child_price, list):
                raise ValidationError(f"extra_child_price must be a list for hotel {hotel_id} room {room_id}")
            
            validated_extra_children = []
            for i, price in enumerate(extra_child_price):
                if not isinstance(price, (int, float)) or price < 0:
                    raise ValidationError(f"extra_child_price[{i}] must be a non-negative number for hotel {hotel_id} room {room_id}")
                validated_extra_children.append(price)
            
            if validated_extra_children:
                occupancy_obj["ExtraChildPrice"] = validated_extra_children
        
        validated_update["Occupancy"] = occupancy_obj
    
    def _validate_pax_pricing(self, pricing_data: Dict[str, Any], validated_update: Dict[str, Any], hotel_id: str, room_id: str):
        """Validate per-person pricing data."""
        if "pax_configurations" not in pricing_data:
            raise ValidationError(f"pax_configurations is required for pax mode for hotel {hotel_id} room {room_id}")
        
        pax_configurations = pricing_data["pax_configurations"]
        if not isinstance(pax_configurations, list) or len(pax_configurations) == 0:
            raise ValidationError(f"pax_configurations must be a non-empty list for hotel {hotel_id} room {room_id}")
        
        validated_pax = []
        for i, config in enumerate(pax_configurations):
            if not isinstance(config, dict):
                raise ValidationError(f"pax_configurations[{i}] must be an object for hotel {hotel_id} room {room_id}")
            
            if "adults" not in config or "price" not in config:
                raise ValidationError(f"pax_configurations[{i}] must contain 'adults' and 'price' for hotel {hotel_id} room {room_id}")
            
            adults = config["adults"]
            if not isinstance(adults, int) or adults < 1:
                raise ValidationError(f"pax_configurations[{i}].adults must be a positive integer for hotel {hotel_id} room {room_id}")
            
            children = config.get("children", 0)
            if not isinstance(children, int) or children < 0:
                raise ValidationError(f"pax_configurations[{i}].children must be a non-negative integer for hotel {hotel_id} room {room_id}")
            
            babies = config.get("babies", 0)
            if not isinstance(babies, int) or babies < 0:
                raise ValidationError(f"pax_configurations[{i}].babies must be a non-negative integer for hotel {hotel_id} room {room_id}")
            
            price = config["price"]
            if not isinstance(price, (int, float)) or price < 0:
                raise ValidationError(f"pax_configurations[{i}].price must be a non-negative number for hotel {hotel_id} room {room_id}")
            
            pax_obj = {
                "Adult": adults,
                "Price": price
            }
            
            if children > 0:
                pax_obj["Child"] = children
            if babies > 0:
                pax_obj["Baby"] = babies
            
            validated_pax.append(pax_obj)
        
        validated_update["Pax"] = validated_pax
    
    def _validate_accommodation_pricing(self, pricing_data: Dict[str, Any], validated_update: Dict[str, Any], hotel_id: str, room_id: str):
        """Validate accommodation pricing data."""
        if "accommodation_price" not in pricing_data:
            raise ValidationError(f"accommodation_price is required for accommodation mode for hotel {hotel_id} room {room_id}")
        
        accommodation_price = pricing_data["accommodation_price"]
        if not isinstance(accommodation_price, (int, float)) or accommodation_price < 0:
            raise ValidationError(f"accommodation_price must be a non-negative number for hotel {hotel_id} room {room_id}")
        
        validated_update["Accommodation"] = {"Price": accommodation_price}
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hotel price update request.
        
        Args:
            arguments: Tool arguments containing price updates
            
        Returns:
            Dictionary containing the update operation results
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            price_updates = arguments.get("price_updates", [])
            language = arguments.get("language", "es")
            
            # Validate price updates
            if not price_updates:
                raise ValidationError("At least one price update is required")
            
            if not isinstance(price_updates, list):
                raise ValidationError("price_updates must be a list")
            
            if len(price_updates) > 100:
                raise ValidationError("Cannot process more than 100 price updates at once")
            
            # Validate and sanitize each update
            validated_updates = []
            for i, update in enumerate(price_updates):
                try:
                    validated_update = self._validate_price_update(update)
                    validated_updates.append(validated_update)
                except ValidationError as e:
                    raise ValidationError(f"Price update #{i+1}: {e.message}")
            
            self.logger.info(
                "Updating hotel prices",
                update_count=len(validated_updates),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            request_payload["PriceUpdate"] = validated_updates
            
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
                
                # Make the hotel price update request
                response = await client.post("/HotelPriceUpdateRQ", request_payload)
            
            # Extract success status from response
            success_status = response.get("Success", False)
            
            # Log successful operation
            self.logger.info(
                "Hotel price update completed",
                update_count=len(validated_updates),
                success=success_status,
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "update_success": success_status,
                "updates_processed": len(validated_updates),
                "price_updates": validated_updates,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_updates": len(validated_updates),
                    "success": success_status,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Processed {len(validated_updates)} price update(s) with {'success' if success_status else 'warnings/errors'}"
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
handler = HotelPriceUpdateRQHandler()


async def call_hotel_price_update_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the HotelPriceUpdateRQ endpoint.
    
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
            
            response_text = f"""💰 **Hotel Price Update Results**

✅ **Summary:**
- **Updates Processed**: {summary['total_updates']}
- **Update Success**: {'✅ Yes' if summary['success'] else '⚠️ With Warnings/Errors'}
- **Language**: {summary['language'].upper()}

"""
            
            # Display details for each update
            updates = data["price_updates"]
            for i, update in enumerate(updates, 1):
                response_text += f"""
{'='*50}
💰 **Price Update #{i}**
{'='*50}

🏨 **Target:**
- **Hotel ID**: {update.get('HotelId', 'N/A')}
- **Room ID**: {update.get('RoomId', 'N/A')}
- **Date Range**: {update.get('DateFrom', 'N/A')} to {update.get('DateTo', 'N/A')}
- **Pricing Mode**: {update.get('Mode', 'N/A').title()}
"""
                
                # Show rate and board if specified
                if update.get('RateId'):
                    response_text += f"- **Rate ID**: {update['RateId']}\n"
                if update.get('BoardId'):
                    response_text += f"- **Board ID**: {update['BoardId']}\n"
                
                # Show pricing details based on mode
                mode = update.get('Mode', '')
                
                if mode == 'occupancy' and 'Occupancy' in update:
                    occupancy = update['Occupancy']
                    response_text += f"""
💰 **Occupancy-Based Pricing:**
- **Base Price**: €{occupancy.get('BasePrice', 'N/A')}
"""
                    
                    extra_adults = occupancy.get('ExtraAdultsPrice', [])
                    if extra_adults:
                        response_text += f"- **Extra Adults**: {', '.join([f'€{price}' for price in extra_adults])}\n"
                    
                    extra_children = occupancy.get('ExtraChildPrice', [])
                    if extra_children:
                        response_text += f"- **Extra Children**: {', '.join([f'€{price}' for price in extra_children])}\n"
                
                elif mode == 'pax' and 'Pax' in update:
                    pax_configs = update['Pax']
                    response_text += f"""
👥 **Per-Person Pricing:**
"""
                    for j, pax in enumerate(pax_configs, 1):
                        adults = pax.get('Adult', 0)
                        children = pax.get('Child', 0)
                        babies = pax.get('Baby', 0)
                        price = pax.get('Price', 0)
                        
                        config_text = f"{adults} adult(s)"
                        if children > 0:
                            config_text += f", {children} child(ren)"
                        if babies > 0:
                            config_text += f", {babies} baby/babies"
                        
                        response_text += f"- **Config {j}**: {config_text} = €{price}\n"
                
                elif mode == 'accommodation' and 'Accommodation' in update:
                    accommodation = update['Accommodation']
                    response_text += f"""
🏠 **Accommodation Pricing:**
- **Fixed Price**: €{accommodation.get('Price', 'N/A')} (regardless of occupancy)
"""
                
                # Show partner configuration
                partner = update.get('Partner', {})
                if partner:
                    response_text += f"""
🤝 **Partner Configuration:**
- **Use Partner Mapping**: {'Yes' if partner.get('UsePartnerMapping') else 'No'}
"""
                    if partner.get('PartnerMappingName'):
                        response_text += f"- **Partner Name**: {partner['PartnerMappingName']}\n"
            
            # Show overall operation status
            if data["update_success"]:
                response_text += f"""

✅ **Operation Status: SUCCESS**

All price updates have been processed successfully. The new pricing is now active in the booking system.

📋 **Next Steps:**
- Changes are immediately reflected in availability searches
- Monitor booking patterns to assess pricing impact
- You can verify the updates using availability search tools
- Consider seasonal adjustments based on demand
"""
            else:
                response_text += f"""

⚠️ **Operation Status: COMPLETED WITH WARNINGS**

The price updates have been processed, but there may have been warnings or partial failures. Please review the details above and check the system logs for more information.

📋 **Recommended Actions:**
- Verify the updates using availability search tools
- Check for any error notifications in the system
- Review pricing conflicts with existing rate rules
- Contact support if issues persist
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Update Hotel Prices**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify all hotel and room IDs exist and are accessible
- Check your authentication credentials and permissions
- Ensure all date ranges are valid (YYYY-MM-DD format)
- Verify date_from is before date_to for all updates
- Check that all price values are non-negative numbers
- Ensure pricing mode matches the provided pricing data structure
- Verify partner mapping configuration
- Check that occupancy configurations are realistic
- Ensure you have pricing management permissions
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while updating hotel prices:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
