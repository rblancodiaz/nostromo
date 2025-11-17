"""
Tests for BasketCreateRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tools.ctbasket.basket_create_rq import BasketCreateRQHandler, call_basket_create_rq


class TestBasketCreateRQHandler:
    """Test cases for BasketCreateRQHandler."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return BasketCreateRQHandler()
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.client_code = "neo"
        config.system_code = "XML"
        config.username = "neomcp"
        config.password = "ECtIOnSPhepO"
        return config
    
    @pytest.fixture
    def mock_successful_response(self):
        """Mock successful API response."""
        return {
            "BasketInfo": {
                "BasketId": "BSK123456",
                "BasketStatus": "open",
                "BudgetId": "BDG789",
                "OrderId": None,
                "Rewards": True
            },
            "Response": {
                "StatusCode": 200,
                "RequestId": "req-123",
                "Timestamp": "2024-01-01T10:00:00Z",
                "TimeResponse": 150
            }
        }
    
    @patch('tools.ctbasket.basket_create_rq.NeobookingsConfig.from_env')
    @patch('tools.ctbasket.basket_create_rq.NeobookingsHTTPClient')
    async def test_execute_basic_basket_creation(self, mock_client_class, mock_config_class, handler, mock_config, mock_successful_response):
        """Test basic basket creation without optional parameters."""
        # Setup mocks
        mock_config_class.return_value = mock_config
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock authentication
        mock_client.post.side_effect = [
            {"Token": "auth_token_123"},  # Authentication response
            mock_successful_response       # Basket creation response
        ]
        
        # Test arguments
        arguments = {}
        
        # Execute
        result = await handler.execute(arguments)
        
        # Assertions
        assert result["success"] is True
        assert result["message"] == "Shopping basket created successfully"
        assert result["data"]["basket_info"]["BasketId"] == "BSK123456"
        assert result["data"]["basket_info"]["BasketStatus"] == "open"
        assert result["data"]["creation_context"]["from_budget"] is False
        assert result["data"]["creation_context"]["from_order"] is False
        
        # Verify API calls
        assert mock_client.post.call_count == 2
        mock_client.set_token.assert_called_once_with("auth_token_123")
    
    @patch('tools.ctbasket.basket_create_rq.NeobookingsConfig.from_env')
    @patch('tools.ctbasket.basket_create_rq.NeobookingsHTTPClient')
    async def test_execute_with_all_optional_parameters(self, mock_client_class, mock_config_class, handler, mock_config, mock_successful_response):
        """Test basket creation with all optional parameters."""
        # Setup mocks
        mock_config_class.return_value = mock_config
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock authentication and basket creation
        mock_client.post.side_effect = [
            {"Token": "auth_token_123"},
            mock_successful_response
        ]
        
        # Test arguments with all optional fields
        arguments = {
            "client_device": "mobile",
            "origin": "website",
            "tracking": {
                "origin": "googlehpa",
                "code": "TRACK123",
                "locale": "es_ES"
            },
            "client_location": {
                "country": "ES",
                "ip": "192.168.1.1"
            },
            "budget_id": "BDG456",
            "call_center_properties": {
                "ignore_release": True,
                "override_price": 100.0
            },
            "language": "en"
        }
        
        # Execute
        result = await handler.execute(arguments)
        
        # Assertions
        assert result["success"] is True
        assert result["data"]["creation_context"]["client_device"] == "mobile"
        assert result["data"]["creation_context"]["origin"] == "website"
        assert result["data"]["creation_context"]["from_budget"] is True
        
        # Verify the API call was made with correct data
        basket_create_call = mock_client.post.call_args_list[1]
        basket_create_data = basket_create_call[0][1]
        
        assert basket_create_data["ClientDevice"] == "mobile"
        assert basket_create_data["Origin"] == "website"
        assert basket_create_data["BudgetId"] == "BDG456"
        assert "Tracking" in basket_create_data
        assert "ClientLocation" in basket_create_data
        assert "CallCenterProperties" in basket_create_data
    
    @patch('tools.ctbasket.basket_create_rq.NeobookingsConfig.from_env')
    @patch('tools.ctbasket.basket_create_rq.NeobookingsHTTPClient')
    async def test_execute_authentication_failure(self, mock_client_class, mock_config_class, handler, mock_config):
        """Test handling of authentication failure."""
        # Setup mocks
        mock_config_class.return_value = mock_config
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock failed authentication
        mock_client.post.return_value = {}  # No token in response
        
        # Test arguments
        arguments = {}
        
        # Execute
        result = await handler.execute(arguments)
        
        # Assertions
        assert result["success"] is False
        assert "Authentication failed" in result["message"]
        assert mock_client.post.call_count == 1  # Only authentication call
    
    @patch('tools.ctbasket.basket_create_rq.NeobookingsConfig.from_env')
    @patch('tools.ctbasket.basket_create_rq.NeobookingsHTTPClient')
    async def test_execute_api_error(self, mock_client_class, mock_config_class, handler, mock_config):
        """Test handling of API errors."""
        # Setup mocks
        mock_config_class.return_value = mock_config
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock authentication success but API error
        from config.base import APIError
        mock_client.post.side_effect = [
            {"Token": "auth_token_123"},
            APIError("API request failed")
        ]
        
        # Test arguments
        arguments = {}
        
        # Execute
        result = await handler.execute(arguments)
        
        # Assertions
        assert result["success"] is False
        assert "API error" in result["message"]
    
    @patch('tools.ctbasket.basket_create_rq.NeobookingsConfig.from_env')
    async def test_execute_validation_error(self, mock_config_class, handler, mock_config):
        """Test handling of validation errors."""
        # Setup mocks
        mock_config_class.return_value = mock_config
        
        # Test with invalid tracking data
        arguments = {
            "tracking": {
                "origin": "invalid_origin",  # Invalid enum value
                "code": "TRACK123"
            }
        }
        
        # Execute
        result = await handler.execute(arguments)
        
        # Assertions
        assert result["success"] is False
        assert "Validation error" in result["message"]


