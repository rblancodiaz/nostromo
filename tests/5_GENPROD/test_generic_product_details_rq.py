"""
Tests for GenericProductDetailsRQ - Generic Product Details Tool
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from tools.ctgenericproduct.generic_product_details_rq import (
    GenericProductDetailsRQHandler,
    call_generic_product_details_rq,
    GENERIC_PRODUCT_DETAILS_RQ_TOOL
)
from config import ValidationError, AuthenticationError, APIError


class TestGenericProductDetailsRQHandler:
    """Test cases for GenericProductDetailsRQHandler"""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing"""
        return GenericProductDetailsRQHandler()
    
    @pytest.fixture
    def sample_arguments(self):
        """Sample valid arguments for testing"""
        return {
            "product_ids": ["PROD123", "PROD456"],
            "hotel_ids": ["HOTEL123"],
            "status": "enabled",
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
                "TimeResponse": 100
            },
            "GenericProductDetail": [
                {
                    "GenericProductId": "PROD123",
                    "HotelId": "HOTEL123",
                    "HotelHash": "hash123",
                    "GenericProductName": "Spa Package",
                    "GenericProductDescription": "Relaxing spa experience with massage and treatments",
                    "Status": "enabled",
                    "ReservationMode": "withdates",
                    "ReservationLimit": 10,
                    "Combinable": "everything",
                    "Order": 1,
                    "GenericProductCategory": [
                        {
                            "Code": "SPA",
                            "Name": "Spa Services"
                        },
                        {
                            "Code": "WELLNESS",
                            "Name": "Wellness"
                        }
                    ],
                    "HotelRoomId": ["ROOM123", "ROOM456"],
                    "HotelBoardId": ["BOARD123"],
                    "HotelRoomExtraId": ["EXTRA123", "EXTRA456"],
                    "Media": [
                        {
                            "MediaType": "photo",
                            "Caption": "Spa facilities",
                            "Url": "https://example.com/spa.jpg",
                            "Main": True,
                            "Order": 1
                        },
                        {
                            "MediaType": "video",
                            "Caption": "Spa tour",
                            "Url": "https://example.com/spa-tour.mp4",
                            "Main": False,
                            "Order": 2
                        }
                    ]
                },
                {
                    "GenericProductId": "PROD456",
                    "HotelId": "HOTEL123",
                    "HotelHash": "hash123",
                    "GenericProductName": "Golf Package",
                    "GenericProductDescription": "Complete golf experience with lessons and equipment",
                    "Status": "enabled",
                    "ReservationMode": "undated",
                    "ReservationLimit": 5,
                    "Combinable": "samecategory",
                    "Order": 2,
                    "GenericProductCategory": [
                        {
                            "Code": "GOLF",
                            "Name": "Golf Services"
                        }
                    ],
                    "HotelRoomId": [],
                    "HotelBoardId": [],
                    "HotelRoomExtraId": [],
                    "Media": []
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_execute_success(self, handler, sample_arguments, sample_api_response):
        """Test successful execution"""
        with patch('tools.ctgenericproduct.generic_product_details_rq.NeobookingsHTTPClient') as mock_client_class:
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
            assert "Retrieved 2 product detail(s)" in result["message"]
            
            data = result["data"]
            assert data["summary"]["total_found"] == 2
            assert len(data["products"]) == 2
            
            # Check first product details
            product1 = data["products"][0]
            assert product1["product_id"] == "PROD123"
            assert product1["product_name"] == "Spa Package"
            assert product1["status"] == "enabled"
            assert product1["reservation_mode"] == "withdates"
            assert product1["reservation_limit"] == 10
            assert product1["combinable"] == "everything"
            assert len(product1["categories"]) == 2
            assert len(product1["hotel_room_ids"]) == 2
            assert len(product1["media"]) == 2
            
            # Check second product details
            product2 = data["products"][1]
            assert product2["product_id"] == "PROD456"
            assert product2["product_name"] == "Golf Package"
            assert product2["reservation_mode"] == "undated"
            assert len(product2["hotel_room_ids"]) == 0
            assert len(product2["media"]) == 0
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            mock_client.set_token.assert_called_once_with("test-token-123")
    
    @pytest.mark.asyncio
    async def test_execute_with_filters(self, handler):
        """Test execution with various filters"""
        arguments = {
            "product_ids": ["PROD123"],
            "hotel_ids": ["HOTEL123", "HOTEL456"],
            "hotel_room_ids": ["ROOM123", "ROOM456"],
            "status": "all",
            "language": "en"
        }
        
        with patch('tools.ctgenericproduct.generic_product_details_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [
                {"Token": "test-token-123"},
                {
                    "Response": {"StatusCode": 200, "RequestId": "test", "Timestamp": "2024-01-15T10:00:00Z", "TimeResponse": 100},
                    "GenericProductDetail": []
                }
            ]
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            
            # Check that filters were applied
            call_args = mock_client.post.call_args_list[1][0][1]
            assert call_args["GenericProductId"] == ["PROD123"]
            assert call_args["HotelId"] == ["HOTEL123", "HOTEL456"]
            assert call_args["HotelRoomId"] == ["ROOM123", "ROOM456"]
            assert call_args["Status"] == "all"
            assert call_args["Request"]["Language"] == "en"
    
    @pytest.mark.asyncio
    async def test_execute_no_filters(self, handler):
        """Test execution with no filters (all products)"""
        arguments = {"language": "es"}
        
        with patch('tools.ctgenericproduct.generic_product_details_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [
                {"Token": "test-token-123"},
                {
                    "Response": {"StatusCode": 200, "RequestId": "test", "Timestamp": "2024-01-15T10:00:00Z", "TimeResponse": 100},
                    "GenericProductDetail": []
                }
            ]
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            
            # Check that only Request is in the payload (no filters)
            call_args = mock_client.post.call_args_list[1][0][1]
            assert "GenericProductId" not in call_args
            assert "HotelId" not in call_args
            assert "HotelRoomId" not in call_args
            assert "Status" not in call_args  # Default "enabled" should not be sent
    
    @pytest.mark.asyncio
    async def test_validation_error_invalid_product_id(self, handler):
        """Test validation error for invalid product ID"""
        arguments = {
            "product_ids": ["", "  "],  # Empty and whitespace-only
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid product ID" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validation_error_invalid_hotel_id(self, handler):
        """Test validation error for invalid hotel ID"""
        arguments = {
            "hotel_ids": [123],  # Not a string
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid hotel ID" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validation_error_invalid_room_id(self, handler):
        """Test validation error for invalid room ID"""
        arguments = {
            "hotel_room_ids": [""],  # Empty string
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid hotel room ID" in result["message"]
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, handler, sample_arguments):
        """Test authentication error handling"""
        with patch('tools.ctgenericproduct.generic_product_details_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock failed authentication
            mock_client.post.return_value = {}  # No token returned
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_api_error(self, handler, sample_arguments):
        """Test API error handling"""
        with patch('tools.ctgenericproduct.generic_product_details_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock successful auth, then API error
            mock_client.post.side_effect = [
                {"Token": "test-token-123"},
                APIError("API request failed", "API_ERROR")
            ]
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is False
            assert "API error" in result["message"]
    
    @pytest.mark.asyncio
    async def test_unexpected_error(self, handler, sample_arguments):
        """Test unexpected error handling"""
        with patch('tools.ctgenericproduct.generic_product_details_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Unexpected error")
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is False
            assert "Unexpected error" in result["message"]
    
    def test_format_categories(self, handler):
        """Test category formatting"""
        categories = [
            {"Code": "SPA", "Name": "Spa Services"},
            {"Code": "WELLNESS", "Name": "Wellness"}
        ]
        
        formatted = handler._format_categories(categories)
        
        assert len(formatted) == 2
        assert formatted[0]["code"] == "SPA"
        assert formatted[0]["name"] == "Spa Services"
        assert formatted[1]["code"] == "WELLNESS"
        assert formatted[1]["name"] == "Wellness"
    
    def test_format_media(self, handler):
        """Test media formatting"""
        media = [
            {
                "MediaType": "photo",
                "Caption": "Test photo",
                "Url": "https://example.com/photo.jpg",
                "Main": True,
                "Order": 1
            },
            {
                "MediaType": "video",
                "Caption": "Test video",
                "Url": "https://example.com/video.mp4",
                "Main": False,
                "Order": 2
            }
        ]
        
        formatted = handler._format_media(media)
        
        assert len(formatted) == 2
        assert formatted[0]["type"] == "photo"
        assert formatted[0]["caption"] == "Test photo"
        assert formatted[0]["url"] == "https://example.com/photo.jpg"
        assert formatted[0]["is_main"] is True
        assert formatted[0]["order"] == 1
        
        assert formatted[1]["type"] == "video"
        assert formatted[1]["is_main"] is False
    
    def test_tool_definition(self):
        """Test that the tool is properly defined"""
        assert GENERIC_PRODUCT_DETAILS_RQ_TOOL.name == "generic_product_details_rq"
        assert "detailed information about generic products" in GENERIC_PRODUCT_DETAILS_RQ_TOOL.description.lower()
        
        # Check that all properties are optional
        required_fields = GENERIC_PRODUCT_DETAILS_RQ_TOOL.inputSchema.get("required", [])
        assert len(required_fields) == 0
        
        # Check enum values for status
        status_enum = GENERIC_PRODUCT_DETAILS_RQ_TOOL.inputSchema["properties"]["status"]["enum"]
        assert "enabled" in status_enum
        assert "disabled" in status_enum
        assert "all" in status_enum


@pytest.mark.asyncio
async def test_call_generic_product_details_rq_success():
    """Test the MCP tool handler function with successful response"""
    arguments = {"product_ids": ["PROD123"], "language": "es"}
    
    mock_result = {
        "success": True,
        "data": {
            "products": [
                {
                    "product_id": "PROD123",
                    "product_name": "Spa Package",
                    "product_description": "Relaxing spa experience",
                    "hotel_id": "HOTEL123",
                    "status": "enabled",
                    "reservation_mode": "withdates",
                    "reservation_limit": 10,
                    "combinable": "everything",
                    "order": 1,
                    "categories": [
                        {"code": "SPA", "name": "Spa Services"}
                    ],
                    "hotel_room_ids": ["ROOM123"],
                    "media": [
                        {"type": "photo", "caption": "Spa facilities", "is_main": True}
                    ]
                }
            ],
            "summary": {"total_found": 1, "status_filter": "enabled", "language": "es"},
            "request_metadata": {"RequestId": "test-123", "Timestamp": "2024-01-15T10:00:00Z"},
            "api_response": {"TimeResponse": 100}
        },
        "message": "Retrieved 1 product detail(s)"
    }
    
    with patch('tools.ctgenericproduct.generic_product_details_rq.handler.execute', return_value=mock_result):
        result = await call_generic_product_details_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Generic Product Details" in response_text
        assert "Total Products Found: 1" in response_text
        assert "Product #1: Spa Package" in response_text
        assert "PROD123" in response_text
        assert "Spa Services (SPA)" in response_text
        assert "ROOM123" in response_text


@pytest.mark.asyncio
async def test_call_generic_product_details_rq_error():
    """Test the MCP tool handler function with error response"""
    arguments = {"product_ids": [""]}
    
    mock_result = {
        "success": False,
        "message": "Validation error: Invalid product ID",
        "error": {"error_code": "VALIDATION_ERROR"}
    }
    
    with patch('tools.ctgenericproduct.generic_product_details_rq.handler.execute', return_value=mock_result):
        result = await call_generic_product_details_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Generic Product Details Retrieval Failed" in response_text
        assert "Validation error" in response_text


@pytest.mark.asyncio
async def test_call_generic_product_details_rq_exception():
    """Test the MCP tool handler function with exception"""
    arguments = {"product_ids": ["PROD123"]}
    
    with patch('tools.ctgenericproduct.generic_product_details_rq.handler.execute', side_effect=Exception("Test error")):
        result = await call_generic_product_details_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Tool Execution Error" in response_text
        assert "Test error" in response_text
