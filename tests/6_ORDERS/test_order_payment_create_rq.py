"""
Tests for OrderPaymentCreateRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_payment_create_rq import OrderPaymentCreateRQHandler, call_order_payment_create_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderPaymentCreateRQ:
    """Test suite for OrderPaymentCreateRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderPaymentCreateRQHandler()
    
    @pytest.fixture
    def sample_payment_data(self):
        """Sample payment data for testing."""
        return {
            "order_id": "ORD123",
            "payment_method": "card",
            "amount": 150.75,
            "currency": "EUR",
            "description": "Hotel reservation payment",
            "payment_date": "2024-01-15T10:30:00",
            "removed": False
        }
    
    @pytest.fixture
    def sample_tpv_token(self):
        """Sample TPV token data."""
        return {
            "tpv_system": "redsys",
            "payer_token": "PT123456789",
            "operation_token": "OT987654321",
            "operation_schema": "OS456789123",
            "pan": "1234"
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
    def mock_payment_response(self):
        """Mock payment creation response."""
        return {
            "Payment": {
                "DateCreated": "2024-01-15T10:30:00Z",
                "Method": "card",
                "Quantity": 150.75,
                "Currency": "EUR",
                "Description": "Hotel reservation payment",
                "Removed": False
            },
            "TokenTpv": {
                "Tpv": "redsys",
                "NeoToken": {
                    "PayerToken": "PT123456789",
                    "OperationToken": "OT987654321",
                    "OperationSchema": "OS456789123",
                    "Pan": "1234"
                }
            },
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_with_token(self, handler, sample_payment_data, sample_tpv_token, mock_auth_response, mock_payment_response):
        """Test successful payment creation with TPV token."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_payment_response]
            
            arguments = {
                **sample_payment_data,
                "tpv_token": sample_tpv_token,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["order_id"] == "ORD123"
            assert result["data"]["payment_summary"]["amount"] == 150.75
            assert result["data"]["payment_summary"]["currency"] == "EUR"
            assert result["data"]["created_payment"]["Method"] == "card"
            assert result["data"]["created_token"]["Tpv"] == "redsys"
            assert "Successfully created payment" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_without_token(self, handler, sample_payment_data, mock_auth_response):
        """Test successful payment creation without TPV token."""
        payment_response = {
            "Payment": {
                "DateCreated": "2024-01-15T10:30:00Z",
                "Method": "card",
                "Quantity": 150.75,
                "Currency": "EUR",
                "Description": "Hotel reservation payment",
                "Removed": False
            },
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
        
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, payment_response]
            
            arguments = {
                **sample_payment_data,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["created_token"] == {}
    
    @pytest.mark.asyncio
    async def test_execute_missing_order_id(self, handler):
        """Test execution with missing order ID."""
        arguments = {
            "payment_method": "card",
            "amount": 150.75,
            "currency": "EUR",
            "description": "Payment",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Order ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_amount(self, handler):
        """Test execution with invalid amount."""
        arguments = {
            "order_id": "ORD123",
            "payment_method": "card",
            "amount": -50.0,  # Negative amount
            "currency": "EUR",
            "description": "Payment",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must be a positive number" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_currency(self, handler):
        """Test execution with invalid currency."""
        arguments = {
            "order_id": "ORD123",
            "payment_method": "card",
            "amount": 150.75,
            "currency": "EURO",  # Invalid format
            "description": "Payment",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "valid 3-letter ISO code" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_payment_date(self, handler):
        """Test execution with invalid payment date."""
        arguments = {
            "order_id": "ORD123",
            "payment_method": "card",
            "amount": 150.75,
            "currency": "EUR",
            "description": "Payment",
            "payment_date": "invalid-date",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid payment date format" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_payment_create_success(self, sample_payment_data):
        """Test the MCP tool handler for successful payment creation."""
        with patch('tools.ctorders.order_payment_create_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "order_id": "ORD123",
                    "created_payment": {
                        "DateCreated": "2024-01-15T10:30:00Z",
                        "Method": "card",
                        "Quantity": 150.75,
                        "Currency": "EUR",
                        "Description": "Hotel reservation payment",
                        "Removed": False
                    },
                    "created_token": {
                        "Tpv": "redsys",
                        "NeoToken": {
                            "PayerToken": "PT123456789",
                            "OperationToken": "OT987654321"
                        }
                    },
                    "payment_summary": {
                        "method": "card",
                        "amount": 150.75,
                        "currency": "EUR",
                        "description": "Hotel reservation payment",
                        "date": "2024-01-15T10:30:00Z",
                        "removed": False
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully created payment for order ORD123"
            }
            
            arguments = sample_payment_data
            result = await call_order_payment_create_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Payment Created Successfully" in response_text
            assert "Order ID: ORD123" in response_text
            assert "Payment Method: card" in response_text
            assert "Amount: 150.75 EUR" in response_text
            assert "TPV Token Information" in response_text
    
    @pytest.mark.asyncio
    async def test_call_payment_create_failure(self):
        """Test the MCP tool handler for failed payment creation."""
        with patch('tools.ctorders.order_payment_create_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Order not found",
                "error": {"code": "404", "details": "Order ORD999 does not exist"}
            }
            
            arguments = {"order_id": "ORD999", "payment_method": "card", "amount": 100, "currency": "EUR", "description": "Test"}
            result = await call_order_payment_create_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Payment Creation Failed" in response_text
            assert "Order not found" in response_text
