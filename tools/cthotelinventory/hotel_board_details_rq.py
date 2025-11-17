"""
HotelBoardDetailsRQ - Get Hotel Board Details Tool

This tool retrieves detailed information about hotel board types (meal plans)
available in the Neobookings system.
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
HOTEL_BOARD_DETAILS_RQ_TOOL = Tool(
    name="hotel_board_details_rq",
    description="""
    Retrieve detailed information about hotel board types (meal plans) from specific hotels.
    
    This tool provides comprehensive information about board options including:
    - Board type details (ID, name, description)
    - Board type classifications (room only, breakfast, half board, etc.)
    - Media and images associated with board types
    - Filtering capabilities by hotel and board
    
    Parameters:
    - hotel_ids (optional): List of hotel identifiers to filter by
    - board_ids (optional): List of board identifiers to filter by
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - Detailed board information for each hotel
    - Board type classifications and descriptions
    - Associated media content
    
    Example usage:
    "Get board details for hotel 'HTL123'"
    "Show me meal plans for hotels 'HTL123' and 'HTL456'"
    "Retrieve all available board types"
    "Get details for board type 'BRD789'"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "hotel_ids": {
                "type": "array",
                "description": "List of hotel identifiers to filter by",
                "items": {
                    "type": "string",
                    "description": "Hotel identifier"
                },
                "maxItems": 50
            },
            "board_ids": {
                "type": "array", 
                "description": "List of board identifiers to filter by",
                "items": {
                    "type": "string",
                    "description": "Board identifier"
                },
                "maxItems": 50
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": [],
        "additionalProperties": False
    }
)


