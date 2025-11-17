"""
GenericProductDetailsRQ - Generic Product Details Tool

This tool retrieves detailed information about generic products including
specifications, descriptions, categories, and associated services.
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
GENERIC_PRODUCT_DETAILS_RQ_TOOL = Tool(
    name="generic_product_details_rq",
    description="""
    Retrieve detailed information about generic products in the system.
    
    This tool provides comprehensive details about generic products including:
    - Product specifications and descriptions
    - Categories and classifications
    - Hotel and room associations
    - Reservation modes and methods
    - Media and promotional content
    - Status and availability settings
    
    Parameters:
    - product_ids (optional): List of specific product IDs to retrieve
    - hotel_ids (optional): List of hotel IDs to filter products by
    - hotel_room_ids (optional): List of room IDs to filter products by
    - status (optional): Filter by product status (enabled, disabled, all)
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Detailed product information including specifications
    - Product categories and classifications
    - Hotel and room associations
    - Media content and descriptions
    - Reservation settings and constraints
    
    Example usage:
    "Get details for product ID PROD123"
    "Show all products for hotel HOTEL456"
    "List enabled products in room ROOM789"
    "Get all product details regardless of status"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "product_ids": {
                "type": "array",
                "description": "List of specific generic product IDs to retrieve details for",
                "items": {
                    "type": "string",
                    "description": "Generic product identifier"
                },
                "maxItems": 50
            },
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel IDs to filter products by",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 20
            },
            "hotel_room_ids": {
                "type": "array",
                "description": "List of hotel room IDs to filter products by",
                "items": {
                    "type": "string",
                    "description": "Hotel room identifier"
                },
                "maxItems": 100
            },
            "status": {
                "type": "string",
                "description": "Filter products by their status",
                "enum": ["enabled", "disabled", "all"],
                "default": "enabled"
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


class GenericProductDetailsRQHandler:
    """Handler for the GenericProductDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="generic_product_details_rq")
    
    def _format_categories(self, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format product categories for readable output."""
        formatted = []
        for category in categories:
            formatted.append({
                "code": category.get("Code"),
                "name": category.get("Name")
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
    
    def _format_product_detail(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Format generic product detail information for readable output."""
        formatted = {
            "product_id": product.get("GenericProductId"),
            "hotel_id": product.get("HotelId"),
            "hotel_hash": product.get("HotelHash"),
            "product_name": product.get("GenericProductName"),
            "product_description": product.get("GenericProductDescription"),
            "status": product.get("Status"),
            "reservation_mode": product.get("ReservationMode"),
            "reservation_limit": product.get("ReservationLimit"),
            "combinable": product.get("Combinable"),
            "order": product.get("Order")
        }
        
        # Format categories
        categories = product.get("GenericProductCategory", [])
        if categories:
            formatted["categories"] = self._format_categories(categories)
        
        # Format associated hotel rooms
        hotel_room_ids = product.get("HotelRoomId", [])
        if hotel_room_ids:
            formatted["hotel_room_ids"] = hotel_room_ids
        
        # Format associated hotel boards
        hotel_board_ids = product.get("HotelBoardId", [])
        if hotel_board_ids:
            formatted["hotel_board_ids"] = hotel_board_ids
        
        # Format associated hotel room extras
        hotel_room_extra_ids = product.get("HotelRoomExtraId", [])
        if hotel_room_extra_ids:
            formatted["hotel_room_extra_ids"] = hotel_room_extra_ids
        
        # Format media
        media = product.get("Media", [])
        if media:
            formatted["media"] = self._format_media(media)
        
        return formatted
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the generic product details request.
        
        Args:
            arguments: Tool arguments containing search criteria
            
        Returns:
            Dictionary containing the product details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            product_ids = arguments.get("product_ids", [])
            hotel_ids = arguments.get("hotel_ids", [])
            hotel_room_ids = arguments.get("hotel_room_ids", [])
            status = arguments.get("status", "enabled")
            language = arguments.get("language", "es")
            
            # Sanitize string inputs
            sanitized_product_ids = []
            if product_ids:
                for product_id in product_ids:
                    if not isinstance(product_id, str) or not product_id.strip():
                        raise ValidationError(f"Invalid product ID: {product_id}")
                    sanitized_product_ids.append(sanitize_string(product_id.strip()))
            
            sanitized_hotel_ids = []
            if hotel_ids:
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            sanitized_room_ids = []
            if hotel_room_ids:
                for room_id in hotel_room_ids:
                    if not isinstance(room_id, str) or not room_id.strip():
                        raise ValidationError(f"Invalid hotel room ID: {room_id}")
                    sanitized_room_ids.append(sanitize_string(room_id.strip()))
            
            self.logger.info(
                "Retrieving generic product details",
                product_ids_count=len(sanitized_product_ids),
                hotel_ids_count=len(sanitized_hotel_ids),
                room_ids_count=len(sanitized_room_ids),
                status=status,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            # Add optional parameters
            if sanitized_product_ids:
                request_payload["GenericProductId"] = sanitized_product_ids
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            if sanitized_room_ids:
                request_payload["HotelRoomId"] = sanitized_room_ids
            if status != "enabled":
                request_payload["Status"] = status
            
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
                
                # Make the generic product details request
                response = await client.post("/GenericProductDetailsRQ", request_payload)
            
            # Extract product details from response
            products_raw = response.get("GenericProductDetail", [])
            
            # Format product results
            formatted_products = []
            for product in products_raw:
                formatted_products.append(self._format_product_detail(product))
            
            # Log successful operation
            self.logger.info(
                "Generic product details retrieved successfully",
                found_products=len(formatted_products),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "products": formatted_products,
                "search_criteria": {
                    "product_ids": sanitized_product_ids,
                    "hotel_ids": sanitized_hotel_ids,
                    "hotel_room_ids": sanitized_room_ids,
                    "status": status,
                    "language": language
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_found": len(formatted_products),
                    "status_filter": status,
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved {len(formatted_products)} product detail(s)"
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
handler = GenericProductDetailsRQHandler()


async def call_generic_product_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the GenericProductDetailsRQ endpoint.
    
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
            
            response_text = f"""📦 **Generic Product Details**

✅ **Search Summary:**
- **Total Products Found**: {summary['total_found']:,}
- **Status Filter**: {summary['status_filter'].title()}
- **Language**: {summary['language'].upper()}

📋 **Search Criteria:**
"""
            if criteria["product_ids"]:
                response_text += f"- **Specific Product IDs**: {len(criteria['product_ids'])} specified\n"
            if criteria["hotel_ids"]:
                response_text += f"- **Hotel IDs**: {len(criteria['hotel_ids'])} specified\n"
            if criteria["hotel_room_ids"]:
                response_text += f"- **Room IDs**: {len(criteria['hotel_room_ids'])} specified\n"
            
            if not any([criteria["product_ids"], criteria["hotel_ids"], criteria["hotel_room_ids"]]):
                response_text += "- **No specific filters applied** (showing all products)\n"
            
            # Display product details
            if data["products"]:
                response_text += f"""
📦 **Product Details ({len(data['products'])} found):**
{'='*80}
"""
                
                for i, product in enumerate(data["products"], 1):
                    response_text += f"""
📦 **Product #{i}: {product.get('product_name', 'Unknown Product')}**
{'-'*60}

🏷️ **Basic Information:**
- **Product ID**: {product.get('product_id', 'N/A')}
- **Name**: {product.get('product_name', 'N/A')}
- **Description**: {product.get('product_description', 'N/A')[:200]}{'...' if len(product.get('product_description', '')) > 200 else ''}
- **Hotel ID**: {product.get('hotel_id', 'N/A')}
- **Status**: {product.get('status', 'N/A').title() if product.get('status') else 'N/A'}
- **Order**: {product.get('order', 'N/A')}

🔧 **Configuration:**
- **Reservation Mode**: {product.get('reservation_mode', 'N/A').title() if product.get('reservation_mode') else 'N/A'}
- **Reservation Limit**: {product.get('reservation_limit', 'N/A')}
- **Combinable**: {product.get('combinable', 'N/A').title() if product.get('combinable') else 'N/A'}
"""
                    
                    # Categories
                    categories = product.get('categories', [])
                    if categories:
                        category_names = [f"{cat['name']} ({cat['code']})" for cat in categories]
                        response_text += f"""
📂 **Categories**: {', '.join(category_names)}
"""
                    
                    # Associated hotel rooms
                    hotel_room_ids = product.get('hotel_room_ids', [])
                    if hotel_room_ids:
                        response_text += f"""
🏠 **Associated Hotel Rooms** ({len(hotel_room_ids)}):
{', '.join(hotel_room_ids[:10])}{'...' if len(hotel_room_ids) > 10 else ''}
"""
                    
                    # Associated hotel boards
                    hotel_board_ids = product.get('hotel_board_ids', [])
                    if hotel_board_ids:
                        response_text += f"""
🍽️ **Associated Hotel Boards** ({len(hotel_board_ids)}):
{', '.join(hotel_board_ids[:10])}{'...' if len(hotel_board_ids) > 10 else ''}
"""
                    
                    # Associated hotel room extras
                    hotel_room_extra_ids = product.get('hotel_room_extra_ids', [])
                    if hotel_room_extra_ids:
                        response_text += f"""
🎁 **Associated Room Extras** ({len(hotel_room_extra_ids)}):
{', '.join(hotel_room_extra_ids[:10])}{'...' if len(hotel_room_extra_ids) > 10 else ''}
"""
                    
                    # Media
                    media = product.get('media', [])
                    if media:
                        response_text += f"""
📸 **Media Content** ({len(media)} item(s)):
"""
                        for media_item in media[:5]:
                            response_text += f"- {media_item['type'].title()}: {media_item.get('caption', 'No caption')}"
                            if media_item.get('is_main'):
                                response_text += " 🌟 (Main)"
                            response_text += "\n"
                        if len(media) > 5:
                            response_text += f"... and {len(media) - 5} more media items\n"
                    
                    response_text += "\n"
            
            else:
                response_text += """
❌ **No Products Found**

No products match your search criteria. Try:
- Removing specific ID filters
- Changing the status filter to 'all'
- Checking different hotel or room IDs
- Verifying product IDs exist in the system
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use product IDs for availability searches
- Review categories for product classification
- Check associated rooms and extras for dependencies
- Review media content for promotional material
- Use status filter to include disabled products
- Consider reservation limits when planning bookings
"""
        else:
            response_text = f"""❌ **Generic Product Details Retrieval Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify product IDs exist in the system
- Check hotel and room ID formats
- Ensure status parameter is valid
- Review authentication credentials
- Verify API endpoint availability
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving generic product details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
