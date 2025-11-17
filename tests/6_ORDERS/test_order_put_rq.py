"""
Tests for OrderPutRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_put_rq import OrderPutRQHandler, call_order_put_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderPutRQ:
    """Test suite for OrderPutRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderPutRQHandler()
    
    @pytest.fixture
    def sample_order_data(self):
        """Sample order data for testing."""
        return {
            "order_id": "ORD123",
            "origin": "booking.com",
            "provider": "booking_provider",
            "order_status": {
                "order_state": "confirm",
                "payment_state": "partial",
                "payment_method": "card",
                "no_show": False,
                "payment_type": "deposit",
                "when_pay": "now"
            }
        }
    
    @pytest.fixture
    def sample_customer_data(self):
        """Sample customer data."""
        return {
            "title": "Mr",
            "firstname": "John",
            "surname": "Doe",
            "date_of_birthday": "1980-01-15",
            "address": "123 Main St",
            "zip": "12345",
            "city": "Barcelona",
            "country": "ES",
            "phone": "+34123456789",
            "email": "john.doe@example.com",
            "passport": "P123456789",
            "state": "Catalonia"
        }
    
    @pytest.fixture
    def sample_amounts_data(self):
        """Sample amounts data."""
        return {
            "currency": "EUR",
            "amount_final": 250.00,
            "amount_total": 275.00,
            "amount_base": 200.00,
            "amount_taxes": 50.00,
            "amount_tourist_tax": 25.00
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
    def mock_put_response(self):
        """Mock order put response."""
        return {
            "OrderId": ["ORD123_CREATED"],
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_minimal(self, handler, sample_order_data, mock_auth_response, mock_put_response):
        """Test successful order put with minimal data."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_put_response]
            
            arguments = {
                **sample_order_data,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["input_order_id"] == "ORD123"
            assert result["data"]["created_order_ids"] == ["ORD123_CREATED"]
            assert result["data"]["operation_summary"]["origin"] == "booking.com"
            assert result["data"]["operation_summary"]["provider"] == "booking_provider"
            assert "Successfully processed order" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_complete(self, handler, sample_order_data, sample_customer_data, sample_amounts_data, mock_auth_response, mock_put_response):
        """Test successful order put with complete data."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_put_response]
            
            arguments = {
                **sample_order_data,
                "customer_data": sample_customer_data,
                "amounts_data": sample_amounts_data,
                "room_data": [
                    {
                        "arrival_date": "2024-02-01",
                        "departure_date": "2024-02-05",
                        "hotel_room_detail": {
                            "hotel_id": "H123",
                            "hotel_room_id": "R456",
                            "hotel_room_name": "Deluxe Room",
                            "hotel_room_description": "Luxury room with sea view"
                        }
                    }
                ],
                "billing_data": {
                    "name": "John Doe Company",
                    "cif": "B12345678",
                    "address": "Business St 456",
                    "zip": "08001",
                    "city": "Barcelona",
                    "country": "ES"
                },
                "petitions": "Late check-in requested",
                "first_payment": 125.00,
                "info_client": "VIP customer",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["operation_summary"]["has_customer_data"] is True
            assert result["data"]["operation_summary"]["has_amounts_data"] is True
            assert result["data"]["operation_summary"]["has_billing_data"] is True
            assert result["data"]["operation_summary"]["has_room_data"] is True
    
    @pytest.mark.asyncio
    async def test_execute_missing_required_fields(self, handler):
        """Test execution with missing required fields."""
        arguments = {
            "order_id": "ORD123",
            # Missing origin, provider, order_status
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Origin is required" in result["message"] or "Provider is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_order_status(self, handler):
        """Test execution with invalid order status."""
        arguments = {
            "order_id": "ORD123",
            "origin": "booking.com",
            "provider": "booking_provider",
            "order_status": {
                # Missing order_state
                "payment_state": "partial"
            },
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Order state is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_date_format(self, handler, sample_order_data):
        """Test execution with invalid date format in room data."""
        arguments = {
            **sample_order_data,
            "room_data": [
                {
                    "arrival_date": "invalid-date",
                    "departure_date": "2024-02-05"
                }
            ],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid date format" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_order_put_success(self, sample_order_data):
        """Test the MCP tool handler for successful order put."""
        with patch('tools.ctorders.order_put_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "input_order_id": "ORD123",
                    "created_order_ids": ["ORD123_CREATED"],
                    "order_details": {
                        "OrderId": "ORD123",
                        "Origin": "booking.com",
                        "Provider": "booking_provider"
                    },
                    "operation_summary": {
                        "origin": "booking.com",
                        "provider": "booking_provider",
                        "order_state": "confirm",
                        "has_customer_data": True,
                        "has_amounts_data": False,
                        "has_billing_data": False,
                        "has_room_data": True
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully processed order ORD123 - Created order IDs: ORD123_CREATED"
            }
            
            arguments = sample_order_data
            result = await call_order_put_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Processing Completed" in response_text
            assert "Input Order ID: ORD123" in response_text
            assert "Origin: booking.com" in response_text
            assert "ORD123_CREATED" in response_text
            assert "Customer Data: ✅ Yes" in response_text
            assert "Room Data: ✅ Yes" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_put_failure(self):
        """Test the MCP tool handler for failed order put."""
        with patch('tools.ctorders.order_put_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid order data",
                "error": {"code": "400", "details": "Order ID already exists"}
            }
            
            arguments = {"order_id": "ORD123", "origin": "test", "provider": "test", "order_status": {"order_state": "confirm"}}
            result = await call_order_put_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Processing Failed" in response_text
            assert "Invalid order data" in response_text
