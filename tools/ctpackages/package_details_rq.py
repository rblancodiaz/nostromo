"""
PackageDetailsRQ - Package Details Tool

This tool retrieves detailed information about tourism packages in the Neobookings system.
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
PACKAGE_DETAILS_RQ_TOOL = Tool(
    name="package_details_rq",
    description="""
    Retrieve detailed information about tourism packages.
    
    This tool provides comprehensive details about tourism packages including
    package descriptions, inclusions, categories, associated hotels and rooms,
    board types, and extra services included in the packages.
    
    Parameters:
    - package_ids (optional): Specific package IDs to retrieve details for
    - hotel_ids (optional): Hotel IDs to get packages for
    - hotel_room_ids (optional): Room IDs to get packages for
    - status (optional): Package status filter (enabled/disabled/all)
    - language (optional): Language for the request
    
    Returns:
    - Detailed package information
    - Package descriptions and categories
    - Included hotel rooms and services
    - Board types and extra services
    - Package status and configuration
    - Media and promotional content
    
    Example usage:
    "Get details for package PKG123"
    "Show all packages for hotel HTL456"
    "List active vacation packages with descriptions"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "package_ids": {
                "type": "array",
                "description": "Specific package IDs to retrieve details for",
                "items": {"type": "string"},
                "maxItems": 100
            },
            "hotel_ids": {
                "type": "array",
                "description": "Hotel IDs to get packages for",
                "items": {"type": "string"},
                "maxItems": 100
            },
            "hotel_room_ids": {
                "type": "array",
                "description": "Room IDs to get packages for",
                "items": {"type": "string"},
                "maxItems": 100
            },
            "status": {
                "type": "string",
                "description": "Package status filter",
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


class PackageDetailsRQHandler:
    """Handler for the PackageDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="package_details_rq")
    
    def _validate_string_list(self, values: List[str], field_name: str, max_items: int = 100) -> List[str]:
        """Validate and sanitize a list of strings."""
        if not values:
            return []
        
        if len(values) > max_items:
            raise ValidationError(f"{field_name}: maximum {max_items} items allowed")
        
        validated_values = []
        for i, value in enumerate(values):
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{field_name} {i+1}: must be a non-empty string")
            
            sanitized_value = sanitize_string(value.strip())
            if not sanitized_value:
                raise ValidationError(f"{field_name} {i+1}: invalid format after sanitization")
            
            validated_values.append(sanitized_value)
        
        return validated_values
    
    def _format_package_details(self, packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format package details information for readable output."""
        formatted_packages = []
        
        for package in packages:
            formatted_package = {
                "package_id": package.get("PackageId"),
                "hotel_id": package.get("HotelId"),
                "hotel_hash": package.get("HotelHash"),
                "package_name": package.get("PackageName"),
                "package_description": package.get("PackageDescription"),
                "status": package.get("Status"),
                "order": package.get("Order"),
                "hotel_room_ids": package.get("HotelRoomId", []),
                "hotel_board_ids": package.get("HotelBoardId", []),
                "hotel_room_extra_ids": package.get("HotelRoomExtraId", []),
                "categories": [],
                "media": []
            }
            
            # Format categories
            categories = package.get("PackageCategory", [])
            for category in categories:
                formatted_package["categories"].append({
                    "code": category.get("Code"),
                    "name": category.get("Name")
                })
            
            # Format media
            media = package.get("Media", [])
            for media_item in media:
                formatted_package["media"].append({
                    "media_type": media_item.get("MediaType"),
                    "caption": media_item.get("Caption"),
                    "url": media_item.get("Url"),
                    "main": media_item.get("Main", False),
                    "order": media_item.get("Order")
                })
            
            # Calculate inclusions summary
            formatted_package["inclusions_summary"] = {
                "total_rooms": len(formatted_package["hotel_room_ids"]),
                "total_boards": len(formatted_package["hotel_board_ids"]),
                "total_extras": len(formatted_package["hotel_room_extra_ids"]),
                "total_categories": len(formatted_package["categories"]),
                "has_media": len(formatted_package["media"]) > 0
            }
            
            formatted_packages.append(formatted_package)
        
        return formatted_packages
    
    def _analyze_package_data(self, packages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze package data to provide insights."""
        if not packages:
            return {
                "total_packages": 0,
                "enabled_packages": 0,
                "disabled_packages": 0,
                "packages_with_media": 0,
                "most_common_categories": [],
                "average_inclusions": 0,
                "hotels_with_packages": 0
            }
        
        total_packages = len(packages)
        enabled_packages = 0
        disabled_packages = 0
        packages_with_media = 0
        category_counts = {}
        total_inclusions = 0
        hotels = set()
        
        for package in packages:
            # Count status
            status = package.get("status", "").lower()
            if status == "enabled":
                enabled_packages += 1
            elif status == "disabled":
                disabled_packages += 1
            
            # Count media
            if package.get("media"):
                packages_with_media += 1
            
            # Count categories
            for category in package.get("categories", []):
                cat_name = category.get("name", "Unknown")
                category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
            
            # Count inclusions
            inclusions = package.get("inclusions_summary", {})
            total_inclusions += (
                inclusions.get("total_rooms", 0) +
                inclusions.get("total_boards", 0) +
                inclusions.get("total_extras", 0)
            )
            
            # Count unique hotels
            if package.get("hotel_id"):
                hotels.add(package["hotel_id"])
        
        # Get most common categories
        most_common_categories = sorted(
            category_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Calculate average inclusions
        average_inclusions = total_inclusions / total_packages if total_packages > 0 else 0
        
        return {
            "total_packages": total_packages,
            "enabled_packages": enabled_packages,
            "disabled_packages": disabled_packages,
            "packages_with_media": packages_with_media,
            "most_common_categories": most_common_categories,
            "average_inclusions": round(average_inclusions, 1),
            "hotels_with_packages": len(hotels),
            "media_percentage": round((packages_with_media / total_packages * 100), 1) if total_packages > 0 else 0
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the package details request.
        
        Args:
            arguments: Tool arguments containing package criteria
            
        Returns:
            Dictionary containing the package details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            package_ids = arguments.get("package_ids", [])
            hotel_ids = arguments.get("hotel_ids", [])
            hotel_room_ids = arguments.get("hotel_room_ids", [])
            status = arguments.get("status", "enabled")
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_package_ids = self._validate_string_list(package_ids, "Package ID", 100)
            validated_hotel_ids = self._validate_string_list(hotel_ids, "Hotel ID", 100)
            validated_hotel_room_ids = self._validate_string_list(hotel_room_ids, "Hotel Room ID", 100)
            
            if status not in ["enabled", "disabled", "all"]:
                raise ValidationError("Status must be 'enabled', 'disabled', or 'all'")
            
            self.logger.info(
                "Retrieving package details",
                package_ids=len(validated_package_ids),
                hotel_ids=len(validated_hotel_ids),
                hotel_room_ids=len(validated_hotel_room_ids),
                status=status,
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"]
            }
            
            # Add optional parameters
            if validated_package_ids:
                request_payload["PackageId"] = validated_package_ids
            if validated_hotel_ids:
                request_payload["HotelId"] = validated_hotel_ids
            if validated_hotel_room_ids:
                request_payload["HotelRoomId"] = validated_hotel_room_ids
            if status:
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
                
                # Make the package details request
                response = await client.post("/PackageDetailsRQ", request_payload)
            
            # Extract data from response
            package_details = response.get("PackageDetail", [])
            api_response = response.get("Response", {})
            
            # Format results
            formatted_packages = self._format_package_details(package_details)
            analysis = self._analyze_package_data(formatted_packages)
            
            # Log successful operation
            self.logger.info(
                "Package details retrieved",
                total_packages=analysis["total_packages"],
                enabled_packages=analysis["enabled_packages"],
                disabled_packages=analysis["disabled_packages"],
                hotels_with_packages=analysis["hotels_with_packages"],
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "package_ids": validated_package_ids,
                    "hotel_ids": validated_hotel_ids,
                    "hotel_room_ids": validated_hotel_room_ids,
                    "status": status
                },
                "package_details": formatted_packages,
                "analysis": analysis,
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved details for {analysis['total_packages']} package(s)"
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
handler = PackageDetailsRQHandler()


async def call_package_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the PackageDetailsRQ endpoint.
    
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
            packages = data["package_details"]
            analysis = data["analysis"]
            search_criteria = data["search_criteria"]
            
            response_text = f"""📦 **Package Details**

📊 **Search Summary:**
- **Total Packages Found**: {analysis['total_packages']}
- **Enabled Packages**: {analysis['enabled_packages']}
- **Disabled Packages**: {analysis['disabled_packages']}
- **Hotels with Packages**: {analysis['hotels_with_packages']}
- **Packages with Media**: {analysis['packages_with_media']} ({analysis['media_percentage']}%)
- **Average Inclusions per Package**: {analysis['average_inclusions']}

"""
            
            # Most common categories
            if analysis['most_common_categories']:
                response_text += f"""🏷️ **Most Common Categories:**
"""
                for i, (category, count) in enumerate(analysis['most_common_categories'], 1):
                    response_text += f"{i}. {category}: {count} package(s)\n"
                response_text += "\n"
            
            if packages:
                response_text += f"""📋 **Package Details ({len(packages)} package(s)):**
{'='*80}
"""
                
                for i, package in enumerate(packages, 1):
                    inclusions = package.get("inclusions_summary", {})
                    
                    response_text += f"""
📦 **Package #{i}**
{'-'*60}

🏷️ **Basic Information:**
- **Package ID**: {package['package_id']}
- **Hotel ID**: {package['hotel_id']}
- **Name**: {package['package_name']}
- **Status**: {package['status']}
- **Order**: {package['order']}

📝 **Description:**
{package.get('package_description', 'No description available')}

📊 **Inclusions Summary:**
- **Hotel Rooms**: {inclusions['total_rooms']} room type(s)
- **Board Options**: {inclusions['total_boards']} board type(s)
- **Extra Services**: {inclusions['total_extras']} extra service(s)
- **Categories**: {inclusions['total_categories']} categor(y/ies)
- **Media Content**: {'Yes' if inclusions['has_media'] else 'No'}
"""
                    
                    # Room IDs
                    if package.get("hotel_room_ids"):
                        response_text += f"""
🏨 **Included Room Types:**
{', '.join(package['hotel_room_ids'])}
"""
                    
                    # Board IDs
                    if package.get("hotel_board_ids"):
                        response_text += f"""
🍽️ **Included Board Types:**
{', '.join(package['hotel_board_ids'])}
"""
                    
                    # Extra services
                    if package.get("hotel_room_extra_ids"):
                        response_text += f"""
🛍️ **Included Extra Services:**
{', '.join(package['hotel_room_extra_ids'])}
"""
                    
                    # Categories
                    categories = package.get("categories", [])
                    if categories:
                        response_text += f"""
🏷️ **Package Categories:**
"""
                        for category in categories:
                            response_text += f"- {category.get('name', 'N/A')} ({category.get('code', 'N/A')})\n"
                    
                    # Media content
                    media = package.get("media", [])
                    if media:
                        response_text += f"""
📸 **Media Content ({len(media)} item(s)):**
"""
                        for j, media_item in enumerate(media[:5], 1):  # Show first 5 media items
                            main_indicator = " ⭐" if media_item.get("main") else ""
                            response_text += f"""
{j}. **{media_item.get('media_type', 'Unknown')}**{main_indicator}
   - Caption: {media_item.get('caption', 'N/A')}
   - URL: {media_item.get('url', 'N/A')}
   - Order: {media_item.get('order', 'N/A')}
"""
                        if len(media) > 5:
                            response_text += f"   ... and {len(media) - 5} more media item(s)\n"
                    
                    response_text += "\n"
            
            else:
                response_text += """❌ **No Package Details Found**

No packages were found matching the specified criteria.

**Possible reasons:**
- Package IDs do not exist
- No packages available for the specified hotels/rooms
- Packages are disabled and status filter excludes them
- No packages configured in the system
- Insufficient permissions to view packages
"""
            
            response_text += f"""

🔍 **Search Criteria Used:**
- **Package IDs**: {len(search_criteria['package_ids'])} specified
- **Hotel IDs**: {len(search_criteria['hotel_ids'])} specified
- **Room IDs**: {len(search_criteria['hotel_room_ids'])} specified
- **Status Filter**: {search_criteria['status']}

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use package details for sales and marketing materials
- Review inclusions to understand package value
- Check categories for proper package classification
- Use media content for promotional displays
- Verify room and board combinations for availability
- Monitor package status for active offerings
- Use for package comparison and recommendation systems
"""
                
        else:
            response_text = f"""❌ **Package Details Retrieval Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify package IDs are correct and exist
- Check that hotel IDs are valid
- Ensure room IDs are properly formatted
- Verify status filter is appropriate
- Check authentication credentials
- Ensure packages are properly configured
- Review API response for specific error codes
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving package details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
