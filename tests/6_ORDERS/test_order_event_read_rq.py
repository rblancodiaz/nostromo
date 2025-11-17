"""
Tests for OrderEventReadRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_event_read_rq import OrderEventReadRQHandler, call_order_event_read_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderEventReadRQ:
    """Test suite for OrderEventReadRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderEventReadRQHandler()
    
    @pytest.fixture
    def sample_order_ids(self):
        """Sample order IDs for testing."""
        return ["ORD123456", "ORD789012"]
    
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
    def mock_event_read_response(self):
        """Mock order event read response."""
        return {
            "ReservationEvent": [
                {
                    "OrderId": "ORD123456",
                    "EventType": "CONFIRM",
                    "EventInfo": "Booking confirmed successfully",
                    "EventDate": "2024-01-15T09:00:00Z"
                },
                {
                    "OrderId": "ORD123456",
                    "EventType": "SEND_EMAIL_USER",
                    "EventInfo": "Confirmation email sent to customer",
                    "EventDate": "2024-01-15T09:01:00Z"
                },
                {
                    "OrderId": "ORD123456",
                    "EventType": "PAYMENT_MANUAL_OK",
                    "EventInfo": "Manual payment processed successfully",
                    "EventDate": "2024-01-15T09:05:00Z"
                },
                {
                    "OrderId": "ORD789012",
                    "EventType": "CONFIRM",
                    "EventInfo": "Booking confirmed successfully",
                    "EventDate": "2024-01-15T10:00:00Z"
                },
                {
                    "OrderId": "ORD789012",
                    "EventType": "TOKENIZE_AUTO_OK",
                    "EventInfo": "Credit card tokenization completed",
                    "EventDate": "2024-01-15T10:01:00Z"
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
    async def test_execute_success_single_order(self, handler, mock_auth_response):
        """Test successful retrieval of events for single order."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            single_order_response = {
                "ReservationEvent": [
                    {
                        "OrderId": "ORD123456",
                        "EventType": "CONFIRM",
                        "EventInfo": "Booking confirmed successfully",
                        "EventDate": "2024-01-15T09:00:00Z"
                    },
                    {
                        "OrderId": "ORD123456",
                        "EventType": "SEND_EMAIL_USER",
                        "EventInfo": "Confirmation email sent to customer",
                        "EventDate": "2024-01-15T09:01:00Z"
                    }
                ],
                "Response": {
                    "StatusCode": 200,
                    "RequestId": "REQ456",
                    "Timestamp": "2024-01-15T10:30:05Z",
                    "TimeResponse": 200
                }
            }
            mock_client.post.side_effect = [mock_auth_response, single_order_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["events"]) == 2
            assert result["data"]["summary"]["total_orders"] == 1
            assert result["data"]["summary"]["total_events"] == 2
            
            # Check first event
            event1 = result["data"]["events"][0]
            assert event1["order_id"] == "ORD123456"
            assert event1["event_type"] == "CONFIRM"
            assert event1["event_info"] == "Booking confirmed successfully"
            assert event1["event_date"] == "2024-01-15T09:00:00Z"
            
            # Check second event
            event2 = result["data"]["events"][1]
            assert event2["order_id"] == "ORD123456"
            assert event2["event_type"] == "SEND_EMAIL_USER"
            assert event2["event_info"] == "Confirmation email sent to customer"
            
            assert "Retrieved 2 events for 1 order(s)" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_multiple_orders(self, handler, sample_order_ids, mock_auth_response, mock_event_read_response):
        """Test successful retrieval of events for multiple orders."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_event_read_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["events"]) == 5
            assert result["data"]["summary"]["total_orders"] == 2
            assert result["data"]["summary"]["total_events"] == 5
            
            # Check events distribution
            ord123_events = [e for e in result["data"]["events"] if e["order_id"] == "ORD123456"]
            ord789_events = [e for e in result["data"]["events"] if e["order_id"] == "ORD789012"]
            
            assert len(ord123_events) == 3
            assert len(ord789_events) == 2
            
            # Check event types for first order
            ord123_event_types = [e["event_type"] for e in ord123_events]
            assert "CONFIRM" in ord123_event_types
            assert "SEND_EMAIL_USER" in ord123_event_types
            assert "PAYMENT_MANUAL_OK" in ord123_event_types
            
            # Check event types for second order
            ord789_event_types = [e["event_type"] for e in ord789_events]
            assert "CONFIRM" in ord789_event_types
            assert "TOKENIZE_AUTO_OK" in ord789_event_types
            
            assert "Retrieved 5 events for 2 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_no_events_found(self, handler, mock_auth_response):
        """Test when no events are found for the orders."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            empty_response = {
                "ReservationEvent": [],
                "Response": {
                    "StatusCode": 200,
                    "RequestId": "REQ456",
                    "Timestamp": "2024-01-15T10:30:05Z",
                    "TimeResponse": 200
                }
            }
            mock_client.post.side_effect = [mock_auth_response, empty_response]
            
            arguments = {
                "order_ids": ["ORD999999"],
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["events"]) == 0
            assert result["data"]["summary"]["total_orders"] == 1
            assert result["data"]["summary"]["total_events"] == 0
            assert "No events found" in result["message"]
    
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
        """Test validation error for invalid order ID format."""
        arguments = {
            "order_ids": ["", "  ", "VALID123"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must be a non-empty string" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_authentication_error(self, handler):
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
                "order_ids": ["ORD123456"],
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_order_event_read_success(self, sample_order_ids):
        """Test the MCP tool handler for successful event reading."""
        with patch('tools.ctorders.order_event_read_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": sample_order_ids,
                    "events": [
                        {
                            "order_id": "ORD123456",
                            "event_type": "CONFIRM",
                            "event_info": "Booking confirmed successfully",
                            "event_date": "2024-01-15T09:00:00Z"
                        },
                        {
                            "order_id": "ORD123456",
                            "event_type": "SEND_EMAIL_USER",
                            "event_info": "Confirmation email sent to customer",
                            "event_date": "2024-01-15T09:01:00Z"
                        },
                        {
                            "order_id": "ORD123456",
                            "event_type": "PAYMENT_MANUAL_OK",
                            "event_info": "Manual payment processed successfully",
                            "event_date": "2024-01-15T09:05:00Z"
                        },
                        {
                            "order_id": "ORD789012",
                            "event_type": "CONFIRM",
                            "event_info": "Booking confirmed successfully",
                            "event_date": "2024-01-15T10:00:00Z"
                        },
                        {
                            "order_id": "ORD789012",
                            "event_type": "TOKENIZE_AUTO_OK",
                            "event_info": "Credit card tokenization completed",
                            "event_date": "2024-01-15T10:01:00Z"
                        }
                    ],
                    "summary": {
                        "total_orders": 2,
                        "total_events": 5,
                        "events_per_order": {
                            "ORD123456": 3,
                            "ORD789012": 2
                        },
                        "event_types_found": ["CONFIRM", "SEND_EMAIL_USER", "PAYMENT_MANUAL_OK", "TOKENIZE_AUTO_OK"]
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Retrieved 5 events for 2 order(s)"
            }
            
            arguments = {"order_ids": sample_order_ids}
            result = await call_order_event_read_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Events Retrieved" in response_text
            assert "Total Orders: 2" in response_text
            assert "Total Events: 5" in response_text
            assert "ORD123456" in response_text
            assert "ORD789012" in response_text
            assert "✅ CONFIRM" in response_text
            assert "📧 SEND_EMAIL_USER" in response_text
            assert "💳 PAYMENT_MANUAL_OK" in response_text
            assert "🔐 TOKENIZE_AUTO_OK" in response_text
            assert "Booking confirmed successfully" in response_text
            assert "2024-01-15T09:00:00Z" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_event_read_no_events(self):
        """Test the MCP tool handler when no events are found."""
        with patch('tools.ctorders.order_event_read_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": ["ORD999999"],
                    "events": [],
                    "summary": {
                        "total_orders": 1,
                        "total_events": 0,
                        "events_per_order": {},
                        "event_types_found": []
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "No events found for the requested orders"
            }
            
            arguments = {"order_ids": ["ORD999999"]}
            result = await call_order_event_read_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Events Retrieved" in response_text
            assert "Total Orders: 1" in response_text
            assert "Total Events: 0" in response_text
            assert "No events found" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_event_read_failure(self):
        """Test the MCP tool handler for failed event reading."""
        with patch('tools.ctorders.order_event_read_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid order IDs provided",
                "error": {"code": "400", "details": "Order not found"}
            }
            
            arguments = {"order_ids": ["INVALID123"]}
            result = await call_order_event_read_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Events Retrieval Failed" in response_text
            assert "Invalid order IDs provided" in response_text
            assert "Troubleshooting" in response_text
