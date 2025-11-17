"""
BasketAddProductRQ - Add Product to Basket Tool

This tool handles adding products (hotel rooms, packages, generic products, extras) 
to an existing shopping basket in the Neobookings system.
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
    validate_required_fields,
    sanitize_string
)

# Tool definition
BASKET_ADD_PRODUCT_RQ_TOOL = Tool(
    name="basket_add_product_rq",
    description="""
    Add products to an existing shopping basket in the Neobookings system.
    
    This tool allows adding various types of products to a basket:
    - Hotel room availability results
    - Hotel room extras
    - Package availability results  
    - Package extras
    - Generic product availability results
    - Generic product extras
    
    Parameters:
    - basket_id (required): Identifier of the basket to add products to
    - hotel_room_availability_ids (optional): List of hotel room availability IDs
    - hotel_room_extra_availability_ids (optional): List of hotel room extra availability IDs
    - package_availability_ids (optional): List of package availability IDs
    - package_extra_availability_ids (optional): List of package extra availability IDs
    - generic_product_availabilities (optional): List of generic product availability objects
    - generic_product_extra_availabilities (optional): List of generic product extra availability objects
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Updated basket details
    - Added product information
    - Total amounts and pricing
    
    Example usage:
    "Add hotel room availability ID 'ROOM123' to basket 'BASKET456'"
    "Add package 'PKG789' and extra 'EXT101' to my basket"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "basket_id": {
                "type": "string",
                "description": "Identifier of the basket to add products to",
                "minLength": 1
            },
            "hotel_room_availability_ids": {
                "type": "array",
                "description": "List of hotel room availability identifiers",
                "items": {
                    "type": "string",
                    "minLength": 1
                }
            },
            "hotel_room_extra_availability_ids": {
                "type": "array", 
                "description": "List of hotel room extra availability identifiers",
                "items": {
                    "type": "string",
                    "minLength": 1
                }
            },
            "package_availability_ids": {
                "type": "array",
                "description": "List of package availability identifiers", 
                "items": {
                    "type": "string",
                    "minLength": 1
                }
            },
            "package_extra_availability_ids": {
                "type": "array",
                "description": "List of package extra availability identifiers",
                "items": {
                    "type": "string", 
                    "minLength": 1
                }
            },
            "generic_product_availabilities": {
                "type": "array",
                "description": "List of generic product availability objects",
                "items": {
                    "type": "object",
                    "properties": {
                        "availability_id": {
                            "type": "string",
                            "description": "Availability identifier",
                            "minLength": 1
                        },
                        "quantity": {
                            "type": "number",
                            "description": "Quantity of products to add",
                            "minimum": 1
                        }
                    },
                    "required": ["availability_id", "quantity"],
                    "additionalProperties": False
                }
            },
            "generic_product_extra_availabilities": {
                "type": "array", 
                "description": "List of generic product extra availability objects",
                "items": {
                    "type": "object",
                    "properties": {
                        "availability_id": {
                            "type": "string",
                            "description": "Availability identifier",
                            "minLength": 1
                        },
                        "quantity": {
                            "type": "number",
                            "description": "Quantity of products to add", 
                            "minimum": 1
                        }
                    },
                    "required": ["availability_id", "quantity"],
                    "additionalProperties": False
                }
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


class BasketAddProductRQHandler:
    """Handler for the BasketAddProductRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="basket_add_product_rq")
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the add product to basket request.
        
        Args:
            arguments: Tool arguments containing basket ID and product details
            
        Returns:
            Dictionary containing the updated basket details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            basket_id = sanitize_string(arguments["basket_id"])
            language = arguments.get("language", "es")
            
            # Validate that at least one product type is provided
            product_fields = [
                "hotel_room_availability_ids",
                "hotel_room_extra_availability_ids", 
                "package_availability_ids",
                "package_extra_availability_ids",
                "generic_product_availabilities",
                "generic_product_extra_availabilities"
            ]
            
            has_products = any(arguments.get(field) for field in product_fields)
            if not has_products:
                raise ValidationError(
                    "At least one product type must be specified to add to the basket",
                    error_code="NO_PRODUCTS_SPECIFIED"
                )
            
            self.logger.info(
                "Adding products to basket",
                basket_id=basket_id,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                **request_data,
                "BasketId": basket_id
            }
            
            # Add product lists if provided
            if arguments.get("hotel_room_availability_ids"):
                request_payload["HotelRoomAvailabilityId"] = arguments["hotel_room_availability_ids"]
                
            if arguments.get("hotel_room_extra_availability_ids"):
                request_payload["HotelRoomExtraAvailabilityId"] = arguments["hotel_room_extra_availability_ids"]
                
            if arguments.get("package_availability_ids"):
                request_payload["PackageAvailabilityId"] = arguments["package_availability_ids"]
                
            if arguments.get("package_extra_availability_ids"):
                request_payload["PackageExtraAvailabilityId"] = arguments["package_extra_availability_ids"]
                
            if arguments.get("generic_product_availabilities"):
                generic_products = []
                for product in arguments["generic_product_availabilities"]:
                    generic_products.append({
                        "AvailabilityId": product["availability_id"],
                        "Quantity": product["quantity"]
                    })
                request_payload["GenericProductAvailability"] = generic_products
                
            if arguments.get("generic_product_extra_availabilities"):
                generic_extras = []
                for extra in arguments["generic_product_extra_availabilities"]:
                    generic_extras.append({
                        "AvailabilityId": extra["availability_id"],
                        "Quantity": extra["quantity"]
                    })
                request_payload["GenericProductExtraAvailability"] = generic_extras
            
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
                
                # Make the basket add product request
                response = await client.post("/BasketAddProductRQ", request_payload)
            
            # Extract basket details from response
            basket_detail = response.get("BasketDetail", {})
            
            # Log successful operation
            self.logger.info(
                "Products added to basket successfully",
                basket_id=basket_id,
                basket_status=basket_detail.get("BasketStatus"),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "basket_id": basket_id,
                "basket_detail": basket_detail,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "products_added": {
                    "hotel_rooms": len(arguments.get("hotel_room_availability_ids", [])),
                    "hotel_room_extras": len(arguments.get("hotel_room_extra_availability_ids", [])),
                    "packages": len(arguments.get("package_availability_ids", [])),
                    "package_extras": len(arguments.get("package_extra_availability_ids", [])),
                    "generic_products": len(arguments.get("generic_product_availabilities", [])),
                    "generic_product_extras": len(arguments.get("generic_product_extra_availabilities", []))
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message="Products successfully added to basket"
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
handler = BasketAddProductRQHandler()


async def call_basket_add_product_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the BasketAddProductRQ endpoint.
    
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
            products_added = data["products_added"]
            
            # Count total products added
            total_products = sum(products_added.values())
            
            response_text = f"""🛒 **Products Added to Basket Successfully**

✅ **Basket Information:**
- **Basket ID**: {data['basket_id']}
- **Status**: {basket_detail.get('BasketStatus', 'Unknown')}
- **Budget ID**: {basket_detail.get('BudgetId', 'Not assigned')}
- **Order ID**: {basket_detail.get('OrderId', 'Not assigned')}

📦 **Products Added Summary** (Total: {total_products}):
"""
            
            # Add details for each product type
            if products_added["hotel_rooms"] > 0:
                response_text += f"- **Hotel Rooms**: {products_added['hotel_rooms']} items\n"
            if products_added["hotel_room_extras"] > 0:
                response_text += f"- **Hotel Room Extras**: {products_added['hotel_room_extras']} items\n"
            if products_added["packages"] > 0:
                response_text += f"- **Packages**: {products_added['packages']} items\n"
            if products_added["package_extras"] > 0:
                response_text += f"- **Package Extras**: {products_added['package_extras']} items\n"
            if products_added["generic_products"] > 0:
                response_text += f"- **Generic Products**: {products_added['generic_products']} items\n"
            if products_added["generic_product_extras"] > 0:
                response_text += f"- **Generic Product Extras**: {products_added['generic_product_extras']} items\n"
            
            response_text += f"""
🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}

💡 **Next Steps:**
- Use `basket_summary_rq` to view detailed basket contents
- Use `basket_lock_rq` to lock the basket before confirmation
- Use `basket_confirm_rq` to complete the reservation

⏱️ **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Add Products to Basket**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the basket ID exists and is accessible
- Check that the product availability IDs are valid
- Ensure the basket is not locked or already confirmed
- Verify your authentication credentials
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while adding products to the basket:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
