"""
Tests for OrderCreditCardRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_credit_card_rq import OrderCreditCardRQHandler, call_order_credit_card_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderCreditCardRQ:
    """Test suite for OrderCreditCardRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderCreditCardRQHandler()
    
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
    def mock_credit_card_response(self):
        """Mock credit card information response."""
        return {
            "OrderCreditCard": [
                {
                    "OrderId": "ORD123456",
                    "CreditCardType": "visa",
                    "CreditCardNumber": "**** **** **** 1234",
                    "ExpirateDateMonth": 12,
                    "ExpirateDateYear": 2025,
                    "CreditCardCode": "***",
                    "CreditCardHolder": "JOHN DOE"
                },
                {
                    "OrderId": "ORD789012",
                    "CreditCardType": "mastercard",
                    "CreditCardNumber": "**** **** **** 5678",
                    "ExpirateDateMonth": 8,
                    "ExpirateDateYear": 2026,
                    "CreditCardCode": "***",
                    "CreditCardHolder": "JANE SMITH"
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
        """Test successful retrieval of credit card info for single order."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            single_card_response = {
                "OrderCreditCard": [
                    {
                        "OrderId": "ORD123456",
                        "CreditCardType": "visa",
                        "CreditCardNumber": "**** **** **** 1234",
                        "ExpirateDateMonth": 12,
                        "ExpirateDateYear": 2025,
                        "CreditCardCode": "***",
                        "CreditCardHolder": "JOHN DOE"
                    }
                ],
                "Response": {
                    "StatusCode": 200,
                    "RequestId": "REQ456",
                    "Timestamp": "2024-01-15T10:30:05Z",
                    "TimeResponse": 200
                }
            }
            mock_client.post.side_effect = [mock_auth_response, single_card_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["credit_cards"]) == 1
            assert result["data"]["credit_cards"][0]["order_id"] == "ORD123456"
            assert result["data"]["credit_cards"][0]["card_type"] == "visa"
            assert result["data"]["credit_cards"][0]["masked_number"] == "**** **** **** 1234"
            assert result["data"]["credit_cards"][0]["expiry_month"] == 12
            assert result["data"]["credit_cards"][0]["expiry_year"] == 2025
            assert result["data"]["credit_cards"][0]["cardholder_name"] == "JOHN DOE"
            assert "Retrieved credit card information for 1 order(s)" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_multiple_orders(self, handler, sample_order_ids, mock_auth_response, mock_credit_card_response):
        """Test successful retrieval of credit card info for multiple orders."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_credit_card_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["credit_cards"]) == 2
            
            # Check first card
            card1 = result["data"]["credit_cards"][0]
            assert card1["order_id"] == "ORD123456"
            assert card1["card_type"] == "visa"
            assert card1["masked_number"] == "**** **** **** 1234"
            
            # Check second card
            card2 = result["data"]["credit_cards"][1]
            assert card2["order_id"] == "ORD789012"
            assert card2["card_type"] == "mastercard"
            assert card2["masked_number"] == "**** **** **** 5678"
            
            assert "Retrieved credit card information for 2 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_no_cards_found(self, handler, mock_auth_response):
        """Test when no credit card information is found."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            empty_response = {
                "OrderCreditCard": [],
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
            assert len(result["data"]["credit_cards"]) == 0
            assert result["data"]["summary"]["total_requested"] == 1
            assert result["data"]["summary"]["total_found"] == 0
            assert "No credit card information found" in result["message"]
    
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
    async def test_call_order_credit_card_success(self, sample_order_ids):
        """Test the MCP tool handler for successful credit card retrieval."""
        with patch('tools.ctorders.order_credit_card_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": sample_order_ids,
                    "credit_cards": [
                        {
                            "order_id": "ORD123456",
                            "card_type": "visa",
                            "masked_number": "**** **** **** 1234",
                            "expiry_month": 12,
                            "expiry_year": 2025,
                            "cvv_masked": "***",
                            "cardholder_name": "JOHN DOE"
                        },
                        {
                            "order_id": "ORD789012",
                            "card_type": "mastercard",
                            "masked_number": "**** **** **** 5678",
                            "expiry_month": 8,
                            "expiry_year": 2026,
                            "cvv_masked": "***",
                            "cardholder_name": "JANE SMITH"
                        }
                    ],
                    "summary": {
                        "total_requested": 2,
                        "total_found": 2,
                        "coverage_rate": 100.0
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Retrieved credit card information for 2 order(s)"
            }
            
            arguments = {"order_ids": sample_order_ids}
            result = await call_order_credit_card_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Credit Card Information Retrieved" in response_text
            assert "Total Orders Processed: 2" in response_text
            assert "Cards Found: 2" in response_text
            assert "Coverage Rate: 100.0%" in response_text
            assert "ORD123456" in response_text
            assert "ORD789012" in response_text
            assert "Visa" in response_text
            assert "MasterCard" in response_text
            assert "**** **** **** 1234" in response_text
            assert "**** **** **** 5678" in response_text
            assert "JOHN DOE" in response_text
            assert "JANE SMITH" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_credit_card_no_cards(self):
        """Test the MCP tool handler when no credit cards are found."""
        with patch('tools.ctorders.order_credit_card_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": ["ORD999999"],
                    "credit_cards": [],
                    "summary": {
                        "total_requested": 1,
                        "total_found": 0,
                        "coverage_rate": 0.0
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "No credit card information found for the requested orders"
            }
            
            arguments = {"order_ids": ["ORD999999"]}
            result = await call_order_credit_card_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Credit Card Information Retrieved" in response_text
            assert "Cards Found: 0" in response_text
            assert "Coverage Rate: 0.0%" in response_text
            assert "No credit card information found" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_credit_card_failure(self):
        """Test the MCP tool handler for failed credit card retrieval."""
        with patch('tools.ctorders.order_credit_card_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid order IDs provided",
                "error": {"code": "400", "details": "Order not found"}
            }
            
            arguments = {"order_ids": ["INVALID123"]}
            result = await call_order_credit_card_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Credit Card Information Retrieval Failed" in response_text
            assert "Invalid order IDs provided" in response_text
            assert "Troubleshooting" in response_text
