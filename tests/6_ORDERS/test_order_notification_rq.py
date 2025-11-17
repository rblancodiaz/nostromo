"""
Tests for OrderNotificationRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_notification_rq import OrderNotificationRQHandler, call_order_notification_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderNotificationRQ:
    """Test suite for OrderNotificationRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderNotificationRQHandler()
    
    @pytest.fixture
    def sample_order_ids(self):
        """Sample order IDs for testing."""
        return ["ORD123456", "ORD789012"]
    
    @pytest.fixture
    def sample_destination_system(self):
        """Sample destination system for testing."""
        return "PMS_SYSTEM"
    
    @pytest.fixture
    def sample_destination_user(self):
        """Sample destination user for testing."""
        return "admin_user"
    
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
        """Mock order notification response."""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_basic_notification(self, handler, sample_order_ids, mock_auth_response, mock_notification_response):
        """Test successful basic notification creation."""
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
            assert result["data"]["notified_order_ids"] == sample_order_ids
            assert result["data"]["destination_system"] == ""
            assert result["data"]["destination_user"] == ""
            assert result["data"]["notification_summary"]["total_orders"] == 2
            assert result["data"]["notification_summary"]["has_specific_system"] is False
            assert result["data"]["notification_summary"]["has_specific_user"] is False
            assert result["data"]["notification_summary"]["notification_type"] == "broadcast"
            assert "Successfully created notifications for 2 order(s)" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_with_destination_system(self, handler, sample_order_ids, sample_destination_system, mock_auth_response, mock_notification_response):
        """Test successful notification with destination system."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "destination_system": sample_destination_system,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["destination_system"] == sample_destination_system
            assert result["data"]["notification_summary"]["has_specific_system"] is True
            assert result["data"]["notification_summary"]["notification_type"] == "targeted"
            
            # Verify request payload includes destination system
            call_args = mock_client.post.call_args_list[1][0][1]  # Second call (notification request)
            assert call_args["DestinationSystem"] == sample_destination_system
    
    @pytest.mark.asyncio
    async def test_execute_success_with_destination_user(self, handler, sample_order_ids, sample_destination_user, mock_auth_response, mock_notification_response):
        """Test successful notification with destination user."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "destination_user": sample_destination_user,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["destination_user"] == sample_destination_user
            assert result["data"]["notification_summary"]["has_specific_user"] is True
            assert result["data"]["notification_summary"]["notification_type"] == "targeted"
            
            # Verify request payload includes destination user
            call_args = mock_client.post.call_args_list[1][0][1]  # Second call (notification request)
            assert call_args["DestinationUser"] == sample_destination_user
    
    @pytest.mark.asyncio
    async def test_execute_success_with_both_destinations(self, handler, sample_order_ids, sample_destination_system, sample_destination_user, mock_auth_response, mock_notification_response):
        """Test successful notification with both destination system and user."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "destination_system": sample_destination_system,
                "destination_user": sample_destination_user,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["destination_system"] == sample_destination_system
            assert result["data"]["destination_user"] == sample_destination_user
            assert result["data"]["notification_summary"]["has_specific_system"] is True
            assert result["data"]["notification_summary"]["has_specific_user"] is True
            assert result["data"]["notification_summary"]["notification_type"] == "targeted"
            
            # Verify request payload includes both destinations
            call_args = mock_client.post.call_args_list[1][0][1]  # Second call (notification request)
            assert call_args["DestinationSystem"] == sample_destination_system
            assert call_args["DestinationUser"] == sample_destination_user
    
    @pytest.mark.asyncio
    async def test_execute_single_order(self, handler, mock_auth_response, mock_notification_response):
        """Test notification creation for single order."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["notified_order_ids"] == ["ORD123456"]
            assert result["data"]["notification_summary"]["total_orders"] == 1
            assert "Successfully created notifications for 1 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_order_ids(self, handler):
        """Test validation error for empty order IDs."""
        arguments = {
            "order_ids": [],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one order ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_order_id(self, handler):
        """Test validation error for invalid order ID."""
        arguments = {
            "order_ids": ["", "  ", "VALID123"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must be a non-empty string" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_destination_system_too_long(self, handler):
        """Test validation error for overly long destination system."""
        long_system = "A" * 101  # Exceeds 100 character limit
        
        arguments = {
            "order_ids": ["ORD123456"],
            "destination_system": long_system,
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must not exceed 100 characters" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_destination_user_too_long(self, handler):
        """Test validation error for overly long destination user."""
        long_user = "A" * 101  # Exceeds 100 character limit
        
        arguments = {
            "order_ids": ["ORD123456"],
            "destination_user": long_user,
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must not exceed 100 characters" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_with_whitespace_destinations(self, handler, sample_order_ids, mock_auth_response, mock_notification_response):
        """Test handling of destinations with whitespace."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "destination_system": "  PMS_SYSTEM  ",
                "destination_user": "  admin_user  ",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            # Should be trimmed
            assert result["data"]["destination_system"] == "PMS_SYSTEM"
            assert result["data"]["destination_user"] == "admin_user"
    
    @pytest.mark.asyncio
    async def test_execute_with_empty_destinations(self, handler, sample_order_ids, mock_auth_response, mock_notification_response):
        """Test handling of empty destination strings."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "destination_system": "",
                "destination_user": "   ",  # Only whitespace
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["destination_system"] == ""
            assert result["data"]["destination_user"] == ""
            assert result["data"]["notification_summary"]["notification_type"] == "broadcast"
            
            # Verify request payload doesn't include empty destinations
            call_args = mock_client.post.call_args_list[1][0][1]  # Second call (notification request)
            assert "DestinationSystem" not in call_args
            assert "DestinationUser" not in call_args
    
    @pytest.mark.asyncio
    async def test_validate_order_ids(self, handler):
        """Test order ID validation."""
        # Valid order IDs
        valid_ids = ["ORD123", "ORD456"]
        validated = handler._validate_order_ids(valid_ids)
        assert validated == valid_ids
        
        # Empty list should raise error
        with pytest.raises(ValidationError):
            handler._validate_order_ids([])
        
        # Invalid order IDs should raise error
        with pytest.raises(ValidationError):
            handler._validate_order_ids(["", "valid"])
    
    @pytest.mark.asyncio
    async def test_call_order_notification_success_broadcast(self, sample_order_ids):
        """Test the MCP tool handler for successful broadcast notification."""
        with patch('tools.ctorders.order_notification_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "notified_order_ids": sample_order_ids,
                    "destination_system": "",
                    "destination_user": "",
                    "notification_summary": {
                        "total_orders": 2,
                        "has_specific_system": False,
                        "has_specific_user": False,
                        "notification_type": "broadcast"
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully created notifications for 2 order(s)"
            }
            
            arguments = {
                "order_ids": sample_order_ids
            }
            result = await call_order_notification_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Notification Creation Successful" in response_text
            assert "Orders Notified: 2" in response_text
            assert "Notification Type: Broadcast" in response_text
            assert "Target System: All systems" in response_text
            assert "Target User: All users" in response_text
            assert "ORD123456: ✅ NOTIFIED" in response_text
            assert "ORD789012: ✅ NOTIFIED" in response_text
            assert "Broadcast Notification:" in response_text
            assert "Maximum reach and visibility" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_notification_success_targeted(self, sample_order_ids, sample_destination_system, sample_destination_user):
        """Test the MCP tool handler for successful targeted notification."""
        with patch('tools.ctorders.order_notification_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "notified_order_ids": sample_order_ids,
                    "destination_system": sample_destination_system,
                    "destination_user": sample_destination_user,
                    "notification_summary": {
                        "total_orders": 2,
                        "has_specific_system": True,
                        "has_specific_user": True,
                        "notification_type": "targeted"
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully created notifications for 2 order(s)"
            }
            
            arguments = {
                "order_ids": sample_order_ids,
                "destination_system": sample_destination_system,
                "destination_user": sample_destination_user
            }
            result = await call_order_notification_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Notification Creation Successful" in response_text
            assert "Notification Type: Targeted" in response_text
            assert f"Target System: {sample_destination_system}" in response_text
            assert f"Target User: {sample_destination_user}" in response_text
            assert f"Destination System: {sample_destination_system}" in response_text
            assert f"Destination User: {sample_destination_user}" in response_text
            assert "Targeted Notification:" in response_text
            assert "Focused communication" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_notification_failure(self):
        """Test the MCP tool handler for failed notification creation."""
        with patch('tools.ctorders.order_notification_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid order IDs provided",
                "error": {"code": "400", "details": "Order ORD999 not found"}
            }
            
            arguments = {
                "order_ids": ["ORD999"]
            }
            result = await call_order_notification_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Notification Creation Failed" in response_text
            assert "Invalid order IDs provided" in response_text
            assert "Troubleshooting" in response_text
            assert "Common Issues" in response_text
    
    @pytest.mark.asyncio
    async def test_execute_many_orders(self, handler, mock_auth_response, mock_notification_response):
        """Test notification creation for many orders."""
        many_orders = [f"ORD{i:06d}" for i in range(50)]
        
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_notification_response]
            
            arguments = {
                "order_ids": many_orders,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["notification_summary"]["total_orders"] == 50
            assert len(result["data"]["notified_order_ids"]) == 50
            assert "Successfully created notifications for 50 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_authentication_error(self, handler, sample_order_ids):
        """Test handling of authentication error."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock failed authentication
            auth_response_no_token = {
                "Response": {
                    "StatusCode": 401,
                    "RequestId": "REQ123",
                    "Timestamp": "2024-01-15T10:30:00Z",
                    "TimeResponse": 150
                }
            }
            mock_client.post.return_value = auth_response_no_token
            
            arguments = {
                "order_ids": sample_order_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
