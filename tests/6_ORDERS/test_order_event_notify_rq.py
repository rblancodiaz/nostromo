"""
Tests for OrderEventNotifyRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_event_notify_rq import OrderEventNotifyRQHandler, call_order_event_notify_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderEventNotifyRQ:
    """Test suite for OrderEventNotifyRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderEventNotifyRQHandler()
    
    @pytest.fixture
    def sample_order_id(self):
        """Sample order ID for testing."""
        return "ORD123456"
    
    @pytest.fixture
    def sample_event_data(self):
        """Sample event data for testing."""
        return {
            "event_type": "BOOKING_MODIFY_CREDITCARD",
            "event_info": "Credit card information updated for booking",
            "event_date": "2024-01-15T10:30:00Z"
        }
    
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
    def mock_event_notify_response(self):
        """Mock event notification response."""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_booking_modify(self, handler, sample_order_id, mock_auth_response, mock_event_notify_response):
        """Test successful booking modification event notification."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_event_notify_response]
            
            arguments = {
                "order_id": sample_order_id,
                "event_type": "BOOKING_MODIFY_CREDITCARD",
                "event_info": "Credit card information updated for booking",
                "event_date": "2024-01-15T10:30:00Z",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["order_id"] == sample_order_id
            assert result["data"]["event_type"] == "BOOKING_MODIFY_CREDITCARD"
            assert result["data"]["event_info"] == "Credit card information updated for booking"
            assert result["data"]["event_date"] == "2024-01-15T10:30:00Z"
            assert "Event notification sent successfully" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_payment_event(self, handler, sample_order_id, mock_auth_response, mock_event_notify_response):
        """Test successful payment event notification."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_event_notify_response]
            
            arguments = {
                "order_id": sample_order_id,
                "event_type": "PAYMENT_MANUAL_OK",
                "event_info": "Manual payment processed successfully",
                "event_date": "2024-01-15T11:00:00Z",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["event_type"] == "PAYMENT_MANUAL_OK"
            assert result["data"]["event_info"] == "Manual payment processed successfully"
            assert "Event notification sent successfully" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_success_cancellation_event(self, handler, sample_order_id, mock_auth_response, mock_event_notify_response):
        """Test successful cancellation event notification."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_event_notify_response]
            
            arguments = {
                "order_id": sample_order_id,
                "event_type": "CANCEL_MANUAL",
                "event_info": "Booking cancelled manually by staff",
                "event_date": "2024-01-15T12:00:00Z",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["event_type"] == "CANCEL_MANUAL"
            assert result["data"]["event_info"] == "Booking cancelled manually by staff"
            assert "Event notification sent successfully" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_success_with_current_time(self, handler, sample_order_id, mock_auth_response, mock_event_notify_response):
        """Test successful event notification with current timestamp."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_event_notify_response]
            
            arguments = {
                "order_id": sample_order_id,
                "event_type": "SEND_EMAIL_USER",
                "event_info": "Confirmation email sent to customer",
                "language": "es"
                # No event_date provided - should use current time
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["event_type"] == "SEND_EMAIL_USER"
            assert result["data"]["event_date"] is not None  # Should be auto-generated
            assert "Event notification sent successfully" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_order_id(self, handler):
        """Test validation error for empty order ID."""
        arguments = {
            "order_id": "",
            "event_type": "CONFIRM",
            "event_info": "Booking confirmed",
            "event_date": "2024-01-15T10:30:00Z",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Order ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_event_type(self, handler, sample_order_id):
        """Test validation error for invalid event type."""
        arguments = {
            "order_id": sample_order_id,
            "event_type": "INVALID_EVENT_TYPE",
            "event_info": "Some event occurred",
            "event_date": "2024-01-15T10:30:00Z",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid event type" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_event_type(self, handler, sample_order_id):
        """Test validation error for empty event type."""
        arguments = {
            "order_id": sample_order_id,
            "event_type": "",
            "event_info": "Some event occurred",
            "event_date": "2024-01-15T10:30:00Z",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Event type is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_date_format(self, handler, sample_order_id):
        """Test validation error for invalid date format."""
        arguments = {
            "order_id": sample_order_id,
            "event_type": "CONFIRM",
            "event_info": "Booking confirmed",
            "event_date": "invalid-date-format",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid date format" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_long_event_info(self, handler, sample_order_id):
        """Test validation error for overly long event info."""
        long_event_info = "A" * 1001  # Exceeds 1000 character limit
        
        arguments = {
            "order_id": sample_order_id,
            "event_type": "CONFIRM",
            "event_info": long_event_info,
            "event_date": "2024-01-15T10:30:00Z",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must not exceed 1000 characters" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_authentication_error(self, handler, sample_order_id):
        """Test authentication error handling."""
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
                "order_id": sample_order_id,
                "event_type": "CONFIRM",
                "event_info": "Booking confirmed",
                "event_date": "2024-01-15T10:30:00Z",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_order_event_notify_success(self, sample_order_id, sample_event_data):
        """Test the MCP tool handler for successful event notification."""
        with patch('tools.ctorders.order_event_notify_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "order_id": sample_order_id,
                    "event_type": sample_event_data["event_type"],
                    "event_info": sample_event_data["event_info"],
                    "event_date": sample_event_data["event_date"],
                    "notification_status": "sent",
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Event notification sent successfully for order ORD123456"
            }
            
            arguments = {
                "order_id": sample_order_id,
                "event_type": sample_event_data["event_type"],
                "event_info": sample_event_data["event_info"],
                "event_date": sample_event_data["event_date"]
            }
            result = await call_order_event_notify_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Event Notification Sent" in response_text
            assert "ORD123456" in response_text
            assert "BOOKING_MODIFY_CREDITCARD" in response_text
            assert "Credit card information updated for booking" in response_text
            assert "2024-01-15T10:30:00Z" in response_text
            assert "Status: ✅ Sent" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_event_notify_multiple_event_types(self):
        """Test the MCP tool handler showing different event type descriptions."""
        with patch('tools.ctorders.order_event_notify_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "order_id": "ORD123456",
                    "event_type": "PAYMENT_AUTO_OK",
                    "event_info": "Automatic payment processed successfully",
                    "event_date": "2024-01-15T10:30:00Z",
                    "notification_status": "sent",
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Event notification sent successfully for order ORD123456"
            }
            
            arguments = {
                "order_id": "ORD123456",
                "event_type": "PAYMENT_AUTO_OK",
                "event_info": "Automatic payment processed successfully"
            }
            result = await call_order_event_notify_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Event Notification Sent" in response_text
            assert "PAYMENT_AUTO_OK" in response_text
            assert "💳 Payment Processing" in response_text  # Should show payment category
    
    @pytest.mark.asyncio
    async def test_call_order_event_notify_failure(self):
        """Test the MCP tool handler for failed event notification."""
        with patch('tools.ctorders.order_event_notify_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid event type provided",
                "error": {"code": "400", "details": "Event type not recognized"}
            }
            
            arguments = {
                "order_id": "ORD123456",
                "event_type": "INVALID_EVENT",
                "event_info": "Invalid event"
            }
            result = await call_order_event_notify_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Event Notification Failed" in response_text
            assert "Invalid event type provided" in response_text
            assert "Troubleshooting" in response_text
            assert "Valid Event Types" in response_text
