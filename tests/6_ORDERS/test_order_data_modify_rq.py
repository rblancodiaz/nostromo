"""
Tests for OrderDataModifyRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_data_modify_rq import OrderDataModifyRQHandler, call_order_data_modify_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderDataModifyRQ:
    """Test suite for OrderDataModifyRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderDataModifyRQHandler()
    
    @pytest.fixture
    def sample_order_ids(self):
        """Sample order IDs for testing."""
        return ["ORD123456", "ORD789012"]
    
    @pytest.fixture
    def sample_payment_method(self):
        """Sample payment method modification."""
        return {
            "credit_card": True,
            "card_details": {
                "number": "4111111111111111",
                "holder_name": "John Doe",
                "expiry_month": 12,
                "expiry_year": 2025,
                "cvv": "123"
            }
        }
    
    @pytest.fixture
    def sample_customer_data(self):
        """Sample customer data modification."""
        return {
            "firstname": "John",
            "surname": "Doe",
            "email": "john.doe@updated.com",
            "phone": "+34666777888",
            "address": "Updated Address 123",
            "city": "Updated City",
            "zip": "28001",
            "country": "es"
        }
    
    @pytest.fixture
    def sample_billing_data(self):
        """Sample billing data modification."""
        return {
            "name": "Updated Company SL",
            "cif": "B12345678",
            "address": "Updated Billing Address",
            "zip": "28001",
            "city": "Madrid",
            "country": "Spain"
        }
    
    @pytest.fixture
    def sample_guest_data(self):
        """Sample guest data modification."""
        return [
            {
                "id": "GUEST001",
                "firstname": "Jane",
                "surname": "Smith",
                "email": "jane.smith@updated.com",
                "date_of_birthday": "1990-05-15"
            }
        ]
    
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
    def mock_modify_response(self):
        """Mock order data modification response."""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_payment_method_update(self, handler, sample_payment_method, mock_auth_response, mock_modify_response):
        """Test successful payment method update."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_modify_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "payment_method": sample_payment_method,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["requested_order_ids"]) == 1
            assert result["data"]["requested_order_ids"][0] == "ORD123456"
            assert result["data"]["modifications"]["payment_method_updated"] is True
            assert "Successfully modified data for 1 order(s)" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_customer_data_update(self, handler, sample_customer_data, mock_auth_response, mock_modify_response):
        """Test successful customer data update."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_modify_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "customer_data": sample_customer_data,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["modifications"]["customer_data_updated"] is True
            assert result["data"]["modifications"]["payment_method_updated"] is False
            assert "Successfully modified data for 1 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_success_comprehensive_update(self, handler, sample_customer_data, sample_billing_data, sample_guest_data, mock_auth_response, mock_modify_response):
        """Test comprehensive data update with multiple fields."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_modify_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "customer_data": sample_customer_data,
                "billing_data": sample_billing_data,
                "guest_data": sample_guest_data,
                "language": "en",
                "special_requests": "Updated special requests",
                "info_client": "Updated client information",
                "info_hotel": "Updated hotel information",
                "avoid_send_client_email": True,
                "avoid_send_establishment_email": False,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["modifications"]["customer_data_updated"] is True
            assert result["data"]["modifications"]["billing_data_updated"] is True
            assert result["data"]["modifications"]["guest_data_updated"] is True
            assert result["data"]["modifications"]["special_requests_updated"] is True
            assert result["data"]["modifications"]["info_client_updated"] is True
            assert result["data"]["modifications"]["info_hotel_updated"] is True
            assert result["data"]["email_settings"]["client_email_avoided"] is True
            assert result["data"]["email_settings"]["establishment_email_avoided"] is False
    
    @pytest.mark.asyncio
    async def test_execute_success_multiple_orders(self, handler, sample_order_ids, sample_customer_data, mock_auth_response, mock_modify_response):
        """Test successful modification of multiple orders."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_modify_response, mock_modify_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "customer_data": sample_customer_data,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["requested_order_ids"]) == 2
            assert set(result["data"]["requested_order_ids"]) == set(sample_order_ids)
            assert "Successfully modified data for 2 order(s)" in result["message"]
            
            # Should have made 3 API calls (1 auth + 2 modify)
            assert mock_client.post.call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_order_ids(self, handler):
        """Test validation error for empty order IDs."""
        arguments = {
            "order_ids": [],
            "customer_data": {"firstname": "John"},
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one order ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_no_modifications(self, handler):
        """Test validation error when no modifications are provided."""
        arguments = {
            "order_ids": ["ORD123456"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one modification field is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_email(self, handler):
        """Test validation error for invalid email format."""
        arguments = {
            "order_ids": ["ORD123456"],
            "customer_data": {"email": "invalid-email"},
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid email format" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_country_code(self, handler):
        """Test validation error for invalid country code."""
        arguments = {
            "order_ids": ["ORD123456"],
            "customer_data": {"country": "invalid"},
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid country code" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_card_number(self, handler):
        """Test validation error for invalid credit card number."""
        invalid_payment_method = {
            "credit_card": True,
            "card_details": {
                "number": "invalid-card-number",
                "holder_name": "John Doe",
                "expiry_month": 12,
                "expiry_year": 2025
            }
        }
        
        arguments = {
            "order_ids": ["ORD123456"],
            "payment_method": invalid_payment_method,
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid credit card number" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_order_data_modify_success(self, sample_order_ids, sample_customer_data):
        """Test the MCP tool handler for successful order data modification."""
        with patch('tools.ctorders.order_data_modify_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": sample_order_ids,
                    "modifications": {
                        "customer_data_updated": True,
                        "billing_data_updated": False,
                        "payment_method_updated": False,
                        "guest_data_updated": False,
                        "special_requests_updated": False,
                        "info_client_updated": False,
                        "info_hotel_updated": False,
                        "language_updated": False
                    },
                    "email_settings": {
                        "client_email_avoided": False,
                        "establishment_email_avoided": False
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully modified data for 2 order(s)"
            }
            
            arguments = {
                "order_ids": sample_order_ids,
                "customer_data": sample_customer_data
            }
            result = await call_order_data_modify_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Data Modification Completed" in response_text
            assert "Successfully Modified Orders: 2" in response_text
            assert "ORD123456" in response_text
            assert "ORD789012" in response_text
            assert "Customer Data: ✅ Updated" in response_text
            assert "Payment Method: ⏸️ No changes" in response_text
            assert "Billing Data: ⏸️ No changes" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_data_modify_comprehensive(self):
        """Test the MCP tool handler for comprehensive modification."""
        with patch('tools.ctorders.order_data_modify_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": ["ORD123456"],
                    "modifications": {
                        "customer_data_updated": True,
                        "billing_data_updated": True,
                        "payment_method_updated": True,
                        "guest_data_updated": True,
                        "special_requests_updated": True,
                        "info_client_updated": True,
                        "info_hotel_updated": True,
                        "language_updated": True
                    },
                    "email_settings": {
                        "client_email_avoided": True,
                        "establishment_email_avoided": True
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully modified data for 1 order(s)"
            }
            
            arguments = {"order_ids": ["ORD123456"]}
            result = await call_order_data_modify_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Data Modification Completed" in response_text
            assert "Customer Data: ✅ Updated" in response_text
            assert "Billing Data: ✅ Updated" in response_text
            assert "Payment Method: ✅ Updated" in response_text
            assert "Guest Data: ✅ Updated" in response_text
            assert "Client Email: Avoided" in response_text
            assert "Establishment Email: Avoided" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_data_modify_failure(self):
        """Test the MCP tool handler for failed order data modification."""
        with patch('tools.ctorders.order_data_modify_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid modification data provided",
                "error": {"code": "400", "details": "Invalid email format"}
            }
            
            arguments = {
                "order_ids": ["ORD123456"],
                "customer_data": {"email": "invalid-email"}
            }
            result = await call_order_data_modify_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Data Modification Failed" in response_text
            assert "Invalid modification data provided" in response_text
            assert "Troubleshooting" in response_text
