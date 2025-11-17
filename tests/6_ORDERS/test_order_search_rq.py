"""
Tests for OrderSearchRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_search_rq import OrderSearchRQHandler, call_order_search_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderSearchRQ:
    """Test suite for OrderSearchRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderSearchRQHandler()
    
    @pytest.fixture
    def sample_search_params(self):
        """Sample search parameters."""
        return {
            "hotel_ids": ["H123", "H456"],
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "date_by": "creationdate",
            "order_by": "creationdate",
            "order_type": "desc",
            "page": 1,
            "num_results": 10
        }
    
    @pytest.fixture
    def sample_filters(self):
        """Sample filter parameters."""
        return {
            "order_states": ["confirm"],
            "payment_states": ["partial", "pending"],
            "payment_methods": ["card", "paypal"],
            "reviewed": True,
            "notification_status": "pending"
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
    def mock_search_response(self):
        """Mock order search response."""
        return {
            "CurrentPage": 1,
            "TotalPages": 3,
            "TotalRecords": 25,
            "OrderBasicDetail": [
                {
                    "OrderId": "ORD123",
                    "OrderIdOrigin": "BK123",
                    "Origin": "booking.com",
                    "OriginAds": "google_ads",
                    "OrderStatusDetail": {
                        "OrderState": "confirm",
                        "PaymentState": "partial",
                        "PaymentMethod": "card",
                        "NoShow": False,
                        "PaymentType": "deposit",
                        "CreationDate": "2024-01-15T09:00:00Z"
                    },
                    "AmountsDetail": {
                        "Currency": "EUR",
                        "AmountTotal": 250.00,
                        "AmountFinal": 225.00
                    },
                    "CustomerDetail": {
                        "Firstname": "John",
                        "Surname": "Doe",
                        "Email": "john.doe@example.com"
                    },
                    "HotelRoomSummaryBasicDetail": [
                        {
                            "ArrivalDate": "2024-02-01",
                            "DepartureDate": "2024-02-05",
                            "HotelRoomBasicDetail": {
                                "HotelId": "H123",
                                "HotelRoomId": "R456",
                                "HotelRoomName": "Deluxe Room"
                            }
                        }
                    ],
                    "HasProducts": False,
                    "HasPackets": False,
                    "ExternalSystem": [],
                    "Tracking": {
                        "Origin": "googlehpa",
                        "Code": "TR123"
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
    async def test_execute_success_basic(self, handler, sample_search_params, mock_auth_response, mock_search_response):
        """Test successful order search with basic parameters."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            arguments = {
                **sample_search_params,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["pagination_info"]["current_page"] == 1
            assert result["data"]["pagination_info"]["total_pages"] == 3
            assert result["data"]["pagination_info"]["total_records"] == 25
            assert len(result["data"]["orders"]) == 1
            assert result["data"]["orders"][0]["order_id"] == "ORD123"
            assert "Found 25 orders" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_with_filters(self, handler, sample_search_params, sample_filters, mock_auth_response, mock_search_response):
        """Test successful order search with filters."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            arguments = {
                **sample_search_params,
                "filters": sample_filters,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["filters_applied"] is not None
            filter_by = result["data"]["search_criteria"]["filters_applied"]
            assert "OrderState" in filter_by
            assert "PaymentState" in filter_by
            assert "Reviewed" in filter_by
            assert "Notified" in filter_by
    
    @pytest.mark.asyncio
    async def test_execute_minimal_params(self, handler, mock_auth_response, mock_search_response):
        """Test execution with minimal required parameters."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            arguments = {
                "order_by": "creationdate",
                "order_type": "desc",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["sorting"]["order_by"] == "creationdate"
            assert result["data"]["search_criteria"]["sorting"]["order_type"] == "desc"
    
    @pytest.mark.asyncio
    async def test_execute_invalid_date_range(self, handler):
        """Test execution with invalid date range."""
        arguments = {
            "date_from": "2024-01-31",
            "date_to": "2024-01-01",  # End before start
            "order_by": "creationdate",
            "order_type": "desc",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "date_from cannot be later than date_to" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_date_format(self, handler):
        """Test execution with invalid date format."""
        arguments = {
            "date_from": "invalid-date",
            "order_by": "creationdate",
            "order_type": "desc",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid date format" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_excessive_date_range(self, handler):
        """Test execution with excessive date range."""
        arguments = {
            "date_from": "2020-01-01",
            "date_to": "2024-01-01",  # More than 2 years
            "order_by": "creationdate",
            "order_type": "desc",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Date range cannot exceed 2 years" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_order_search_success(self, sample_search_params):
        """Test the MCP tool handler for successful order search."""
        with patch('tools.ctorders.order_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "search_criteria": {
                        "hotel_ids": ["H123", "H456"],
                        "order_ids": [],
                        "date_range": {
                            "from": "2024-01-01",
                            "to": "2024-01-31",
                            "filter_by": "creationdate"
                        },
                        "sorting": {
                            "order_by": "creationdate",
                            "order_type": "desc"
                        },
                        "pagination": {
                            "page": 1,
                            "num_results": 10
                        },
                        "filters_applied": None
                    },
                    "pagination_info": {
                        "current_page": 1,
                        "total_pages": 3,
                        "total_records": 25,
                        "results_per_page": 10,
                        "results_returned": 10
                    },
                    "orders": [
                        {
                            "order_id": "ORD123",
                            "order_id_origin": "BK123",
                            "origin": "booking.com",
                            "order_status": {
                                "OrderState": "confirm",
                                "PaymentState": "partial"
                            },
                            "amounts": {
                                "AmountTotal": 250.00,
                                "Currency": "EUR"
                            },
                            "customer": {
                                "Firstname": "John",
                                "Surname": "Doe"
                            },
                            "room_summaries": [{"arrival_date": "2024-02-01"}],
                            "has_products": False,
                            "has_packets": False
                        }
                    ],
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Found 25 orders, returning page 1 of 3"
            }
            
            arguments = sample_search_params
            result = await call_order_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Search Results" in response_text
            assert "Total Records Found: 25" in response_text
            assert "Current Page: 1 of 3" in response_text
            assert "ORD123" in response_text
            assert "Status: confirm | Payment: partial" in response_text
            assert "Amount: 250.0 EUR" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_search_no_results(self):
        """Test the MCP tool handler when no orders are found."""
        with patch('tools.ctorders.order_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "search_criteria": {
                        "hotel_ids": [],
                        "order_ids": [],
                        "date_range": {"from": None, "to": None, "filter_by": "creationdate"},
                        "sorting": {"order_by": "creationdate", "order_type": "desc"},
                        "pagination": {"page": 1, "num_results": 10},
                        "filters_applied": None
                    },
                    "pagination_info": {
                        "current_page": 1,
                        "total_pages": 0,
                        "total_records": 0,
                        "results_per_page": 10,
                        "results_returned": 0
                    },
                    "orders": [],
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Found 0 orders, returning page 1 of 0"
            }
            
            arguments = {"order_by": "creationdate", "order_type": "desc"}
            result = await call_order_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Search Results" in response_text
            assert "Total Records Found: 0" in response_text
            assert "No orders found matching the search criteria" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_search_failure(self):
        """Test the MCP tool handler for failed order search."""
        with patch('tools.ctorders.order_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid search parameters",
                "error": {"code": "400", "details": "Date range too large"}
            }
            
            arguments = {"order_by": "creationdate", "order_type": "desc"}
            result = await call_order_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Search Failed" in response_text
            assert "Invalid search parameters" in response_text
