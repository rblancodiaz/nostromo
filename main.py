#!/usr/bin/env python3
"""
Neobookings MCP Server

A Model Context Protocol (MCP) server for the Neobookings hotel reservation API.
This server provides tools for managing hotel reservations through natural language interactions.

This comprehensive implementation includes 51 endpoints across 9 main categories:
- Authentication (1 endpoint)
- Basket Management (9 endpoints) 
- Budget Management (4 endpoints)
- Hotel & Inventory Management (15 endpoints)
- Generic Product Management (3 endpoints)
- Order Management (13 endpoints)
- Package Management (4 endpoints)
- Users and Rewards Management (1 endpoint)
- Geographic Search (1 endpoint)
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import ServerCapabilities, Tool
import mcp.types as types
from mcp.server.session import ServerSession
from mcp.server.stdio import stdio_server
import structlog

# Import configuration
from config import logger, NeobookingsConfig

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 1: AUTHENTICATION
# ==========================================
from tools.ctauthentication.authenticator_rq import AUTHENTICATOR_RQ_TOOL, call_authenticator_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 2: BASKET MANAGEMENT
# ==========================================
from tools.ctbasket.basket_add_product_rq import BASKET_ADD_PRODUCT_RQ_TOOL, call_basket_add_product_rq
from tools.ctbasket.basket_confirm_rq import BASKET_CONFIRM_RQ_TOOL, call_basket_confirm_rq
from tools.ctbasket.basket_create_rq import BASKET_CREATE_RQ_TOOL, call_basket_create_rq
from tools.ctbasket.basket_del_product_rq import BASKET_DEL_PRODUCT_RQ_TOOL, call_basket_del_product_rq
from tools.ctbasket.basket_delete_rq import BASKET_DELETE_RQ_TOOL, call_basket_delete_rq
from tools.ctbasket.basket_lock_rq import BASKET_LOCK_RQ_TOOL, call_basket_lock_rq
from tools.ctbasket.basket_properties_update_rq import BASKET_PROPERTIES_UPDATE_RQ_TOOL, call_basket_properties_update_rq
from tools.ctbasket.basket_summary_rq import BASKET_SUMMARY_RQ_TOOL, call_basket_summary_rq
from tools.ctbasket.basket_unlock_rq import BASKET_UNLOCK_RQ_TOOL, call_basket_unlock_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 3: BUDGET MANAGEMENT
# ==========================================
from tools.ctbudget.budget_delete_rq import BUDGET_DELETE_RQ_TOOL, call_budget_delete_rq
from tools.ctbudget.budget_details_rq import BUDGET_DETAILS_RQ_TOOL, call_budget_details_rq
from tools.ctbudget.budget_properties_update_rq import BUDGET_PROPERTIES_UPDATE_RQ_TOOL, call_budget_properties_update_rq
from tools.ctbudget.budget_search_rq import BUDGET_SEARCH_RQ_TOOL, call_budget_search_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 4: HOTEL & INVENTORY MANAGEMENT
# ==========================================
from tools.cthotelinventory.chain_info_list_details_rq import CHAIN_INFO_LIST_DETAILS_RQ_TOOL, call_chain_info_list_details_rq
from tools.cthotelinventory.hotel_board_details_rq import HOTEL_BOARD_DETAILS_RQ_TOOL, call_hotel_board_details_rq
from tools.cthotelinventory.hotel_calendar_avail_rq import HOTEL_CALENDAR_AVAIL_RQ_TOOL, call_hotel_calendar_avail_rq
from tools.cthotelinventory.hotel_details_rq import HOTEL_DETAILS_RQ_TOOL, call_hotel_details_rq
from tools.cthotelinventory.hotel_info_list_details_rq import HOTEL_INFO_LIST_DETAILS_RQ_TOOL, call_hotel_info_list_details_rq
from tools.cthotelinventory.hotel_inventory_read_rq import HOTEL_INVENTORY_READ_RQ_TOOL, call_hotel_inventory_read_rq
from tools.cthotelinventory.hotel_inventory_update_rq import HOTEL_INVENTORY_UPDATE_RQ_TOOL, call_hotel_inventory_update_rq
from tools.cthotelinventory.hotel_offer_details_rq import HOTEL_OFFER_DETAILS_RQ_TOOL, call_hotel_offer_details_rq
from tools.cthotelinventory.hotel_price_update_rq import HOTEL_PRICE_UPDATE_RQ_TOOL, call_hotel_price_update_rq
from tools.cthotelinventory.hotel_rate_details_rq import HOTEL_RATE_DETAILS_RQ_TOOL, call_hotel_rate_details_rq
from tools.cthotelinventory.hotel_room_avail_rq import HOTEL_ROOM_AVAIL_RQ_TOOL, call_hotel_room_avail_rq
from tools.cthotelinventory.hotel_room_details_rq import HOTEL_ROOM_DETAILS_RQ_TOOL, call_hotel_room_details_rq
from tools.cthotelinventory.hotel_room_extra_avail_rq import HOTEL_ROOM_EXTRA_AVAIL_RQ_TOOL, call_hotel_room_extra_avail_rq
from tools.cthotelinventory.hotel_room_extra_details_rq import HOTEL_ROOM_EXTRA_DETAILS_RQ_TOOL, call_hotel_room_extra_details_rq
from tools.cthotelinventory.hotel_search_rq import HOTEL_SEARCH_RQ_TOOL, call_hotel_search_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 5: GENERIC PRODUCT MANAGEMENT
# ==========================================
from tools.ctgenericproduct.generic_product_avail_rq import GENERIC_PRODUCT_AVAIL_RQ_TOOL, call_generic_product_avail_rq
from tools.ctgenericproduct.generic_product_details_rq import GENERIC_PRODUCT_DETAILS_RQ_TOOL, call_generic_product_details_rq
from tools.ctgenericproduct.generic_product_extra_avail_rq import GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL, call_generic_product_extra_avail_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 6: ORDER MANAGEMENT
# ==========================================
from tools.ctorders.order_cancel_rq import ORDER_CANCEL_RQ_TOOL, call_order_cancel_rq
from tools.ctorders.order_credit_card_rq import ORDER_CREDIT_CARD_RQ_TOOL, call_order_credit_card_rq
from tools.ctorders.order_data_modify_rq import ORDER_DATA_MODIFY_RQ_TOOL, call_order_data_modify_rq
from tools.ctorders.order_details_rq import ORDER_DETAILS_RQ_TOOL, call_order_details_rq
from tools.ctorders.order_event_notify_rq import ORDER_EVENT_NOTIFY_RQ_TOOL, call_order_event_notify_rq
from tools.ctorders.order_event_read_rq import ORDER_EVENT_READ_RQ_TOOL, call_order_event_read_rq
from tools.ctorders.order_event_search_rq import ORDER_EVENT_SEARCH_RQ_TOOL, call_order_event_search_rq
from tools.ctorders.order_notification_read_rq import ORDER_NOTIFICATION_READ_RQ_TOOL, call_order_notification_read_rq
from tools.ctorders.order_notification_remove_rq import ORDER_NOTIFICATION_REMOVE_RQ_TOOL, call_order_notification_remove_rq
from tools.ctorders.order_notification_rq import ORDER_NOTIFICATION_RQ_TOOL, call_order_notification_rq
from tools.ctorders.order_payment_create_rq import ORDER_PAYMENT_CREATE_RQ_TOOL, call_order_payment_create_rq
from tools.ctorders.order_put_rq import ORDER_PUT_RQ_TOOL, call_order_put_rq
from tools.ctorders.order_search_rq import ORDER_SEARCH_RQ_TOOL, call_order_search_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 7: PACKAGE MANAGEMENT
# ==========================================
from tools.ctpackages.package_avail_rq import PACKAGE_AVAIL_RQ_TOOL, call_package_avail_rq
from tools.ctpackages.package_calendar_avail_rq import PACKAGE_CALENDAR_AVAIL_RQ_TOOL, call_package_calendar_avail_rq
from tools.ctpackages.package_details_rq import PACKAGE_DETAILS_RQ_TOOL, call_package_details_rq
from tools.ctpackages.package_extra_avail_rq import PACKAGE_EXTRA_AVAIL_RQ_TOOL, call_package_extra_avail_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 8: USERS AND REWARDS MANAGEMENT
# ==========================================
from tools.ctusers.user_rewards_details_rq import USER_REWARDS_DETAILS_RQ_TOOL, call_user_rewards_details_rq

# ==========================================
# IMPORT ALL TOOLS FROM CATEGORY 9: GEOGRAPHIC SEARCH
# ==========================================
from tools.ctgeosearch.zone_search_rq import ZONE_SEARCH_RQ_TOOL, call_zone_search_rq

# Configure logging
logger = structlog.get_logger("mcp-neobookings")

# Server configuration
SERVER_NAME = "mcp-neobookings"
SERVER_VERSION = "1.0.0"

# ==========================================
# TOOL REGISTRY AND ROUTING CONFIGURATION
# ==========================================

# Define all available tools in organized categories
ALL_TOOLS = [
    # Category 1: Authentication (1 tool)
    AUTHENTICATOR_RQ_TOOL,
    
    # Category 2: Basket Management (9 tools)
    BASKET_ADD_PRODUCT_RQ_TOOL,
    BASKET_CONFIRM_RQ_TOOL,
    BASKET_CREATE_RQ_TOOL,
    BASKET_DEL_PRODUCT_RQ_TOOL,
    BASKET_DELETE_RQ_TOOL,
    BASKET_LOCK_RQ_TOOL,
    BASKET_PROPERTIES_UPDATE_RQ_TOOL,
    BASKET_SUMMARY_RQ_TOOL,
    BASKET_UNLOCK_RQ_TOOL,
    
    # Category 3: Budget Management (4 tools)
    BUDGET_DELETE_RQ_TOOL,
    BUDGET_DETAILS_RQ_TOOL,
    BUDGET_PROPERTIES_UPDATE_RQ_TOOL,
    BUDGET_SEARCH_RQ_TOOL,
    
    # Category 4: Hotel & Inventory Management (15 tools)
    CHAIN_INFO_LIST_DETAILS_RQ_TOOL,
    HOTEL_BOARD_DETAILS_RQ_TOOL,
    HOTEL_CALENDAR_AVAIL_RQ_TOOL,
    HOTEL_DETAILS_RQ_TOOL,
    HOTEL_INFO_LIST_DETAILS_RQ_TOOL,
    HOTEL_INVENTORY_READ_RQ_TOOL,
    HOTEL_INVENTORY_UPDATE_RQ_TOOL,
    HOTEL_OFFER_DETAILS_RQ_TOOL,
    HOTEL_PRICE_UPDATE_RQ_TOOL,
    HOTEL_RATE_DETAILS_RQ_TOOL,
    HOTEL_ROOM_AVAIL_RQ_TOOL,
    HOTEL_ROOM_DETAILS_RQ_TOOL,
    HOTEL_ROOM_EXTRA_AVAIL_RQ_TOOL,
    HOTEL_ROOM_EXTRA_DETAILS_RQ_TOOL,
    HOTEL_SEARCH_RQ_TOOL,
    
    # Category 5: Generic Product Management (3 tools)
    GENERIC_PRODUCT_AVAIL_RQ_TOOL,
    GENERIC_PRODUCT_DETAILS_RQ_TOOL,
    GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL,
    
    # Category 6: Order Management (13 tools)
    ORDER_CANCEL_RQ_TOOL,
    ORDER_CREDIT_CARD_RQ_TOOL,
    ORDER_DATA_MODIFY_RQ_TOOL,
    ORDER_DETAILS_RQ_TOOL,
    ORDER_EVENT_NOTIFY_RQ_TOOL,
    ORDER_EVENT_READ_RQ_TOOL,
    ORDER_EVENT_SEARCH_RQ_TOOL,
    ORDER_NOTIFICATION_READ_RQ_TOOL,
    ORDER_NOTIFICATION_REMOVE_RQ_TOOL,
    ORDER_NOTIFICATION_RQ_TOOL,
    ORDER_PAYMENT_CREATE_RQ_TOOL,
    ORDER_PUT_RQ_TOOL,
    ORDER_SEARCH_RQ_TOOL,
    
    # Category 7: Package Management (4 tools)
    PACKAGE_AVAIL_RQ_TOOL,
    PACKAGE_CALENDAR_AVAIL_RQ_TOOL,
    PACKAGE_DETAILS_RQ_TOOL,
    PACKAGE_EXTRA_AVAIL_RQ_TOOL,
    
    # Category 8: Users and Rewards Management (1 tool)
    USER_REWARDS_DETAILS_RQ_TOOL,
    
    # Category 9: Geographic Search (1 tool)
    ZONE_SEARCH_RQ_TOOL
]

# Define tool routing map for efficient dispatching
TOOL_HANDLERS = {
    # Category 1: Authentication
    "authenticator_rq": call_authenticator_rq,
    
    # Category 2: Basket Management
    "basket_add_product_rq": call_basket_add_product_rq,
    "basket_confirm_rq": call_basket_confirm_rq,
    "basket_create_rq": call_basket_create_rq,
    "basket_del_product_rq": call_basket_del_product_rq,
    "basket_delete_rq": call_basket_delete_rq,
    "basket_lock_rq": call_basket_lock_rq,
    "basket_properties_update_rq": call_basket_properties_update_rq,
    "basket_summary_rq": call_basket_summary_rq,
    "basket_unlock_rq": call_basket_unlock_rq,
    
    # Category 3: Budget Management
    "budget_delete_rq": call_budget_delete_rq,
    "budget_details_rq": call_budget_details_rq,
    "budget_properties_update_rq": call_budget_properties_update_rq,
    "budget_search_rq": call_budget_search_rq,
    
    # Category 4: Hotel & Inventory Management
    "chain_info_list_details_rq": call_chain_info_list_details_rq,
    "hotel_board_details_rq": call_hotel_board_details_rq,
    "hotel_calendar_avail_rq": call_hotel_calendar_avail_rq,
    "hotel_details_rq": call_hotel_details_rq,
    "hotel_info_list_details_rq": call_hotel_info_list_details_rq,
    "hotel_inventory_read_rq": call_hotel_inventory_read_rq,
    "hotel_inventory_update_rq": call_hotel_inventory_update_rq,
    "hotel_offer_details_rq": call_hotel_offer_details_rq,
    "hotel_price_update_rq": call_hotel_price_update_rq,
    "hotel_rate_details_rq": call_hotel_rate_details_rq,
    "hotel_room_avail_rq": call_hotel_room_avail_rq,
    "hotel_room_details_rq": call_hotel_room_details_rq,
    "hotel_room_extra_avail_rq": call_hotel_room_extra_avail_rq,
    "hotel_room_extra_details_rq": call_hotel_room_extra_details_rq,
    "hotel_search_rq": call_hotel_search_rq,
    
    # Category 5: Generic Product Management
    "generic_product_avail_rq": call_generic_product_avail_rq,
    "generic_product_details_rq": call_generic_product_details_rq,
    "generic_product_extra_avail_rq": call_generic_product_extra_avail_rq,
    
    # Category 6: Order Management
    "order_cancel_rq": call_order_cancel_rq,
    "order_credit_card_rq": call_order_credit_card_rq,
    "order_data_modify_rq": call_order_data_modify_rq,
    "order_details_rq": call_order_details_rq,
    "order_event_notify_rq": call_order_event_notify_rq,
    "order_event_read_rq": call_order_event_read_rq,
    "order_event_search_rq": call_order_event_search_rq,
    "order_notification_read_rq": call_order_notification_read_rq,
    "order_notification_remove_rq": call_order_notification_remove_rq,
    "order_notification_rq": call_order_notification_rq,
    "order_payment_create_rq": call_order_payment_create_rq,
    "order_put_rq": call_order_put_rq,
    "order_search_rq": call_order_search_rq,
    
    # Category 7: Package Management
    "package_avail_rq": call_package_avail_rq,
    "package_calendar_avail_rq": call_package_calendar_avail_rq,
    "package_details_rq": call_package_details_rq,
    "package_extra_avail_rq": call_package_extra_avail_rq,
    
    # Category 8: Users and Rewards Management
    "user_rewards_details_rq": call_user_rewards_details_rq,
    
    # Category 9: Geographic Search
    "zone_search_rq": call_zone_search_rq
}

# Tool categories for easy management and debugging
TOOL_CATEGORIES = {
    "authentication": [
        "authenticator_rq"
    ],
    "basket_management": [
        "basket_add_product_rq", "basket_confirm_rq", "basket_create_rq",
        "basket_del_product_rq", "basket_delete_rq", "basket_lock_rq",
        "basket_properties_update_rq", "basket_summary_rq", "basket_unlock_rq"
    ],
    "budget_management": [
        "budget_delete_rq", "budget_details_rq", "budget_properties_update_rq",
        "budget_search_rq"
    ],
    "hotel_inventory_management": [
        "chain_info_list_details_rq", "hotel_board_details_rq", "hotel_calendar_avail_rq",
        "hotel_details_rq", "hotel_info_list_details_rq", "hotel_inventory_read_rq",
        "hotel_inventory_update_rq", "hotel_offer_details_rq", "hotel_price_update_rq",
        "hotel_rate_details_rq", "hotel_room_avail_rq", "hotel_room_details_rq",
        "hotel_room_extra_avail_rq", "hotel_room_extra_details_rq", "hotel_search_rq"
    ],
    "generic_product_management": [
        "generic_product_avail_rq", "generic_product_details_rq", "generic_product_extra_avail_rq"
    ],
    "order_management": [
    "order_cancel_rq", "order_credit_card_rq", "order_data_modify_rq",
    "order_details_rq", "order_event_notify_rq", "order_event_read_rq",
    "order_event_search_rq", "order_notification_read_rq", "order_notification_remove_rq",
    "order_notification_rq", "order_payment_create_rq", "order_put_rq", "order_search_rq"
    ],
    "package_management": [
    "package_avail_rq", "package_calendar_avail_rq", "package_details_rq",
    "package_extra_avail_rq"
    ],
    "users_rewards_management": [
        "user_rewards_details_rq"
    ],
    "geographic_search": [
        "zone_search_rq"
    ]
}


def create_server() -> Server:
    """Create and configure the MCP server with all available tools."""
    server = Server(SERVER_NAME)
    
    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        """List all available tools organized by category."""
        
        logger.info(
            "Listing all available tools",
            total_tools=len(ALL_TOOLS),
            categories=len(TOOL_CATEGORIES),
            authentication_tools=len(TOOL_CATEGORIES["authentication"]),
            basket_tools=len(TOOL_CATEGORIES["basket_management"]),
            budget_tools=len(TOOL_CATEGORIES["budget_management"]),
            hotel_tools=len(TOOL_CATEGORIES["hotel_inventory_management"]),
            product_tools=len(TOOL_CATEGORIES["generic_product_management"]),
            order_tools=len(TOOL_CATEGORIES["order_management"]),
            package_tools=len(TOOL_CATEGORIES["package_management"]),
            users_tools=len(TOOL_CATEGORIES["users_rewards_management"]),
            geographic_tools=len(TOOL_CATEGORIES["geographic_search"])
        )
        
        return ALL_TOOLS
    
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle tool calls with comprehensive routing and error handling."""
        
        # Determine tool category for logging
        tool_category = "unknown"
        for category, tools in TOOL_CATEGORIES.items():
            if name in tools:
                tool_category = category
                break
        
        logger.info(
            "Tool called",
            tool_name=name,
            tool_category=tool_category,
            arguments=arguments,
            has_handler=name in TOOL_HANDLERS
        )
        
        try:
            # Route to appropriate tool handler
            if name in TOOL_HANDLERS:
                handler = TOOL_HANDLERS[name]
                result = await handler(arguments)
                
                logger.info(
                    "Tool executed successfully",
                    tool_name=name,
                    tool_category=tool_category,
                    result_count=len(result) if result else 0
                )
                
                return result
            else:
                error_msg = f"Unknown tool: {name}"
                available_tools = list(TOOL_HANDLERS.keys())
                
                logger.error(
                    "Unknown tool requested",
                    tool_name=name,
                    available_tools_count=len(available_tools)
                )
                
                # Provide helpful error with available tools
                suggestion_text = f"""❌ **Unknown Tool: {name}**

The requested tool is not available. Here are the available tools organized by category:

🔐 **Authentication ({len(TOOL_CATEGORIES['authentication'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['authentication'])}

🛒 **Basket Management ({len(TOOL_CATEGORIES['basket_management'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['basket_management'])}

💰 **Budget Management ({len(TOOL_CATEGORIES['budget_management'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['budget_management'])}

🏨 **Hotel & Inventory Management ({len(TOOL_CATEGORIES['hotel_inventory_management'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['hotel_inventory_management'])}

📦 **Generic Product Management ({len(TOOL_CATEGORIES['generic_product_management'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['generic_product_management'])}

📋 **Order Management ({len(TOOL_CATEGORIES['order_management'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['order_management'])}

📦 **Package Management ({len(TOOL_CATEGORIES['package_management'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['package_management'])}

👥 **Users and Rewards Management ({len(TOOL_CATEGORIES['users_rewards_management'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['users_rewards_management'])}

🌍 **Geographic Search ({len(TOOL_CATEGORIES['geographic_search'])} tools):**
{chr(10).join(f'• {tool}' for tool in TOOL_CATEGORIES['geographic_search'])}

💡 **Total Available Tools**: {len(ALL_TOOLS)}

Please use one of the tools listed above. Tool names are case-sensitive.
"""
                
                return [types.TextContent(type="text", text=suggestion_text)]
                
        except Exception as e:
            error_msg = f"Error executing tool {name}: {str(e)}"
            
            logger.error(
                "Tool execution failed",
                tool_name=name,
                tool_category=tool_category,
                error=str(e),
                error_type=type(e).__name__
            )
            
            error_text = f"""💥 **Tool Execution Error**

**Tool**: {name}
**Category**: {tool_category.replace('_', ' ').title()}
**Error**: {str(e)}
**Error Type**: {type(e).__name__}

🔧 **Troubleshooting Steps:**
1. Verify the tool arguments are correct
2. Check authentication credentials if required
3. Ensure the API endpoint is accessible
4. Review the tool documentation for proper usage
5. Contact support if the issue persists

**Available Debugging Info:**
- Tool exists in registry: {'Yes' if name in TOOL_HANDLERS else 'No'}
- Arguments provided: {len(arguments) if arguments else 0} parameter(s)
- Server status: Running normally
"""
            
            return [types.TextContent(type="text", text=error_text)]
    
    @server.list_resources()
    async def handle_list_resources() -> list[types.Resource]:
        """List available resources."""
        # Currently no static resources defined
        # Future: Could include API documentation, schema files, etc.
        logger.debug("Resource list requested - no resources currently available")
        return []
    
    @server.read_resource()
    async def handle_read_resource(uri: types.AnyUrl) -> str:
        """Read a specific resource."""
        # Currently no resources defined
        logger.warning("Resource read requested but no resources available", uri=str(uri))
        raise ValueError(f"Resource not found: {uri}")
    
    @server.list_prompts()
    async def handle_list_prompts() -> list[types.Prompt]:
        """List available prompts."""
        # Currently no custom prompts defined
        # Future: Could include reservation workflow prompts, search templates, etc.
        logger.debug("Prompt list requested - no prompts currently available")
        return []
    
    @server.get_prompt()
    async def handle_get_prompt(name: str, arguments: dict | None = None) -> types.GetPromptResult:
        """Get a specific prompt."""
        # Currently no prompts defined
        logger.warning("Prompt requested but no prompts available", prompt_name=name)
        raise ValueError(f"Prompt not found: {name}")
    
    return server


