"""
Test module for PackageExtraAvailRQ endpoint
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from tools.ctpackages.package_extra_avail_rq import (
    PackageExtraAvailRQHandler,
    call_package_extra_avail_rq,
    PACKAGE_EXTRA_AVAIL_RQ_TOOL
)
from config import ValidationError, AuthenticationError, APIError


class TestPackageExtraAvailRQHandler:
    """Test cases for PackageExtraAvailRQHandler"""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing"""
        return PackageExtraAvailRQHandler()
    
    @pytest.fixture
    def sample_arguments(self):
        """Sample valid arguments for testing"""
        return {
            "package_availability_ids": ["PKG-AVAIL-001", "PKG-AVAIL-002"],
            "basket_id": "basket-123",
            "origin": "web",
            "client_device": "desktop",
            "language": "es"
        }
    
    @pytest.fixture
    def sample_api_response(self):
        """Sample API response for testing"""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "req-123",
                "Timestamp": "2024-01-01T12:00:00Z",
                "TimeResponse": 150
            },
            "PackageExtraAvail": [
                {
                    "PackageExtraAvailabilityId": "extra-avail-001",
                    "PackageAvailabilityId": "PKG-AVAIL-001",
                    "PackageExtraId": "EXTRA-001",
                    "Release": 1,
                    "MinStay": 2,
                    "Availability": 10,
                    "DateForExtra": "2024-01-15",
                    "PackageExtraAmounts": {
                        "ExtraAmountType": "day",
                        "Currency": "EUR",
                        "AmountFinal": 50.0,
                        "AmountBase": 45.0,
                        "AmountTaxes": 5.0,
                        "AmountOffers": 5.0,
                        "AmountDiscounts": 0.0
                    }
                }
            ],
            "PackageExtraNotAvail": [
                {
                    "PackageAvailabilityId": "PKG-AVAIL-002",
                    "PackageExtraId": "EXTRA-002",
                    "ExtraAmountType": "stay",
                    "Release": 7,
                    "MinStay": 3,
                    "Cause": {
                        "Code": 101,
                        "Description": "Extra service not available for selected dates",
                        "Target": "DateRange"
                    }
                }
            ]
        }
    
    def test_tool_definition(self):
        """Test that the tool is properly defined"""
        assert PACKAGE_EXTRA_AVAIL_RQ_TOOL.name == "package_extra_avail_rq"
        assert "package_availability_ids" in PACKAGE_EXTRA_AVAIL_RQ_TOOL.inputSchema["properties"]
        assert PACKAGE_EXTRA_AVAIL_RQ_TOOL.inputSchema["required"] == ["package_availability_ids"]
    
    def test_validate_package_availability_ids_valid(self, handler):
        """Test validation of valid package availability IDs"""
        valid_ids = ["PKG-001", "PKG-002", "PKG-003"]
        result = handler._validate_package_availability_ids(valid_ids)
        assert len(result) == 3
        assert all(isinstance(id, str) for id in result)
    
    def test_validate_package_availability_ids_empty(self, handler):
        """Test validation fails for empty package availability IDs"""
        with pytest.raises(ValidationError, match="Package availability IDs are required"):
            handler._validate_package_availability_ids([])
    
    def test_validate_package_availability_ids_too_many(self, handler):
        """Test validation fails for too many package availability IDs"""
        too_many_ids = [f"PKG-{i:03d}" for i in range(51)]
        with pytest.raises(ValidationError, match="Maximum 50 package availability IDs allowed"):
            handler._validate_package_availability_ids(too_many_ids)
    
    def test_validate_package_availability_ids_invalid_format(self, handler):
        """Test validation fails for invalid package availability ID format"""
        invalid_ids = ["", "  ", None]
        with pytest.raises(ValidationError):
            handler._validate_package_availability_ids(invalid_ids)
    
    def test_validate_package_availability_ids_too_long(self, handler):
        """Test validation fails for too long package availability IDs"""
        long_id = "PKG-" + "A" * 100  # More than 100 characters
        with pytest.raises(ValidationError, match="maximum 100 characters allowed"):
            handler._validate_package_availability_ids([long_id])
    
    def test_format_package_extra_availability(self, handler):
        """Test formatting of package extra availability data"""
        extra_data = [
            {
                "PackageExtraAvailabilityId": "extra-avail-001",
                "PackageAvailabilityId": "PKG-AVAIL-001",
                "PackageExtraId": "EXTRA-001",
                "Release": 1,
                "MinStay": 2,
                "Availability": 10,
                "DateForExtra": "2024-01-15",
                "PackageExtraAmounts": {
                    "ExtraAmountType": "day",
                    "Currency": "EUR",
                    "AmountFinal": 50.0,
                    "AmountBase": 45.0,
                    "AmountTaxes": 5.0
                }
            }
        ]
        
        result = handler._format_package_extra_availability(extra_data)
        
        assert len(result) == 1
        assert result[0]["availability_id"] == "extra-avail-001"
        assert result[0]["package_availability_id"] == "PKG-AVAIL-001"
        assert result[0]["extra_id"] == "EXTRA-001"
        assert result[0]["release"] == 1
        assert result[0]["min_stay"] == 2
        assert result[0]["availability"] == 10
        assert result[0]["date_for_extra"] == "2024-01-15"
        assert result[0]["amounts"]["extra_amount_type"] == "day"
        assert result[0]["amounts"]["currency"] == "EUR"
        assert result[0]["amounts"]["final_amount"] == 50.0
    
    def test_format_package_extra_not_available(self, handler):
        """Test formatting of package extra not available data"""
        extra_data = [
            {
                "PackageAvailabilityId": "PKG-AVAIL-002",
                "PackageExtraId": "EXTRA-002",
                "ExtraAmountType": "stay",
                "Release": 7,
                "MinStay": 3,
                "Cause": {
                    "Code": 101,
                    "Description": "Extra service not available for selected dates",
                    "Target": "DateRange"
                }
            }
        ]
        
        result = handler._format_package_extra_not_available(extra_data)
        
        assert len(result) == 1
        assert result[0]["package_availability_id"] == "PKG-AVAIL-002"
        assert result[0]["extra_id"] == "EXTRA-002"
        assert result[0]["extra_amount_type"] == "stay"
        assert result[0]["release"] == 7
        assert result[0]["min_stay"] == 3
        assert result[0]["cause"]["code"] == 101
        assert result[0]["cause"]["description"] == "Extra service not available for selected dates"
        assert result[0]["cause"]["target"] == "DateRange"
    
    @pytest.mark.asyncio
    async def test_execute_successful(self, handler, sample_arguments, sample_api_response):
        """Test successful execution of package extra availability request"""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            # Mock the HTTP client
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock authentication response
            mock_client.post.side_effect = [
                {"Token": "test-token"},  # Auth response
                sample_api_response       # Package extra availability response
            ]
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is True
            assert "data" in result
            assert result["data"]["summary"]["total_extras_available"] == 1
            assert result["data"]["summary"]["total_extras_not_available"] == 1
            assert result["data"]["summary"]["packages_checked"] == 2
            assert len(result["data"]["extras_available"]) == 1
            assert len(result["data"]["extras_not_available"]) == 1
    
    @pytest.mark.asyncio
    async def test_execute_authentication_failure(self, handler, sample_arguments):
        """Test execution with authentication failure"""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock failed authentication
            mock_client.post.return_value = {"Token": None}
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error(self, handler):
        """Test execution with validation error"""
        invalid_arguments = {
            "package_availability_ids": [],  # Empty list should cause validation error
            "language": "es"
        }
        
        result = await handler.execute(invalid_arguments)
        
        assert result["success"] is False
        assert "Validation error" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_api_error(self, handler, sample_arguments):
        """Test execution with API error"""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock successful authentication but API error
            mock_client.post.side_effect = [
                {"Token": "test-token"},
                APIError("API_ERROR", "Service temporarily unavailable")
            ]
            
            result = await handler.execute(sample_arguments)
            
            assert result["success"] is False
            assert "API error" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_with_optional_parameters(self, handler, sample_api_response):
        """Test execution with optional parameters"""
        arguments_with_optionals = {
            "package_availability_ids": ["PKG-AVAIL-001"],
            "basket_id": "basket-123",
            "origin": "mobile-app",
            "tracking": {
                "origin": "googlehpa",
                "code": "track-123",
                "locale": "es"
            },
            "client_location": {
                "country": "ES",
                "ip": "192.168.1.1"
            },
            "client_device": "mobile",
            "language": "en"
        }
        
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_client.post.side_effect = [
                {"Token": "test-token"},
                sample_api_response
            ]
            
            result = await handler.execute(arguments_with_optionals)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["basket_id"] == "basket-123"
            assert result["data"]["search_criteria"]["origin"] == "mobile-app"
            assert result["data"]["search_criteria"]["client_device"] == "mobile"


