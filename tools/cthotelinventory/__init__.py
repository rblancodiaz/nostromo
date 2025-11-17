"""
Hotel Inventory Management Tools

This module contains all hotel and inventory management tools for the Neobookings MCP Server.
These tools handle hotel information, room availability, pricing, and inventory management.
"""

from .chain_info_list_details_rq import CHAIN_INFO_LIST_DETAILS_RQ_TOOL, call_chain_info_list_details_rq
from .hotel_board_details_rq import HOTEL_BOARD_DETAILS_RQ_TOOL, call_hotel_board_details_rq
from .hotel_calendar_avail_rq import HOTEL_CALENDAR_AVAIL_RQ_TOOL, call_hotel_calendar_avail_rq
from .hotel_details_rq import HOTEL_DETAILS_RQ_TOOL, call_hotel_details_rq
from .hotel_info_list_details_rq import HOTEL_INFO_LIST_DETAILS_RQ_TOOL, call_hotel_info_list_details_rq
from .hotel_inventory_read_rq import HOTEL_INVENTORY_READ_RQ_TOOL, call_hotel_inventory_read_rq
from .hotel_inventory_update_rq import HOTEL_INVENTORY_UPDATE_RQ_TOOL, call_hotel_inventory_update_rq
from .hotel_offer_details_rq import HOTEL_OFFER_DETAILS_RQ_TOOL, call_hotel_offer_details_rq
from .hotel_price_update_rq import HOTEL_PRICE_UPDATE_RQ_TOOL, call_hotel_price_update_rq
from .hotel_rate_details_rq import HOTEL_RATE_DETAILS_RQ_TOOL, call_hotel_rate_details_rq
from .hotel_room_avail_rq import HOTEL_ROOM_AVAIL_RQ_TOOL, call_hotel_room_avail_rq
from .hotel_room_details_rq import HOTEL_ROOM_DETAILS_RQ_TOOL, call_hotel_room_details_rq
from .hotel_room_extra_avail_rq import HOTEL_ROOM_EXTRA_AVAIL_RQ_TOOL, call_hotel_room_extra_avail_rq
from .hotel_room_extra_details_rq import HOTEL_ROOM_EXTRA_DETAILS_RQ_TOOL, call_hotel_room_extra_details_rq
from .hotel_search_rq import HOTEL_SEARCH_RQ_TOOL, call_hotel_search_rq

__all__ = [
    # Tools
    "CHAIN_INFO_LIST_DETAILS_RQ_TOOL",
    "HOTEL_BOARD_DETAILS_RQ_TOOL", 
    "HOTEL_CALENDAR_AVAIL_RQ_TOOL",
    "HOTEL_DETAILS_RQ_TOOL",
    "HOTEL_INFO_LIST_DETAILS_RQ_TOOL",
    "HOTEL_INVENTORY_READ_RQ_TOOL",
    "HOTEL_INVENTORY_UPDATE_RQ_TOOL",
    "HOTEL_OFFER_DETAILS_RQ_TOOL",
    "HOTEL_PRICE_UPDATE_RQ_TOOL",
    "HOTEL_RATE_DETAILS_RQ_TOOL",
    "HOTEL_ROOM_AVAIL_RQ_TOOL",
    "HOTEL_ROOM_DETAILS_RQ_TOOL",
    "HOTEL_ROOM_EXTRA_AVAIL_RQ_TOOL",
    "HOTEL_ROOM_EXTRA_DETAILS_RQ_TOOL",
    "HOTEL_SEARCH_RQ_TOOL",
    
    # Handlers
    "call_chain_info_list_details_rq",
    "call_hotel_board_details_rq",
    "call_hotel_calendar_avail_rq", 
    "call_hotel_details_rq",
    "call_hotel_info_list_details_rq",
    "call_hotel_inventory_read_rq",
    "call_hotel_inventory_update_rq",
    "call_hotel_offer_details_rq",
    "call_hotel_price_update_rq",
    "call_hotel_rate_details_rq",
    "call_hotel_room_avail_rq",
    "call_hotel_room_details_rq",
    "call_hotel_room_extra_avail_rq",
    "call_hotel_room_extra_details_rq",
    "call_hotel_search_rq"
]