async def main():
    """Main entry point for the MCP server."""
    try:
        # Load configuration
        config = NeobookingsConfig.from_env()
        
        logger.info(
            "Starting Neobookings MCP Server",
            server_name=SERVER_NAME,
            server_version=SERVER_VERSION,
            api_base_url=config.base_url,
            total_tools=len(ALL_TOOLS),
            tool_categories=len(TOOL_CATEGORIES),
            authentication_enabled=bool(config.client_code and config.username),
            client_code=config.client_code,
            system_code=config.system_code,
            username=config.username
        )
        
        # Log tool summary by category
        for category, tools in TOOL_CATEGORIES.items():
            logger.info(
                f"Loaded {category.replace('_', ' ').title()} tools",
                category=category,
                tool_count=len(tools),
                tools=tools
            )
        
        # Create and configure server
        server = create_server()
        
        # Define comprehensive server capabilities
        capabilities = ServerCapabilities(
            tools={"listChanged": True},
            resources={"subscribe": True, "listChanged": True},
            prompts={"listChanged": True}
        )
        
        # Initialize server options
        options = InitializationOptions(
            server_name=SERVER_NAME,
            server_version=SERVER_VERSION,
            capabilities=capabilities
        )
        
        logger.info(
            "MCP server configured successfully",
            capabilities=["tools", "resources", "prompts"],
            ready_for_connections=True
        )
        
        # Run the server using stdio transport
        async with stdio_server() as (read_stream, write_stream):
            logger.info(
                "MCP server started successfully and ready for connections",
                transport="stdio",
                total_endpoints=len(ALL_TOOLS),
                status="ready"
            )
            
            await server.run(
                read_stream,
                write_stream,
                options
            )
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(
            "Fatal server error",
            error=str(e),
            error_type=type(e).__name__,
            server_name=SERVER_NAME
        )
        sys.exit(1)


