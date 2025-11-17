"""
Tests for AuthenticatorRQ tool.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Import the modules to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from tools.authenticator_rq import AuthenticatorRQHandler, call_authenticator_rq
from config import ValidationError, AuthenticationError, APIError


@pytest.fixture
def handler():
    """Create a handler instance for testing."""
    return AuthenticatorRQHandler()


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    with patch('tools.authenticator_rq.NeobookingsConfig') as mock:
        config = Mock()
        config.client_code = "neo"
        config.system_code = "XML"
        config.username = "neomcp"
        config.password = "ECtIOnSPhepO"
        config.base_url = "https://ws-test.neobookings.com/api/v2"
        config.timeout = 30
        mock.from_env.return_value = config
        yield config


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing."""
    with patch('tools.authenticator_rq.NeobookingsHTTPClient') as mock:
        client = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client)
        mock.return_value.__aexit__ = AsyncMock(return_value=None)
        yield client


class TestAuthenticatorRQHandler:
    """Tests for the AuthenticatorRQHandler class."""
    
    @pytest.mark.asyncio
    async def test_execute_success_default_language(self, handler, mock_config, mock_http_client):
        """Test successful authentication with default language."""
        # Setup mock response
        mock_response = {
            "Token": "abc123def456",
            "Response": {
                "StatusCode": 200,
                "RequestId": "test-request-id",
                "Timestamp": "2024-01-01T12:00:00Z",
                "TimeResponse": 150
            }
        }
        mock_http_client.post.return_value = mock_response
        
        # Execute the handler
        result = await handler.execute({})
        
        # Verify the result
        assert result["success"] is True
        assert "Authentication successful" in result["message"]
        assert result["data"]["token"] == "abc123def456"
        assert result["data"]["language"] == "es"
        assert result["data"]["session_info"]["client_code"] == "neo"
        
        # Verify the API call was made correctly
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "/AuthenticatorRQ"
        assert call_args[1]["require_auth"] is False
        
        # Verify request structure
        request_data = call_args[0][1]
        assert "Request" in request_data
        assert "Credentials" in request_data
        assert request_data["Request"]["Language"] == "es"
        assert request_data["Credentials"]["ClientCode"] == "neo"
    
    @pytest.mark.asyncio
    async def test_execute_success_custom_language(self, handler, mock_config, mock_http_client):
        """Test successful authentication with custom language."""
        # Setup mock response
        mock_response = {
            "Token": "xyz789uvw012",
            "Response": {
                "StatusCode": 200,
                "RequestId": "test-request-id-2",
                "Timestamp": "2024-01-01T12:00:00Z"
            }
        }
        mock_http_client.post.return_value = mock_response
        
        # Execute with custom language
        result = await handler.execute({"language": "en"})
        
        # Verify the result
        assert result["success"] is True
        assert result["data"]["language"] == "en"
        
        # Verify the request was made with correct language
        call_args = mock_http_client.post.call_args
        request_data = call_args[0][1]
        assert request_data["Request"]["Language"] == "en"
    
    @pytest.mark.asyncio
    async def test_execute_invalid_language(self, handler, mock_config):
        """Test authentication with invalid language code."""
        result = await handler.execute({"language": "invalid"})
        
        assert result["success"] is False
        assert "Invalid language code" in result["message"]
        assert result["error"]["error_code"] == "VALIDATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_execute_no_token_in_response(self, handler, mock_config, mock_http_client):
        """Test authentication when no token is returned."""
        # Setup mock response without token
        mock_response = {
            "Response": {
                "StatusCode": 200,
                "RequestId": "test-request-id",
                "Timestamp": "2024-01-01T12:00:00Z"
            }
        }
        mock_http_client.post.return_value = mock_response
        
        result = await handler.execute({})
        
        assert result["success"] is False
        assert "No authentication token received" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_api_error(self, handler, mock_config, mock_http_client):
        """Test authentication with API error."""
        # Setup mock to raise API error
        mock_http_client.post.side_effect = APIError("Connection failed", "API_ERROR")
        
        result = await handler.execute({})
        
        assert result["success"] is False
        assert "API error" in result["message"]
        assert "Connection failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_authentication_error(self, handler, mock_config, mock_http_client):
        """Test authentication with authentication error."""
        # Setup mock to raise authentication error
        mock_http_client.post.side_effect = AuthenticationError("Invalid credentials", "AUTH_ERROR")
        
        result = await handler.execute({})
        
        assert result["success"] is False
        assert "Authentication failed" in result["message"]
        assert "Invalid credentials" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_unexpected_error(self, handler, mock_config, mock_http_client):
        """Test authentication with unexpected error."""
        # Setup mock to raise unexpected error
        mock_http_client.post.side_effect = Exception("Unexpected error")
        
        result = await handler.execute({})
        
        assert result["success"] is False
        assert "Unexpected error" in result["message"]


class TestCallAuthenticatorRQ:
    """Tests for the call_authenticator_rq function."""
    
    @pytest.mark.asyncio
    async def test_call_success(self, mock_config):
        """Test successful tool call."""
        with patch('tools.authenticator_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "message": "Authentication successful",
                "data": {
                    "token": "test-token-123456789",
                    "language": "es",
                    "request_metadata": {
                        "RequestId": "test-id",
                        "Timestamp": "2024-01-01T12:00:00Z"
                    },
                    "session_info": {
                        "base_url": "https://ws-test.neobookings.com/api/v2",
                        "client_code": "neo",
                        "system_code": "XML",
                        "username": "neomcp"
                    },
                    "api_response": {
                        "TimeResponse": 150
                    }
                }
            }
            
            result = await call_authenticator_rq({"language": "es"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Authentication Successful" in result[0].text
            assert "test-token-123456789" in result[0].text
            assert "150ms" in result[0].text
    
    @pytest.mark.asyncio
    async def test_call_failure(self, mock_config):
        """Test failed tool call."""
        with patch('tools.authenticator_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Authentication failed: Invalid credentials",
                "error": {
                    "error_code": "AUTH_ERROR",
                    "details": {}
                }
            }
            
            result = await call_authenticator_rq({"language": "es"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Authentication Failed" in result[0].text
            assert "Invalid credentials" in result[0].text
    
    @pytest.mark.asyncio
    async def test_call_exception(self, mock_config):
        """Test tool call with exception."""
        with patch('tools.authenticator_rq.handler') as mock_handler:
            mock_handler.execute.side_effect = Exception("Test exception")
            
            result = await call_authenticator_rq({})
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Tool Execution Error" in result[0].text
            assert "Test exception" in result[0].text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
