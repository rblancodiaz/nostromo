"""
Tests for GenericProductExtraAvailRQ - Generic Product Extra Availability Tool
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from tools.ctgenericproduct.generic_product_extra_avail_rq import (
    GenericProductExtraAvailRQHandler,
    call_generic_product_extra_avail_rq,
    GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL
)
from config import ValidationError, AuthenticationError, APIError


class TestGenericProductExtraAvailRQHandler:
    """Test cases for GenericProductExtraAvailRQHandler"""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing"""
        return GenericProductExtraAvailRQHandler()
    
    @pytest.fixture
    def sample_arguments(self):
        """Sample valid arguments for testing"""
        return {
            "product_availability_ids": ["AVAIL123", "AVAIL456"],
            "basket_id": "BASKET123",
            "origin": "web",
            "client_country": "ES",
            "client_ip": "192.168.1.1",
            "client_device": "desktop",
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
                "TimeResponse": 120
            },
            "GenericProductExtraAvail": [
                {
                    "GenericProductExtraAvailabilityId": "EXTRA_AVAIL123",
                    "GenericProductAvailabilityId": "AVAIL123",
                    "GenericProductExtraId": "EXTRA123",
                    "Release": 7,
                    "MinStay": 2,
                    "Availability": 10,
                    "DateForExtra": "2024-12-15",
                    "GenericProductExtraAmounts": {
                        "ExtraAmountType": "unit",
                        "Currency": "EUR",
                        "AmountFinal": 50.00,
                        "AmountBase": 45.00,
                        "AmountTaxes": 5.00,
                        "AmountBefore": 50.00,
                        "AmountBeforeInventory": 48.00,
                        "AmountBeforeMax": 55.00,
                        "AmountOffers": 0.00,
                        "AmountDiscounts": 0.00
                    }
                },
                {
                    "GenericProductExtraAvailabilityId": "EXTRA_AVAIL456",
                    "GenericProductAvailabilityId": "AVAIL456",
                    "GenericProductExtraId": "EXTRA456",
                    "Release": 14,
                    "MinStay": 1,
                    "Availability": 5,
                    "DateForExtra": "2024-12-16",
                    "GenericProductExtraAmounts": {
                        "ExtraAmountType": "day",
                        "Currency": "EUR",
                        "AmountFinal": 25.00,
                        "AmountBase": 20.00,
                        "AmountTaxes": 3.00,
                        "AmountBefore": 25.00,
                        "AmountBeforeInventory": 22.00,
                        "AmountBeforeMax": 28.00,
                        "AmountOffers": 2.00,
                        "AmountDiscounts": 0.00
                    }
                }
            ],
            "GenericProductExtraNotAvail": [
                {
                    "GenericProductAvailabilityId": "AVAIL789",
                    "GenericProductExtraId": "EXTRA789",
                    "ExtraAmountType": "person",
                    "Release": 3,
                    "MinStay": 1,
                    "Cause": {
                        "Code": 102,
                        "Description": "Insufficient availability",
                        "Target": "quantity"
                    }
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_execute_success(self, handler, sample_arguments, sample_api_response):
        """Test successful execution"""
        with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.NeobookingsHTTPClient') as mock_client_class:
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
            assert "Found 2 available and 1 unavailable extra(s)" in result["message"]
            
            data = result["data"]
            assert data["summary"]["total_availability_ids"] == 2
            assert data["summary"]["available_extras_count"] == 2
            assert data["summary"]["unavailable_extras_count"] == 1
            assert len(data["available_extras"]) == 2
            assert len(data["unavailable_extras"]) == 1
            
            # Check first available extra
            extra1 = data["available_extras"][0]
            assert extra1["extra_availability_id"] == "EXTRA_AVAIL123"
            assert extra1["product_availability_id"] == "AVAIL123"
            assert extra1["extra_id"] == "EXTRA123"
            assert extra1["release"] == 7
            assert extra1["min_stay"] == 2
            assert extra1["availability"] == 10
            assert extra1["date_for_extra"] == "2024-12-15"
            
            # Check amounts for first extra
            amounts1 = extra1["amounts"]
            assert amounts1["amount_type"] == "unit"
            assert amounts1["currency"] == "EUR"
            assert amounts1["final_amount"] == 50.00
            assert amounts1["base_amount"] == 45.00
            assert amounts1["taxes_amount"] == 5.00
            
            # Check second available extra
            extra2 = data["available_extras"][1]
            assert extra2["extra_availability_id"] == "EXTRA_AVAIL456"
            assert extra2["amounts"]["amount_type"] == "day"
            assert extra2["amounts"]["offers_amount"] == 2.00
            
            # Check unavailable extra
            unavail_extra = data["unavailable_extras"][0]
            assert unavail_extra["product_availability_id"] == "AVAIL789"
            assert unavail_extra["extra_id"] == "EXTRA789"
            assert unavail_extra["amount_type"] == "person"
            assert unavail_extra["cause"]["code"] == 102
            assert unavail_extra["cause"]["description"] == "Insufficient availability"
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            mock_client.set_token.assert_called_once_with("test-token-123")
    
    @pytest.mark.asyncio
    async def test_execute_minimal_arguments(self, handler):
        """Test execution with minimal required arguments"""
        arguments = {
            "product_availability_ids": ["AVAIL123"],
            "language": "es"
        }
        
        with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [
                {"Token": "test-token-123"},
                {
                    "Response": {"StatusCode": 200, "RequestId": "test", "Timestamp": "2024-01-15T10:00:00Z", "TimeResponse": 100},
                    "GenericProductExtraAvail": [],
                    "GenericProductExtraNotAvail": []
                }
            ]
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            
            # Check that only required fields are in the payload
            call_args = mock_client.post.call_args_list[1][0][1]
            assert call_args["GenericProductAvailabilityId"] == ["AVAIL123"]
            assert "BasketId" not in call_args
            assert "Origin" not in call_args
            assert "ClientLocation" not in call_args
            assert "ClientDevice" not in call_args
    
    @pytest.mark.asyncio
    async def test_execute_with_all_optional_fields(self, handler):
        """Test execution with all optional fields"""
        arguments = {
            "product_availability_ids": ["AVAIL123"],
            "basket_id": "BASKET123",
            "origin": "mobile_app",
            "client_country": "FR",
            "client_ip": "10.0.0.1",
            "client_device": "tablet",
            "language": "fr"
        }
        
        with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [
                {"Token": "test-token-123"},
                {
                    "Response": {"StatusCode": 200, "RequestId": "test", "Timestamp": "2024-01-15T10:00:00Z", "TimeResponse": 100},
                    "GenericProductExtraAvail": [],
                    "GenericProductExtraNotAvail": []
                }
            ]
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            
            # Check that all optional fields are in the payload
            call_args = mock_client.post.call_args_list[1][0][1]
            assert call_args["GenericProductAvailabilityId"] == ["AVAIL123"]
            assert call_args["BasketId"] == "BASKET123"
            assert call_args["Origin"] == "mobile_app"
            assert call_args["ClientDevice"] == "tablet"
            assert call_args["Request"]["Language"] == "fr"
            
            client_location = call_args["ClientLocation"]
            assert client_location["Country"] == "FR"
            assert client_location["Ip"] == "10.0.0.1"
    
    @pytest.mark.asyncio
    async def test_execute_with_client_country_only(self, handler):
        """Test execution with only client country (no IP)"""
        arguments = {
            "product_availability_ids": ["AVAIL123"],
            "client_country": "DE"
        }
        
        with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [
                {"Token": "test-token-123"},
                {
                    "Response": {"StatusCode": 200, "RequestId": "test", "Timestamp": "2024-01-15T10:00:00Z", "TimeResponse": 100},
                    "GenericProductExtraAvail": [],
                    "GenericProductExtraNotAvail": []
                }
            ]
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            
            # Check client location with only country
            call_args = mock_client.post.call_args_list[1][0][1]
            client_location = call_args["ClientLocation"]
            assert client_location["Country"] == "DE"
            assert "Ip" not in client_location
    
    @pytest.mark.asyncio
    async def test_validation_error_empty_availability_ids(self, handler):
        """Test validation error when no availability IDs provided"""
        arguments = {"product_availability_ids": []}
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one product availability ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validation_error_missing_availability_ids(self, handler):
        """Test validation error when availability IDs not provided"""
        arguments = {"language": "es"}
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one product availability ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validation_error_invalid_availability_id(self, handler):
        """Test validation error for invalid availability ID"""
        arguments = {
            "product_availability_ids": ["AVAIL123", "", "  "],  # Include empty and whitespace
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid product availability ID" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validation_error_invalid_basket_id(self, handler):
        """Test validation error for invalid basket ID"""
        arguments = {
            "product_availability_ids": ["AVAIL123"],
            "basket_id": 123,  # Not a string
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid basket ID" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validation_error_invalid_client_country(self, handler):
        """Test validation error for invalid client country"""
        arguments = {
            "product_availability_ids": ["AVAIL123"],
            "client_country": "ESP",  # Should be 2 characters
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Client country code must be 2 characters" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validation_error_empty_client_country(self, handler):
        """Test validation error for empty client country"""
        arguments = {
            "product_availability_ids": ["AVAIL123"],
            "client_country": "",  # Empty string
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid client country" in result["message"]
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, handler, sample_arguments):
        """Test authentication error handling"""
        with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.NeobookingsHTTPClient') as mock_client_class:
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
        with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.NeobookingsHTTPClient') as mock_client_class:
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
        with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.NeobookingsHTTPClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Unexpected error")
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is False
            assert "Unexpected error" in result["message"]
    
    def test_format_extra_amounts(self, handler):
        """Test extra amounts formatting"""
        amounts = {
            "ExtraAmountType": "unit",
            "Currency": "EUR",
            "AmountFinal": 50.00,
            "AmountBase": 45.00,
            "AmountTaxes": 5.00,
            "AmountBefore": 50.00,
            "AmountBeforeInventory": 48.00,
            "AmountBeforeMax": 55.00,
            "AmountOffers": 2.00,
            "AmountDiscounts": 1.00
        }
        
        formatted = handler._format_extra_amounts(amounts)
        
        assert formatted["amount_type"] == "unit"
        assert formatted["currency"] == "EUR"
        assert formatted["final_amount"] == 50.00
        assert formatted["base_amount"] == 45.00
        assert formatted["taxes_amount"] == 5.00
        assert formatted["before_amount"] == 50.00
        assert formatted["inventory_amount"] == 48.00
        assert formatted["max_amount"] == 55.00
        assert formatted["offers_amount"] == 2.00
        assert formatted["discounts_amount"] == 1.00
    
    def test_format_extra_amounts_empty(self, handler):
        """Test extra amounts formatting with empty input"""
        formatted = handler._format_extra_amounts({})
        assert formatted == {}
        
        formatted = handler._format_extra_amounts(None)
        assert formatted == {}
    
    def test_tool_definition(self):
        """Test that the tool is properly defined"""
        assert GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL.name == "generic_product_extra_avail_rq"
        assert "availability of extras/supplements for generic products" in GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL.description.lower()
        
        # Check required fields
        required_fields = GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL.inputSchema["required"]
        assert "product_availability_ids" in required_fields
        
        # Check array constraints
        availability_ids_schema = GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL.inputSchema["properties"]["product_availability_ids"]
        assert availability_ids_schema["type"] == "array"
        assert availability_ids_schema["minItems"] == 1
        assert availability_ids_schema["maxItems"] == 50
        
        # Check enum values for client_device
        device_enum = GENERIC_PRODUCT_EXTRA_AVAIL_RQ_TOOL.inputSchema["properties"]["client_device"]["enum"]
        assert "desktop" in device_enum
        assert "mobile" in device_enum
        assert "tablet" in device_enum


@pytest.mark.asyncio
async def test_call_generic_product_extra_avail_rq_success():
    """Test the MCP tool handler function with successful response"""
    arguments = {
        "product_availability_ids": ["AVAIL123"],
        "language": "es"
    }
    
    mock_result = {
        "success": True,
        "data": {
            "available_extras": [
                {
                    "extra_availability_id": "EXTRA_AVAIL123",
                    "product_availability_id": "AVAIL123",
                    "extra_id": "EXTRA123",
                    "release": 7,
                    "min_stay": 2,
                    "availability": 10,
                    "date_for_extra": "2024-12-15",
                    "amounts": {
                        "amount_type": "unit",
                        "currency": "EUR",
                        "final_amount": 50.00,
                        "base_amount": 45.00,
                        "taxes_amount": 5.00
                    }
                }
            ],
            "unavailable_extras": [],
            "summary": {
                "total_availability_ids": 1,
                "available_extras_count": 1,
                "unavailable_extras_count": 0,
                "language": "es"
            },
            "request_metadata": {"RequestId": "test-123", "Timestamp": "2024-01-15T10:00:00Z"},
            "api_response": {"TimeResponse": 120}
        },
        "message": "Found 1 available and 0 unavailable extra(s)"
    }
    
    with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.handler.execute', return_value=mock_result):
        result = await call_generic_product_extra_avail_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Generic Product Extra Availability" in response_text
        assert "Available Extras: 1" in response_text
        assert "Unavailable Extras: 0" in response_text
        assert "Extra #1" in response_text
        assert "EXTRA_AVAIL123" in response_text
        assert "50.0 EUR" in response_text
        assert "unit" in response_text


@pytest.mark.asyncio
async def test_call_generic_product_extra_avail_rq_error():
    """Test the MCP tool handler function with error response"""
    arguments = {"product_availability_ids": []}
    
    mock_result = {
        "success": False,
        "message": "Validation error: At least one product availability ID is required",
        "error": {"error_code": "VALIDATION_ERROR"}
    }
    
    with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.handler.execute', return_value=mock_result):
        result = await call_generic_product_extra_avail_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Generic Product Extra Availability Search Failed" in response_text
        assert "Validation error" in response_text


@pytest.mark.asyncio
async def test_call_generic_product_extra_avail_rq_exception():
    """Test the MCP tool handler function with exception"""
    arguments = {"product_availability_ids": ["AVAIL123"]}
    
    with patch('tools.ctgenericproduct.generic_product_extra_avail_rq.handler.execute', side_effect=Exception("Test error")):
        result = await call_generic_product_extra_avail_rq(arguments)
        
        assert len(result) == 1
        assert result[0].type == "text"
        
        response_text = result[0].text
        assert "Tool Execution Error" in response_text
        assert "Test error" in response_text
