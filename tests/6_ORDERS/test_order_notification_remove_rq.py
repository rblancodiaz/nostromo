"""
Tests for OrderNotificationRemoveRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_notification_remove_rq import OrderNotificationRemoveRQHandler, call_order_notification_remove_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderNotificationRemoveRQ:
    """Test suite for OrderNotificationRemoveRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderNotificationRemoveRQHandler()
    
    @pytest.fixture
    def sample_order_ids(self):
        """Sample order IDs for testing."""
        return ["ORD123", "ORD456"]
    
    @pytest.fixture
    def mock_auth_response(self):
        """Mock authentication response."""
        return {
            "Token": "test_token_12345",
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ123",
                "Timestamp": "2024-01-15T10:30:00Z",
                "TimeResponse": 150
            }
        }
    
    @pytest.fixture
    def mock_remove_response(self):
        """Mock notification removal response."""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success(self, handler, sample_order_ids, mock_auth_response, mock_remove_response):
        """Test successful notification removal."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_remove_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "destination_system": "booking_system",
                "destination_user": "admin",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["processed_order_ids"] == sample_order_ids
            assert result["data"]["removal_scope"]["destination_system"] == "booking_system"
            assert result["data"]["removal_scope"]["destination_user"] == "admin"
            assert result["data"]["removal_scope"]["specific_targeting"] is True
            assert "Successfully removed notifications" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_global_removal(self, handler, sample_order_ids, mock_auth_response, mock_remove_response):
        """Test global notification removal (no specific system/user)."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_remove_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["removal_scope"]["destination_system"] == "All systems"
            assert result["data"]["removal_scope"]["destination_user"] == "All users"
            assert result["data"]["removal_scope"]["specific_targeting"] is False
            assert result["data"]["removal_summary"]["removal_type"] == "Global"
    
    @pytest.mark.asyncio
    async def test_execute_empty_order_ids(self, handler):
        """Test execution with empty order IDs list."""
        arguments = {
            "order_ids": [],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one order ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_destination_system(self, handler, sample_order_ids):
        """Test execution with invalid destination system."""
        arguments = {
            "order_ids": sample_order_ids,
            "destination_system": "x" * 101,  # Exceeds max length
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "exceeds maximum length" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_notification_remove_success(self, sample_order_ids):
        """Test the MCP tool handler for successful notification removal."""
        with patch('tools.ctorders.order_notification_remove_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "processed_order_ids": sample_order_ids,
                    "removal_scope": {
                        "destination_system": "booking_system",
                        "destination_user": "admin",
                        "specific_targeting": True
                    },
                    "removal_summary": {
                        "total_orders": 2,
                        "removal_type": "Targeted"
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully removed notifications for 2 order(s)"
            }
            
            arguments = {"order_ids": sample_order_ids}
            result = await call_order_notification_remove_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Notifications Removed Successfully" in response_text
            assert "Total Orders Processed: 2" in response_text
            assert "Removal Type: Targeted" in response_text
            assert "ORD123" in response_text
    
    @pytest.mark.asyncio
    async def test_call_notification_remove_failure(self):
        """Test the MCP tool handler for failed notification removal."""
        with patch('tools.ctorders.order_notification_remove_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Order not found",
                "error": {"code": "404", "details": "Order ORD999 does not exist"}
            }
            
            arguments = {"order_ids": ["ORD999"]}
            result = await call_order_notification_remove_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Notification Removal Failed" in response_text
            assert "Order not found" in response_text
