"""
Tests for OrderCancelRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_cancel_rq import OrderCancelRQHandler, call_order_cancel_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderCancelRQ:
    """Test suite for OrderCancelRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderCancelRQHandler()
    
    @pytest.fixture
    def sample_order_ids(self):
        """Sample order IDs for testing."""
        return ["ORD123456", "ORD789012"]
    
    @pytest.fixture
    def sample_cancellation_reason(self):
        """Sample cancellation reason."""
        return "Customer requested cancellation due to change in travel plans"
    
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
    def mock_cancel_response(self):
        """Mock order cancellation response."""
        return {
            "OrdersCancelled": ["ORD123456", "ORD789012"],
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_single_order(self, handler, mock_auth_response, mock_cancel_response):
        """Test successful cancellation of a single order."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock successful cancellation of single order
            single_cancel_response = {
                "OrdersCancelled": ["ORD123456"],
                "Response": mock_cancel_response["Response"]
            }
            mock_client.post.side_effect = [mock_auth_response, single_cancel_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "reason": "Customer requested cancellation",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["cancellation_summary"]["total_requested"] == 1
            assert result["data"]["cancellation_summary"]["total_cancelled"] == 1
            assert result["data"]["cancellation_summary"]["success_rate"] == 100.0
            assert "ORD123456" in result["data"]["cancelled_order_ids"]
            assert result["data"]["cancellation_reason"] == "Customer requested cancellation"
            assert "Successfully cancelled 1 of 1 order(s)" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_multiple_orders(self, handler, sample_order_ids, sample_cancellation_reason, mock_auth_response, mock_cancel_response):
        """Test successful cancellation of multiple orders."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_cancel_response]
            
            arguments = {
                "order_ids": sample_order_ids,
                "reason": sample_cancellation_reason,
                "avoid_send_client_email": True,
                "avoid_send_establishment_email": False,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["cancellation_summary"]["total_requested"] == 2
            assert result["data"]["cancellation_summary"]["total_cancelled"] == 2
            assert result["data"]["cancellation_summary"]["success_rate"] == 100.0
            assert set(result["data"]["cancelled_order_ids"]) == set(sample_order_ids)
            assert result["data"]["email_settings"]["client_email_avoided"] is True
            assert result["data"]["email_settings"]["establishment_email_avoided"] is False
            assert "Successfully cancelled 2 of 2 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_partial_success(self, handler, mock_auth_response):
        """Test partial cancellation success (some orders cancelled, some not)."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock partial success - only one order cancelled
            partial_cancel_response = {
                "OrdersCancelled": ["ORD123456"],  # Only first order cancelled
                "Response": {
                    "StatusCode": 200,
                    "RequestId": "REQ456",
                    "Timestamp": "2024-01-15T10:30:05Z",
                    "TimeResponse": 200
                }
            }
            mock_client.post.side_effect = [mock_auth_response, partial_cancel_response]
            
            arguments = {
                "order_ids": ["ORD123456", "ORD789012"],
                "reason": "Customer requested cancellation",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["cancellation_summary"]["total_requested"] == 2
            assert result["data"]["cancellation_summary"]["total_cancelled"] == 1
            assert result["data"]["cancellation_summary"]["success_rate"] == 50.0
            assert "ORD123456" in result["data"]["cancelled_order_ids"]
            assert "ORD789012" not in result["data"]["cancelled_order_ids"]
            assert "Successfully cancelled 1 of 2 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_order_ids(self, handler):
        """Test validation error for empty order IDs."""
        arguments = {
            "order_ids": [],
            "reason": "Customer requested cancellation",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one order ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_reason(self, handler):
        """Test validation error for empty cancellation reason."""
        arguments = {
            "order_ids": ["ORD123456"],
            "reason": "",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Cancellation reason is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_reason_too_long(self, handler):
        """Test validation error for overly long cancellation reason."""
        long_reason = "A" * 501  # Exceeds 500 character limit
        
        arguments = {
            "order_ids": ["ORD123456"],
            "reason": long_reason,
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must not exceed 500 characters" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_order_id(self, handler):
        """Test validation error for invalid order ID format."""
        arguments = {
            "order_ids": ["", "  ", "VALID123"],
            "reason": "Customer requested cancellation",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must be a non-empty string" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_too_many_orders(self, handler):
        """Test validation error for too many orders."""
        # Create list with more than 100 orders
        too_many_orders = [f"ORD{i:06d}" for i in range(101)]
        
        arguments = {
            "order_ids": too_many_orders,
            "reason": "Bulk cancellation",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        # Should fail due to maxItems validation in schema or custom validation
    
    @pytest.mark.asyncio
    async def test_call_order_cancel_success(self, sample_order_ids, sample_cancellation_reason):
        """Test the MCP tool handler for successful order cancellation."""
        with patch('tools.ctorders.order_cancel_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": sample_order_ids,
                    "cancelled_order_ids": sample_order_ids,
                    "cancellation_reason": sample_cancellation_reason,
                    "email_settings": {
                        "client_email_avoided": False,
                        "establishment_email_avoided": False
                    },
                    "cancellation_summary": {
                        "total_requested": 2,
                        "total_cancelled": 2,
                        "success_rate": 100.0
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully cancelled 2 of 2 order(s)"
            }
            
            arguments = {
                "order_ids": sample_order_ids,
                "reason": sample_cancellation_reason
            }
            result = await call_order_cancel_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Cancellation Completed" in response_text
            assert "Total Orders Requested: 2" in response_text
            assert "Successfully Cancelled: 2" in response_text
            assert "Success Rate: 100.0%" in response_text
            assert "ORD123456" in response_text
            assert "ORD789012" in response_text
            assert "CANCELLED" in response_text
            assert sample_cancellation_reason in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_cancel_partial_success(self):
        """Test the MCP tool handler for partial cancellation success."""
        with patch('tools.ctorders.order_cancel_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "requested_order_ids": ["ORD123456", "ORD789012"],
                    "cancelled_order_ids": ["ORD123456"],  # Only one cancelled
                    "cancellation_reason": "Customer request",
                    "email_settings": {
                        "client_email_avoided": False,
                        "establishment_email_avoided": False
                    },
                    "cancellation_summary": {
                        "total_requested": 2,
                        "total_cancelled": 1,
                        "success_rate": 50.0
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Successfully cancelled 1 of 2 order(s)"
            }
            
            arguments = {
                "order_ids": ["ORD123456", "ORD789012"],
                "reason": "Customer request"
            }
            result = await call_order_cancel_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Cancellation Completed" in response_text
            assert "Success Rate: 50.0%" in response_text
            assert "CANCELLED" in response_text
            assert "NOT CANCELLED" in response_text
            assert "Partially Successful Cancellation" in response_text
            assert "ORD789012" in response_text  # Should be in failed orders list
    
    @pytest.mark.asyncio
    async def test_call_order_cancel_failure(self):
        """Test the MCP tool handler for failed order cancellation."""
        with patch('tools.ctorders.order_cancel_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid order IDs provided",
                "error": {"code": "400", "details": "Order not found"}
            }
            
            arguments = {
                "order_ids": ["INVALID123"],
                "reason": "Customer request"
            }
            result = await call_order_cancel_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Cancellation Failed" in response_text
            assert "Invalid order IDs provided" in response_text
            assert "Troubleshooting" in response_text
