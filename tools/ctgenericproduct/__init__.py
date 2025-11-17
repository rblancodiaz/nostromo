"""
ctgenericproduct - Generic Products Management Tools

This module contains tools for managing generic products in the Neobookings system,
including availability searches, product details, and extra services.
"""

from .generic_product_avail_rq import GENERIC_PRODUCT_AVAIL_RQ_TOOL, call_generic_product_avail_rq
from .generic_product_details_rq import GENERIC_PRODUCT_DETAILS_RQ_TOOL, call_generic_product_details_rq
from .generic_product_extra_avail_rq import GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL, call_generic_product_extra_avail_rq

__all__ = [
    # Tools
    "GENERIC_PRODUCT_AVAIL_RQ_TOOL",
    "GENERIC_PRODUCT_DETAILS_RQ_TOOL", 
    "GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL",
    
    # Handlers
    "call_generic_product_avail_rq",
    "call_generic_product_details_rq",
    "call_generic_product_extra_avail_rq"
]