class TestPackageExtraAvailRQTool:
    """Test cases for the MCP tool function"""
    
    @pytest.mark.asyncio
    async def test_call_package_extra_avail_rq_success(self):
        """Test successful tool call"""
        arguments = {
            "package_availability_ids": ["PKG-AVAIL-001"],
            "language": "es"
        }
        
        mock_result = {
            "success": True,
            "data": {
                "search_criteria": {
                    "package_availability_ids": ["PKG-AVAIL-001"],
                    "basket_id": None,
                    "origin": None,
                    "client_device": "desktop"
                },
                "extras_available": [
                    {
                        "availability_id": "extra-avail-001",
                        "package_availability_id": "PKG-AVAIL-001",
                        "extra_id": "EXTRA-001",
                        "amounts": {
                            "currency": "EUR",
                            "final_amount": 50.0
                        }
                    }
                ],
                "extras_not_available": [],
                "summary": {
                    "total_extras_available": 1,
                    "total_extras_not_available": 0,
                    "packages_checked": 1
                },
                "request_metadata": {
                    "RequestId": "req-123",
                    "Timestamp": "2024-01-01T12:00:00Z"
                },
                "api_response": {
                    "TimeResponse": 150
                }
            },
            "message": "Found 1 available package extras"
        }
        
        with patch.object(PackageExtraAvailRQHandler, 'execute', return_value=mock_result):
            result = await call_package_extra_avail_rq(arguments)
            
            assert len(result) == 1
            assert "Package Extra Availability Results" in result[0].text
            assert "Total Extras Available: 1" in result[0].text
            assert "EXTRA-001" in result[0].text
    
    @pytest.mark.asyncio
    async def test_call_package_extra_avail_rq_failure(self):
        """Test tool call with failure"""
        arguments = {
            "package_availability_ids": [],
            "language": "es"
        }
        
        mock_result = {
            "success": False,
            "message": "Validation error: Package availability IDs are required",
            "error": {"error_code": "VALIDATION_ERROR"}
        }
        
        with patch.object(PackageExtraAvailRQHandler, 'execute', return_value=mock_result):
            result = await call_package_extra_avail_rq(arguments)
            
            assert len(result) == 1
            assert "Package Extra Availability Request Failed" in result[0].text
            assert "Validation error" in result[0].text
    
    @pytest.mark.asyncio
    async def test_call_package_extra_avail_rq_exception(self):
        """Test tool call with unexpected exception"""
        arguments = {
            "package_availability_ids": ["PKG-AVAIL-001"],
            "language": "es"
        }
        
        with patch.object(PackageExtraAvailRQHandler, 'execute', side_effect=Exception("Unexpected error")):
            result = await call_package_extra_avail_rq(arguments)
            
            assert len(result) == 1
            assert "Tool Execution Error" in result[0].text
            assert "Unexpected error" in result[0].text


class TestIntegration:
    """Integration tests for the package extra availability functionality"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_package_extra_availability_workflow(self):
        """Test complete package extra availability workflow"""
        # This test would require actual API credentials and should be run separately
        # It's marked with @pytest.mark.integration for selective running
        pass
    
    def test_tool_schema_validation(self):
        """Test that the tool schema is valid"""
        schema = PACKAGE_EXTRA_AVAIL_RQ_TOOL.inputSchema
        
        # Check required fields
        assert "package_availability_ids" in schema["required"]
        
        # Check field types
        props = schema["properties"]
        assert props["package_availability_ids"]["type"] == "array"
        assert props["package_availability_ids"]["items"]["type"] == "string"
        assert props["basket_id"]["type"] == "string"
        assert props["client_device"]["enum"] == ["desktop", "mobile", "tablet"]
        assert props["language"]["enum"] == ["es", "en", "fr", "de", "it", "pt"]
        
        # Check constraints
        assert props["package_availability_ids"]["minItems"] == 1
        assert props["package_availability_ids"]["maxItems"] == 50
        assert props["package_availability_ids"]["items"]["maxLength"] == 100


if __name__ == "__main__":
    pytest.main([__file__])
