"""
ctgenericproduct - Generic Products Management Tests

This module contains tests for generic products management tools.
"""

from .test_generic_product_avail_rq import *
from .test_generic_product_details_rq import *
from .test_generic_product_extra_avail_rq import *

__all__ = [
    "TestGenericProductAvailRQHandler",
    "TestGenericProductDetailsRQHandler", 
    "TestGenericProductExtraAvailRQHandler"
]
