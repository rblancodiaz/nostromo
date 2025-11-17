"""
Tests for GenericProductAvailRQ - Generic Product Availability Search Tool
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from tools.ctgenericproduct.generic_product_avail_rq import (
    GenericProductAvailRQHandler,
    call_generic_product_avail_rq,
    GENERIC_PRODUCT_AVAIL_RQ_TOOL
)
from config import ValidationError, AuthenticationError, APIError


class TestGenericProductAvailRQHandler:
    """Test cases for GenericProductAvailRQHandler"""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing"""
        return GenericProductAvailRQHandler()
    
    @pytest.fixture
    def sample_arguments(self):
        """Sample valid arguments for testing"""
        return {
            "product_distributions": [
                {
                    "product_rph": 1,
                    "date_from": "2024-12-15",
                    "date_to": "2024-12-20",
                    "guests": [
                        {"age": 30, "amount": 2},
                        {"age": 8, "amount": 1}
                    ]
                }
            ],
            "countries": ["ES"],
            "zones": ["MAD"],
            "hotel_ids": ["HOTEL123"],
            "page": 1,
            "num_results": 10,
            "language": "es"
        }
    
    @pytest.fixture
    def sample_api_response(self):
        """Sample API response for testing"""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "test-request-123",
                "Timestamp": "2024-01-15T10:00:00Z",
                "TimeResponse": 150
            },
            "CurrentPage": 1,
            "TotalPages": 2,
            "TotalRecords": 15,
            "GenericProductDistribution": [
                {
                    "GenericProductRPH": 1,
                    "DateFrom": "2024-12-15",
                    "DateTo": "2024-12-20",
                    "Guest": [
                        {"Age": 30, "Amount": 2},
                        {"Age": 8, "Amount": 1}
                    ]
                }
            ],
            "GenericProductAvail": [
                {
                    "GenericProductAvailabilityId": "AVAIL123",
                    "GenericProductRPH": 1,
                    "GenericProductId": "PROD123",
                    "HotelRoomAvail": [
                        {
                            "HotelRoomAvailabilityId": "ROOM_AVAIL123",
                            "HotelId": "HOTEL123",
                            "HotelHash": "hash123",
                            "HotelRoomId": "ROOM123",
                            "HotelRoomRPH": 1,
                            "Quantity": 5,
                            "AmountsDetail": {
                                "Currency": "EUR",
                                "AmountFinal": 150.00,
                                "AmountTotal": 150.00,
                                "AmountBase": 120.00,
                                "AmountTaxes": 18.00,
                                "AmountTouristTax": 12.00
                            }
                        }
                    ]
                }
            ],
            "GenericProductNotAvail": [
                {
                    "GenericProductRPH": 2,
                    "GenericProductId": "PROD456",
                    "Cause": {
                        "Code": 101,
                        "Description": "No availability",
                        "Target": "availability"
                    }
                }
            ],
            "HotelBasicDetail": [],
            "HotelRoomBasicDetail": [],
            "GenericProductDetail": [],
            "HotelRoomExtraDetail": []
        }
    
    @pytest.mark.asyncio
    async def test_execute_success(self, handler, sample_arguments, sample_api_response):
        """Test successful execution"""
        with patch('tools.ctgenericproduct.generic_product_avail_rq.NeobookingsHTTPClient') as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock authentication response
            mock_client.post.side_effect = [
                {"Token": "test-token-123"},  # Auth response
                sample_api_response  # Main response
            ]
            
            # Execute
            result = await handler.execute(sample_arguments)
            
            # Assertions
            assert result["success"] is True
            assert "Found 15 product result(s)" in result["message"]
            
            data = result["data"]
            assert data["summary"]["total_found"] == 15
            assert data["summary"]["available_count"] == 1
            assert data["summary"]["unavailable_count"] == 1
            assert len(data["available_products"]) == 1
            assert len(data["unavailable_products"]) == 1
            
            # Check pagination
            pagination = data["pagination"]
            assert pagination["current_page"] == 1
            assert pagination["total_pages"] == 2
            assert pagination["total_records"] == 15
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            mock_client.set_token.assert_called_once_with("test-token-123")
    
    @pytest.mark.asyncio
    async def test_validation_error_empty_distributions(self, handler):
        """Test validation error when no product distributions provided"""
        arguments = {"product_distributions": []}
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "product distributions" in result["message"].lower()
    
    @pytest.mark.asyncio
    async def test_validation_error_invalid_distribution(self, handler):
        """Test validation error for invalid distribution data"""
        arguments = {
            "product_distributions": [
                {
                    "product_rph": -1,  # Invalid negative value
                    "guests": [{"age": 30, "amount": 1}]
                }
            ]
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "product_rph must be a positive integer" in result["message"]
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, handler, sample_arguments):
        """Test authentication error handling"""
        with patch('tools.ctgenericproduct.generic_product_avail_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock failed authentication
            mock_client.post.return_value = {}  # No token returned
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
    
    def test_tool_definition(self):
        """Test that the tool is properly defined"""
        assert GENERIC_PRODUCT_AVAIL_RQ_TOOL.name == "generic_product_avail_rq"
        assert "search for availability of generic products" in GENERIC_PRODUCT_AVAIL_RQ_TOOL.description.lower()
        
        # Check required fields
        required_fields = GENERIC_PRODUCT_AVAIL_RQ_TOOL.inputSchema["required"]
        assert "product_distributions" in required_fields


@pytest.mark.asyncio
async def test_call_generic_product_avail_rq_success():
    """Test the MCP tool handler function with successful response"""
    arguments = {
        "product_distributions": [
            {
                "product_rph": 1,
                "date_from": "2024-12-15",
                "date_to": "2024-12-20",
                "guests": [{"age": 30, "amount": 2}]
            }
        ]
    }
    
    mock_result = {
        "success": True,
        "data": {
            "available_products": [
                {
                    "availability_id": "AVAIL123",
                    "product_id": "PROD123",
                    "product_rph": 1,
                    "hotel_rooms": [
                        {
                            "availability_id": "ROOM_AVAIL123",
                            "hotel_id": "HOTEL123",
                            "room_id": "ROOM123",
                            "quantity": 5,
                            "amounts": {
                                "final_amount": 150.00,
                                "currency": "EUR"
                            }
                        }
                    ]
                }
            ],
            "unavailable_products": [],
            "pagination": {"current_page": 1, "total_pages": 1, "has_next_page": False, "has_previous_page": False},
            "summary": {"total_found": 1, "available_count": 1, "unavailable_count": 0, "language": "es"},
            "request_metadata": {"RequestId": "test-123", "Timestamp": "2024-01-15T10:00:00Z"},
            "api_response": {"TimeResponse": 150}
        },
        "message": "Found 1 product result(s), showing page 1 of 1"
    }
    
    with patch('tools.ctgenericproduct.generic_product_avail_rq.handler.execute', return_value=mock_result):
        result = await call_generic_product_avail_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Generic Product Availability Search Results" in response_text
        assert "Total Results Found: 1" in response_text
        assert "Available Products: 1" in response_text


@pytest.mark.asyncio
async def test_call_generic_product_avail_rq_exception():
    """Test the MCP tool handler function with exception"""
    arguments = {"product_distributions": [{"product_rph": 1, "guests": [{"age": 30, "amount": 1}]}]}
    
    with patch('tools.ctgenericproduct.generic_product_avail_rq.handler.execute', side_effect=Exception("Test error")):
        result = await call_generic_product_avail_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Tool Execution Error" in response_text
        assert "Test error" in response_text