class TestBasketCreateRQMCPHandler:
    """Test cases for the MCP handler function."""
    
    @pytest.mark.asyncio
    async def test_call_basket_create_rq_success(self):
        """Test successful MCP handler call."""
        arguments = {"client_device": "desktop"}
        
        with patch('tools.ctbasket.basket_create_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "basket_info": {
                        "BasketId": "BSK123",
                        "BasketStatus": "open"
                    },
                    "creation_context": {
                        "client_device": "desktop",
                        "origin": None,
                        "from_budget": False,
                        "from_order": False,
                        "empty_basket": False
                    },
                    "request_metadata": {
                        "RequestId": "req-123",
                        "Timestamp": "2024-01-01T10:00:00Z"
                    },
                    "api_response": {
                        "TimeResponse": 150
                    }
                },
                "message": "Shopping basket created successfully"
            }
            
            result = await call_basket_create_rq(arguments)
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Basket Created Successfully" in result[0].text
            assert "BSK123" in result[0].text
            assert "desktop" in result[0].text
    
    @pytest.mark.asyncio
    async def test_call_basket_create_rq_failure(self):
        """Test failed MCP handler call."""
        arguments = {"invalid": "data"}
        
        with patch('tools.ctbasket.basket_create_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "error": {"error_code": "VALIDATION_ERROR"},
                "message": "Validation error: Invalid parameters"
            }
            
            result = await call_basket_create_rq(arguments)
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Failed to Create Shopping Basket" in result[0].text
            assert "Validation error" in result[0].text
    
    @pytest.mark.asyncio
    async def test_call_basket_create_rq_exception(self):
        """Test exception handling in MCP handler."""
        arguments = {}
        
        with patch('tools.ctbasket.basket_create_rq.handler') as mock_handler:
            mock_handler.execute.side_effect = Exception("Unexpected error")
            
            result = await call_basket_create_rq(arguments)
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Tool Execution Error" in result[0].text
            assert "Unexpected error" in result[0].text