def print_startup_banner():
    """Print a startup banner with server information."""
    banner = f"""
{'='*80}
NEOBOOKINGS MCP SERVER v{SERVER_VERSION}
{'='*80}

Server Statistics:
   • Total Tools Available: {len(ALL_TOOLS)}
   • Tool Categories: {len(TOOL_CATEGORIES)}
   • Authentication Tools: {len(TOOL_CATEGORIES['authentication'])}
   • Basket Management Tools: {len(TOOL_CATEGORIES['basket_management'])}
   • Budget Management Tools: {len(TOOL_CATEGORIES['budget_management'])}
   • Hotel & Inventory Tools: {len(TOOL_CATEGORIES['hotel_inventory_management'])}
   • Generic Product Tools: {len(TOOL_CATEGORIES['generic_product_management'])}
   • Order Management Tools: {len(TOOL_CATEGORIES['order_management'])}
   • Package Management Tools: {len(TOOL_CATEGORIES['package_management'])}
   • Users and Rewards Tools: {len(TOOL_CATEGORIES['users_rewards_management'])}
   • Geographic Search Tools: {len(TOOL_CATEGORIES['geographic_search'])}

Ready to process hotel reservation requests through natural language!

Integration Support:
   • Claude Desktop: Configured via claude_desktop_config.json
   • MCP Protocol: Full compatibility
   • API Version: Neobookings Public API v2
   • Transport: STDIO

Usage: The server automatically handles authentication and provides
   comprehensive hotel search, booking, and management capabilities.

{'='*80}
"""
    print(banner)


if __name__ == "__main__":
    # Print startup information
    
    # Run the server
    asyncio.run(main())
