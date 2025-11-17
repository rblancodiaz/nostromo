"""
Tests for OrderNotificationReadRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_notification_read_rq import OrderNotificationReadRQHandler, call_order_notification_read_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderNotificationReadRQ:
    """Test suite for OrderNotificationReadRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderNotificationReadRQHandler()
    
    @pytest.fixture
    def sample_order_ids(self):
        """Sample order IDs for testing."""
        return ["ORD123", "ORD456", "ORD789"]
    
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
    def mock_notification_response(self):
        """Mock notification read response."""
        return {
            "Notification": [
                {
                    "ReservationId": "ORD123",
                    "Status": "confirmed",
                    "Date": "2024-01-15T09:00:00Z",
                    "Notified": True,
                    "System": "booking_system",
                    "User": {
                        "Username": "admin",
                        "ClientCode": "neo",
                        "System": "XML"
                    }
                },
                {
                    "ReservationId": "ORD456",
                    "Status": "pending",
                    "Date": "2024-01-15T10:00:00Z", 
                    "Notified": False,
                    "System": "booking_system",
                    "User": {
                        "Username": "user",
                        "ClientCode": "neo",
                        "System": "XML"
                    }
                }
            ],
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success(self, handler, sample_order_ids, mock_auth_response, mock_notification_response):
        """Test successful notification read."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["requested_order_ids"] == sample_order_ids
            assert len(result["data"]["notifications"]) == 2
            assert result["data"]["summary"]["notified_count"] == 1
            assert result["data"]["summary"]["pending_count"] == 1
            assert "Retrieved notification status" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
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
    async def test_execute_invalid_order_ids(self, handler):
        """Test execution with invalid order IDs."""
        arguments = {
            "order_ids": ["", "  ", None],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must be a non-empty string" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_authentication_error(self, handler, sample_order_ids):
        """Test authentication failure."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = {"Response": {"StatusCode": 401}}
            
            arguments = {
                "order_ids": sample_order_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_notification_read_success(self, sample_order_ids):
        """Test the MCP tool handler for successful notification read."""
        with patch('tools.ctorders.order_notification_read_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": sample_order_ids,
                    "notifications": [
                        {
                            "reservation_id": "ORD123",
                            "status": "confirmed",
                            "date": "2024-01-15T09:00:00Z",
                            "notified": True,
                            "system": "booking_system",
                            "user": {"Username": "admin"}
                        }
                    ],
                    "summary": {
                        "total_orders": 3,
                        "notifications_found": 1,
                        "notified_count": 1,
                        "pending_count": 0,
                        "notification_rate": 100.0
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Retrieved notification status for 1 orders"
            }
            
            arguments = {"order_ids": sample_order_ids}
            result = await call_order_notification_read_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Notification Status Retrieved" in response_text
            assert "Notification Rate: 100.0%" in response_text
            assert "ORD123" in response_text
    
    @pytest.mark.asyncio
    async def test_call_notification_read_failure(self):
        """Test the MCP tool handler for failed notification read."""
        with patch('tools.ctorders.order_notification_read_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Order not found",
                "error": {"code": "404", "details": "Order ORD999 does not exist"}
            }
            
            arguments = {"order_ids": ["ORD999"]}
            result = await call_order_notification_read_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Notification Status Read Failed" in response_text
            assert "Order not found" in response_text