class HotelBoardDetailsRQHandler:
    """Handler for the HotelBoardDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="hotel_board_details_rq")
    
    def _format_board_type(self, board_type: Dict[str, Any]) -> Dict[str, Any]:
        """Format board type information for readable output."""
        return {
            "code": board_type.get("Code"),
            "name": board_type.get("Name"),
            "description": board_type.get("Description")
        }
    
    def _format_media(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format media information for readable output."""
        formatted_media = []
        for media in media_list:
            formatted_media.append({
                "type": media.get("MediaType"),
                "caption": media.get("Caption"),
                "url": media.get("Url"),
                "is_main": media.get("Main", False),
                "order": media.get("Order", 0)
            })
        return formatted_media
    
    def _format_board_detail(self, board_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Format board detail information for readable output."""
        formatted = {
            "hotel_id": board_detail.get("HotelId"),
            "board_id": board_detail.get("HotelBoardId"),
            "board_name": board_detail.get("HotelBoardName"),
            "board_description": board_detail.get("HotelBoardDescription")
        }
        
        # Format board type
        board_type = board_detail.get("HotelBoardType", {})
        if board_type:
            formatted["board_type"] = self._format_board_type(board_type)
        
        # Format media
        media_list = board_detail.get("Media", [])
        if media_list:
            formatted["media"] = self._format_media(media_list)
        
        return formatted
    
    def _group_boards_by_hotel(self, board_details: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group board details by hotel for better organization."""
        grouped = {}
        
        for board in board_details:
            hotel_id = board["hotel_id"]
            
            if hotel_id not in grouped:
                grouped[hotel_id] = {
                    "hotel_id": hotel_id,
                    "boards": []
                }
            
            grouped[hotel_id]["boards"].append(board)
        
        return grouped
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the hotel board details request.
        
        Args:
            arguments: Tool arguments containing filters and language
            
        Returns:
            Dictionary containing the hotel board details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            hotel_ids = arguments.get("hotel_ids", [])
            board_ids = arguments.get("board_ids", [])
            language = arguments.get("language", "es")
            
            # Validate and sanitize hotel IDs
            sanitized_hotel_ids = []
            if hotel_ids:
                if not isinstance(hotel_ids, list):
                    raise ValidationError("hotel_ids must be a list")
                
                for hotel_id in hotel_ids:
                    if not isinstance(hotel_id, str) or not hotel_id.strip():
                        raise ValidationError(f"Invalid hotel ID: {hotel_id}")
                    sanitized_hotel_ids.append(sanitize_string(hotel_id.strip()))
            
            # Validate and sanitize board IDs
            sanitized_board_ids = []
            if board_ids:
                if not isinstance(board_ids, list):
                    raise ValidationError("board_ids must be a list")
                
                for board_id in board_ids:
                    if not isinstance(board_id, str) or not board_id.strip():
                        raise ValidationError(f"Invalid board ID: {board_id}")
                    sanitized_board_ids.append(sanitize_string(board_id.strip()))
            
            self.logger.info(
                "Retrieving hotel board details",
                hotel_count=len(sanitized_hotel_ids),
                board_count=len(sanitized_board_ids),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
            if sanitized_hotel_ids:
                request_payload["HotelId"] = sanitized_hotel_ids
            
            if sanitized_board_ids:
                request_payload["BoardId"] = sanitized_board_ids
            
            # Add FilterBy if needed (empty for now, can be extended)
            request_payload["FilterBy"] = {}
            
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
                
                # Make the hotel board details request
                response = await client.post("/HotelBoardDetailsRQ", request_payload)
            
            # Extract board details from response
            board_details_raw = response.get("HotelBoardDetail", [])
            
            # Format board details
            formatted_boards = []
            for board_detail in board_details_raw:
                formatted_boards.append(self._format_board_detail(board_detail))
            
            # Group boards by hotel
            grouped_by_hotel = self._group_boards_by_hotel(formatted_boards)
            
            # Log successful operation
            self.logger.info(
                "Hotel board details retrieved successfully",
                board_count=len(formatted_boards),
                hotel_count=len(grouped_by_hotel),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "board_details": formatted_boards,
                "grouped_by_hotel": grouped_by_hotel,
                "filters_applied": {
                    "hotel_ids": sanitized_hotel_ids,
                    "board_ids": sanitized_board_ids
                },
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_boards": len(formatted_boards),
                    "hotels_with_boards": len(grouped_by_hotel),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved {len(formatted_boards)} board details from {len(grouped_by_hotel)} hotels"
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
handler = HotelBoardDetailsRQHandler()


async def call_hotel_board_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the HotelBoardDetailsRQ endpoint.
    
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
            filters = data["filters_applied"]
            
            response_text = f"""🍽️ **Hotel Board Details Retrieved**

✅ **Summary:**
- **Total Boards**: {summary['total_boards']}
- **Hotels with Boards**: {summary['hotels_with_boards']}
- **Language**: {summary['language'].upper()}

📋 **Filters Applied:**
- **Hotel IDs**: {', '.join(filters['hotel_ids']) if filters['hotel_ids'] else 'All hotels'}
- **Board IDs**: {', '.join(filters['board_ids']) if filters['board_ids'] else 'All boards'}

"""
            
            # Display board details grouped by hotel
            grouped_data = data["grouped_by_hotel"]
            if grouped_data:
                response_text += f"""
{'='*70}
🏨 **BOARD DETAILS BY HOTEL**
{'='*70}
"""
                
                for hotel_id, hotel_data in grouped_data.items():
                    boards = hotel_data["boards"]
                    
                    response_text += f"""
🏨 **Hotel ID: {hotel_id}**
   **Available Boards**: {len(boards)} board type(s)

"""
                    
                    for i, board in enumerate(boards, 1):
                        response_text += f"""   {i:2d}. 🍽️ **{board['board_name']}**
      **Board ID**: {board['board_id']}
      **Description**: {board.get('board_description', 'N/A')}
"""
                        
                        # Display board type information
                        board_type = board.get('board_type', {})
                        if board_type:
                            response_text += f"""      **Type**: {board_type.get('name', 'N/A')} ({board_type.get('code', 'N/A')})
"""
                            if board_type.get('description'):
                                response_text += f"""      **Type Description**: {board_type['description']}
"""
                        
                        # Display media information
                        media = board.get('media', [])
                        if media:
                            response_text += f"""      **Media**: {len(media)} item(s)
"""
                            for j, media_item in enumerate(media[:3], 1):  # Show first 3 media items
                                response_text += f"""        {j}. {media_item['type'].title()}: {media_item.get('caption', 'No caption')}
"""
                                if media_item.get('is_main'):
                                    response_text += f"""           🌟 Main image
"""
                    
                    response_text += "\n"
            
            # Display all board details in list format
            board_details = data["board_details"]
            if board_details:
                response_text += f"""
{'='*70}
📋 **ALL BOARD DETAILS**
{'='*70}
"""
                for i, board in enumerate(board_details, 1):
                    response_text += f"""
{i:2d}. 🍽️ **{board['board_name']}**
    **Hotel ID**: {board['hotel_id']}
    **Board ID**: {board['board_id']}
    **Description**: {board.get('board_description', 'N/A')}
"""
                    
                    board_type = board.get('board_type', {})
                    if board_type:
                        response_text += f"""    **Type**: {board_type.get('name', 'N/A')} ({board_type.get('code', 'N/A')})
"""
                    
                    media_count = len(board.get('media', []))
                    if media_count > 0:
                        response_text += f"""    **Media Items**: {media_count}
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Hotel Board Details**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the hotel IDs and board IDs exist and are accessible
- Check your authentication credentials
- Ensure you have permission to view these board details
- Verify the ID formats are correct
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving hotel board details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
