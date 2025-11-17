"""
Tests for OrderEventSearchRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_event_search_rq import OrderEventSearchRQHandler, call_order_event_search_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderEventSearchRQ:
    """Test suite for OrderEventSearchRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderEventSearchRQHandler()
    
    @pytest.fixture
    def sample_hotel_ids(self):
        """Sample hotel IDs for testing."""
        return ["H123", "H456"]
    
    @pytest.fixture
    def sample_event_types(self):
        """Sample event types for testing."""
        return ["CONFIRM", "PAYMENT_AUTO_OK", "CANCEL_MANUAL"]
    
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
        """Mock order event search response."""
        return {
            "ReservationIds": ["ORD123456", "ORD789012", "ORD555777"],
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 300
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_basic_search(self, handler, sample_hotel_ids, sample_event_types, mock_auth_response, mock_search_response):
        """Test successful basic order event search."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            arguments = {
                "hotel_ids": sample_hotel_ids,
                "event_types": sample_event_types,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["hotel_ids"] == sample_hotel_ids
            assert result["data"]["search_criteria"]["event_types"] == sample_event_types
            assert result["data"]["found_order_ids"] == ["ORD123456", "ORD789012", "ORD555777"]
            assert result["data"]["search_summary"]["hotels_searched"] == 2
            assert result["data"]["search_summary"]["event_types_searched"] == 3
            assert result["data"]["search_summary"]["orders_found"] == 3
            assert result["data"]["search_summary"]["date_range_used"] is False
            assert "Found 3 order(s) with specified events" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_with_date_range(self, handler, sample_hotel_ids, sample_event_types, mock_auth_response, mock_search_response):
        """Test successful search with date range."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            arguments = {
                "hotel_ids": sample_hotel_ids,
                "event_types": sample_event_types,
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "date_type": "dateEvent",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["date_from"] == "2024-01-01"
            assert result["data"]["search_criteria"]["date_to"] == "2024-01-31"
            assert result["data"]["search_criteria"]["date_type"] == "dateEvent"
            assert result["data"]["search_criteria"]["date_type_description"] == "Event occurrence date"
            assert result["data"]["search_summary"]["date_range_used"] is True
            
            # Verify request payload includes date parameters
            call_args = mock_client.post.call_args_list[1][0][1]  # Second call (search request)
            assert call_args["DateFrom"] == "2024-01-01"
            assert call_args["DateTo"] == "2024-01-31"
            assert call_args["DateType"] == "dateEvent"
    
    @pytest.mark.asyncio
    async def test_execute_success_no_results(self, handler, sample_hotel_ids, sample_event_types, mock_auth_response):
        """Test successful search with no results."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            empty_search_response = {
                "ReservationIds": [],
                "Response": {
                    "StatusCode": 200,
                    "RequestId": "REQ456",
                    "Timestamp": "2024-01-15T10:30:05Z",
                    "TimeResponse": 150
                }
            }
            mock_client.post.side_effect = [mock_auth_response, empty_search_response]
            
            arguments = {
                "hotel_ids": sample_hotel_ids,
                "event_types": sample_event_types,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["found_order_ids"] == []
            assert result["data"]["search_summary"]["orders_found"] == 0
            assert "Found 0 order(s) with specified events" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_single_hotel_single_event(self, handler, mock_auth_response, mock_search_response):
        """Test search with single hotel and event type."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            arguments = {
                "hotel_ids": ["H123"],
                "event_types": ["PAYMENT_AUTO_OK"],
                "date_type": "dateArrival",
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["hotel_ids"] == ["H123"]
            assert result["data"]["search_criteria"]["event_types"] == ["PAYMENT_AUTO_OK"]
            assert result["data"]["search_criteria"]["date_type"] == "dateArrival"
            assert result["data"]["search_criteria"]["date_type_description"] == "Reservation arrival date"
            assert result["data"]["search_summary"]["hotels_searched"] == 1
            assert result["data"]["search_summary"]["event_types_searched"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_hotel_ids(self, handler):
        """Test validation error for empty hotel IDs."""
        arguments = {
            "hotel_ids": [],
            "event_types": ["CONFIRM"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one hotel ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_event_types(self, handler):
        """Test validation error for empty event types."""
        arguments = {
            "hotel_ids": ["H123"],
            "event_types": [],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one event type is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_hotel_id(self, handler):
        """Test validation error for invalid hotel ID."""
        arguments = {
            "hotel_ids": ["", "  ", "VALID123"],
            "event_types": ["CONFIRM"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must be a non-empty string" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_event_type(self, handler):
        """Test validation error for invalid event type."""
        arguments = {
            "hotel_ids": ["H123"],
            "event_types": ["INVALID_EVENT_TYPE"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "is not a valid event type" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_date_format(self, handler):
        """Test validation error for invalid date format."""
        arguments = {
            "hotel_ids": ["H123"],
            "event_types": ["CONFIRM"],
            "date_from": "2024/01/01",  # Wrong format
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_date_range_invalid(self, handler):
        """Test validation error for invalid date range."""
        arguments = {
            "hotel_ids": ["H123"],
            "event_types": ["CONFIRM"],
            "date_from": "2024-01-31",
            "date_to": "2024-01-01",  # End before start
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Date from must be before date to" in result["message"]
    
    @pytest.mark.asyncio
    async def test_validate_event_types_removes_duplicates(self, handler):
        """Test that duplicate event types are removed."""
        event_types = ["CONFIRM", "PAYMENT_AUTO_OK", "CONFIRM", "PAYMENT_AUTO_OK"]
        validated_types = handler._validate_event_types(event_types)
        
        assert len(validated_types) == 2
        assert set(validated_types) == {"CONFIRM", "PAYMENT_AUTO_OK"}
    
    @pytest.mark.asyncio
    async def test_validate_event_types_case_normalization(self, handler):
        """Test that event types are normalized to uppercase."""
        event_types = ["confirm", "payment_auto_ok", "CANCEL_MANUAL"]
        validated_types = handler._validate_event_types(event_types)
        
        assert "CONFIRM" in validated_types
        assert "PAYMENT_AUTO_OK" in validated_types
        assert "CANCEL_MANUAL" in validated_types
    
    @pytest.mark.asyncio
    async def test_get_event_type_description(self, handler):
        """Test event type description mapping."""
        assert handler._get_event_type_description("CONFIRM") == "Reservation confirmed"
        assert handler._get_event_type_description("PAYMENT_AUTO_OK") == "Automatic payment successful"
        assert handler._get_event_type_description("CANCEL_MANUAL") == "Manual cancellation"
        assert handler._get_event_type_description("UNKNOWN_EVENT") == "UNKNOWN_EVENT"
    
    @pytest.mark.asyncio
    async def test_get_date_type_description(self, handler):
        """Test date type description mapping."""
        assert handler._get_date_type_description("dateEvent") == "Event occurrence date"
        assert handler._get_date_type_description("dateArrival") == "Reservation arrival date"
        assert handler._get_date_type_description("dateDeparture") == "Reservation departure date"
        assert handler._get_date_type_description("dateCreation") == "Reservation creation date"
        assert handler._get_date_type_description("unknown") == "unknown"
    
    @pytest.mark.asyncio
    async def test_call_order_event_search_success(self, sample_hotel_ids, sample_event_types):
        """Test the MCP tool handler for successful search."""
        with patch('tools.ctorders.order_event_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "search_criteria": {
                        "hotel_ids": sample_hotel_ids,
                        "event_types": sample_event_types,
                        "event_type_descriptions": [
                            "Reservation confirmed",
                            "Automatic payment successful", 
                            "Manual cancellation"
                        ],
                        "date_from": "2024-01-01",
                        "date_to": "2024-01-31",
                        "date_type": "dateEvent",
                        "date_type_description": "Event occurrence date"
                    },
                    "found_order_ids": ["ORD123456", "ORD789012"],
                    "search_summary": {
                        "hotels_searched": 2,
                        "event_types_searched": 3,
                        "orders_found": 2,
                        "date_range_used": True
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 300}
                },
                "message": "Found 2 order(s) with specified events"
            }
            
            arguments = {
                "hotel_ids": sample_hotel_ids,
                "event_types": sample_event_types,
                "date_from": "2024-01-01",
                "date_to": "2024-01-31"
            }
            result = await call_order_event_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Event Search Results" in response_text
            assert "Hotels Searched: 2" in response_text
            assert "Event Types: 3" in response_text
            assert "Orders Found: 2" in response_text
            assert "H123" in response_text
            assert "H456" in response_text
            assert "CONFIRM" in response_text
            assert "PAYMENT_AUTO_OK" in response_text
            assert "CANCEL_MANUAL" in response_text
            assert "ORD123456" in response_text
            assert "ORD789012" in response_text
            assert "Event occurrence date" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_event_search_no_results(self):
        """Test the MCP tool handler for search with no results."""
        with patch('tools.ctorders.order_event_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "search_criteria": {
                        "hotel_ids": ["H123"],
                        "event_types": ["PAYMENT_AUTO_OK"],
                        "event_type_descriptions": ["Automatic payment successful"],
                        "date_from": None,
                        "date_to": None,
                        "date_type": "dateEvent",
                        "date_type_description": "Event occurrence date"
                    },
                    "found_order_ids": [],
                    "search_summary": {
                        "hotels_searched": 1,
                        "event_types_searched": 1,
                        "orders_found": 0,
                        "date_range_used": False
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 150}
                },
                "message": "Found 0 order(s) with specified events"
            }
            
            arguments = {
                "hotel_ids": ["H123"],
                "event_types": ["PAYMENT_AUTO_OK"]
            }
            result = await call_order_event_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Event Search Results" in response_text
            assert "Orders Found: 0" in response_text
            assert "No Orders Found" in response_text
            assert "Possible reasons:" in response_text
            assert "Suggestions:" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_event_search_failure(self):
        """Test the MCP tool handler for failed search."""
        with patch('tools.ctorders.order_event_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid hotel IDs provided",
                "error": {"code": "400", "details": "Hotel H999 not found"}
            }
            
            arguments = {
                "hotel_ids": ["H999"],
                "event_types": ["CONFIRM"]
            }
            result = await call_order_event_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Event Search Failed" in response_text
            assert "Invalid hotel IDs provided" in response_text
            assert "Troubleshooting" in response_text
            assert "Valid Event Types" in response_text
