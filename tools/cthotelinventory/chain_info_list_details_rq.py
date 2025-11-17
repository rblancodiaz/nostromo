"""
ChainInfoListDetailsRQ - Get Chain Information List Details Tool

This tool retrieves detailed information about hotel chains and their associated hotels
in the Neobookings system.
"""

import json
from typing import Dict, Any, List
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
CHAIN_INFO_LIST_DETAILS_RQ_TOOL = Tool(
    name="chain_info_list_details_rq",
    description="""
    Retrieve detailed information about hotel chains and their associated hotels.
    
    This tool provides comprehensive information about hotel chains including:
    - Chain details (ID, name)
    - Hotels associated with each chain
    - Complete chain and hotel listings
    
    Parameters:
    - language (optional): Language code for the request (default: "es")
    
    Returns:
    - List of chain information details
    - List of hotel-chain associations
    - Complete chain and hotel mappings
    
    Example usage:
    "Get information about all hotel chains"
    "Show me the list of hotels by chain"
    "Retrieve chain details and their hotels"
    """,
    inputSchema={
        "type": "object",
        "properties": {
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


class ChainInfoListDetailsRQHandler:
    """Handler for the ChainInfoListDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="chain_info_list_details_rq")
    
    def _format_chain_info(self, chain_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format chain information for readable output."""
        return {
            "chain_id": chain_info.get("ChainId"),
            "chain_name": chain_info.get("ChainName")
        }
    
    def _format_hotel_chain_info(self, hotel_chain_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format hotel chain association information for readable output."""
        return {
            "chain_id": hotel_chain_info.get("ChainId"),
            "hotel_id": hotel_chain_info.get("HotelId"),
            "hotel_name": hotel_chain_info.get("HotelName")
        }
    
    def _group_hotels_by_chain(self, chains: List[Dict[str, Any]], hotel_chains: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group hotels by their chain for better organization."""
        chain_map = {chain["chain_id"]: chain for chain in chains}
        grouped = {}
        
        for hotel_chain in hotel_chains:
            chain_id = hotel_chain["chain_id"]
            
            if chain_id not in grouped:
                chain_info = chain_map.get(chain_id, {"chain_name": "Unknown Chain"})
                grouped[chain_id] = {
                    "chain_info": chain_info,
                    "hotels": []
                }
            
            grouped[chain_id]["hotels"].append({
                "hotel_id": hotel_chain["hotel_id"],
                "hotel_name": hotel_chain["hotel_name"]
            })
        
        return grouped
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the chain info list details request.
        
        Args:
            arguments: Tool arguments containing language
            
        Returns:
            Dictionary containing the chain information details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            language = arguments.get("language", "es")
            
            self.logger.info(
                "Retrieving chain information list details",
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = request_data.copy()
            
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
                
                # Make the chain info list details request
                response = await client.post("/ChainInfoListDetailsRQ", request_payload)
            
            # Extract chain information from response
            chain_info_list_raw = response.get("ChainInfoListDetail", [])
            hotel_chain_info_list_raw = response.get("HotelChainInfoListDetail", [])
            
            # Format chain information
            formatted_chains = []
            for chain_info in chain_info_list_raw:
                formatted_chains.append(self._format_chain_info(chain_info))
            
            # Format hotel chain associations
            formatted_hotel_chains = []
            for hotel_chain_info in hotel_chain_info_list_raw:
                formatted_hotel_chains.append(self._format_hotel_chain_info(hotel_chain_info))
            
            # Group hotels by chain
            grouped_by_chain = self._group_hotels_by_chain(formatted_chains, formatted_hotel_chains)
            
            # Log successful operation
            self.logger.info(
                "Chain information retrieved successfully",
                chain_count=len(formatted_chains),
                hotel_count=len(formatted_hotel_chains),
                grouped_chains=len(grouped_by_chain),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "chains": formatted_chains,
                "hotel_chain_associations": formatted_hotel_chains,
                "grouped_by_chain": grouped_by_chain,
                "request_metadata": request_data["Request"],
                "api_response": response.get("Response", {}),
                "summary": {
                    "total_chains": len(formatted_chains),
                    "total_hotels": len(formatted_hotel_chains),
                    "chains_with_hotels": len(grouped_by_chain),
                    "language": language
                }
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Retrieved {len(formatted_chains)} chains and {len(formatted_hotel_chains)} hotel associations"
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
handler = ChainInfoListDetailsRQHandler()


async def call_chain_info_list_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    MCP tool handler for the ChainInfoListDetailsRQ endpoint.
    
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
            
            response_text = f"""🏨 **Hotel Chain Information Retrieved**

✅ **Summary:**
- **Total Chains**: {summary['total_chains']}
- **Total Hotels**: {summary['total_hotels']}
- **Chains with Hotels**: {summary['chains_with_hotels']}
- **Language**: {summary['language'].upper()}

"""
            
            # Display grouped information by chain
            grouped_data = data["grouped_by_chain"]
            if grouped_data:
                response_text += f"""
{'='*60}
🏨 **CHAINS AND THEIR HOTELS**
{'='*60}
"""
                
                for chain_id, chain_data in grouped_data.items():
                    chain_info = chain_data["chain_info"]
                    hotels = chain_data["hotels"]
                    
                    response_text += f"""
🔗 **Chain: {chain_info.get('chain_name', 'Unknown')}**
   **Chain ID**: {chain_id}
   **Hotels**: {len(hotels)} hotel(s)

"""
                    
                    if hotels:
                        for i, hotel in enumerate(hotels, 1):
                            response_text += f"""   {i:2d}. 🏪 **{hotel['hotel_name']}** (ID: {hotel['hotel_id']})
"""
                    
                    response_text += "\n"
            
            # Display all chains list
            chains = data["chains"]
            if chains:
                response_text += f"""
{'='*60}
📋 **ALL CHAINS LIST**
{'='*60}
"""
                for i, chain in enumerate(chains, 1):
                    response_text += f"""
{i:2d}. 🏨 **{chain['chain_name']}**
    **Chain ID**: {chain['chain_id']}
"""
            
            # Display all hotel associations
            hotel_associations = data["hotel_chain_associations"]
            if hotel_associations:
                response_text += f"""

{'='*60}
🏪 **ALL HOTEL-CHAIN ASSOCIATIONS**
{'='*60}
"""
                for i, association in enumerate(hotel_associations, 1):
                    response_text += f"""
{i:2d}. **{association['hotel_name']}**
    **Hotel ID**: {association['hotel_id']}
    **Chain ID**: {association['chain_id']}
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms
"""
        else:
            response_text = f"""❌ **Failed to Retrieve Chain Information**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Check your authentication credentials
- Verify network connectivity
- Ensure the API service is available
- Contact support if the issue persists
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving chain information:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
