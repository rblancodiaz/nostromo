"""
Tests for BudgetSearchRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctbudget.budget_search_rq import BudgetSearchRQHandler, call_budget_search_rq
from config import ValidationError, AuthenticationError, APIError


class TestBudgetSearchRQ:
    """Test suite for BudgetSearchRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return BudgetSearchRQHandler()
    
    @pytest.fixture
    def basic_search_args(self):
        """Basic search arguments for testing."""
        return {
            "order_by": "creationdate",
            "order_type": "desc",
            "language": "es"
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
        """Mock budget search response."""
        return {
            "BudgetBasicDetail": [
                {
                    "BudgetId": "BDG123",
                    "Origin": "web",
                    "HotelId": "HTL001",
                    "RateName": "Standard Rate",
                    "BoardName": "Half Board",
                    "CreationUser": "user123",
                    "ArrivalDate": "2024-02-01",
                    "DepartureDate": "2024-02-05",
                    "Status": "pending",
                    "IsSent": True,
                    "SentDate": "2024-01-15T14:30:00",
                    "IsCopied": False,
                    "CreationDate": "2024-01-15T09:00:00Z",
                    "CustomerDetail": {
                        "Name": "Juan",
                        "Surname": "García",
                        "Email": "juan@email.com",
                        "Phone": "+34666777888",
                        "Country": "ES",
                        "City": "Madrid"
                    },
                    "AmountsDetail": {
                        "Currency": "EUR",
                        "AmountFinal": 250.00,
                        "AmountTotal": 275.00,
                        "AmountBase": 225.00
                    }
                },
                {
                    "BudgetId": "BDG456",
                    "Origin": "mobile",
                    "HotelId": "HTL002",
                    "Status": "expired",
                    "CreationDate": "2024-01-14T15:00:00Z",
                    "CustomerDetail": {
                        "Name": "María",
                        "Surname": "López",
                        "Email": "maria@email.com"
                    }
                }
            ],
            "CurrentPage": 1,
            "TotalPages": 3,
            "TotalRecords": 25,
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 300
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_basic_search_success(self, handler, basic_search_args, mock_auth_response, mock_search_response):
        """Test successful basic budget search."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            result = await handler.execute(basic_search_args)
            
            assert result["success"] is True
            assert len(result["data"]["budgets"]) == 2
            assert result["data"]["pagination"]["current_page"] == 1
            assert result["data"]["pagination"]["total_pages"] == 3
            assert result["data"]["pagination"]["total_records"] == 25
            assert "Found 2 budget(s) on page 1 of 3" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_search_with_filters(self, handler, mock_auth_response, mock_search_response):
        """Test search with various filters."""
        arguments = {
            "budget_ids": ["BDG123", "BDG456"],
            "hotel_ids": ["HTL001", "HTL002"],
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "date_by": "creationdate",
            "filter_by": {
                "name": "Juan",
                "country": "ES",
                "status": ["pending", "expired"],
                "client": {
                    "email": "juan@email.com",
                    "phone": {
                        "prefix": "+34",
                        "number": "666777888"
                    }
                }
            },
            "page": 1,
            "num_results": 20,
            "order_by": "creationdate",
            "order_type": "desc",
            "language": "es"
        }
        
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_search_response]
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["budget_ids"] == ["BDG123", "BDG456"]
            assert result["data"]["search_criteria"]["hotel_ids"] == ["HTL001", "HTL002"]
            assert result["data"]["search_criteria"]["date_from"] == "2024-01-01"
            assert result["data"]["search_criteria"]["date_to"] == "2024-01-31"
    
    @pytest.mark.asyncio
    async def test_execute_missing_required_params(self, handler):
        """Test execution with missing required parameters."""
        arguments = {
            "language": "es"
            # Missing order_by and order_type
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "order_by is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_date_format(self, handler):
        """Test execution with invalid date format."""
        arguments = {
            "date_from": "2024/01/15",  # Wrong format
            "order_by": "creationdate",
            "order_type": "desc",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid date format" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_date_range(self, handler):
        """Test execution with invalid date range."""
        arguments = {
            "date_from": "2024-01-31",
            "date_to": "2024-01-15",  # End date before start date
            "order_by": "creationdate",
            "order_type": "desc",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "date_from cannot be later than date_to" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_empty_results(self, handler, basic_search_args, mock_auth_response):
        """Test search with no results."""
        empty_response = {
            "BudgetBasicDetail": [],
            "CurrentPage": 1,
            "TotalPages": 0,
            "TotalRecords": 0,
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ789",
                "Timestamp": "2024-01-15T10:30:10Z",
                "TimeResponse": 100
            }
        }
        
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, empty_response]
            
            result = await handler.execute(basic_search_args)
            
            assert result["success"] is True
            assert len(result["data"]["budgets"]) == 0
            assert result["data"]["pagination"]["total_records"] == 0
    
    def test_validate_date_format_valid(self, handler):
        """Test date format validation with valid dates."""
        # Should not raise an exception
        handler._validate_date_format("2024-01-15", "test_field")
        handler._validate_date_format("2024-12-31", "test_field")
    
    def test_validate_date_format_invalid(self, handler):
        """Test date format validation with invalid dates."""
        with pytest.raises(ValidationError):
            handler._validate_date_format("2024/01/15", "test_field")
        
        with pytest.raises(ValidationError):
            handler._validate_date_format("15-01-2024", "test_field")
        
        with pytest.raises(ValidationError):
            handler._validate_date_format("invalid", "test_field")
    
    def test_format_budget_basic_detail_complete(self, handler):
        """Test formatting of complete budget basic details."""
        budget = {
            "BudgetId": "BDG123",
            "Origin": "web",
            "HotelId": "HTL001",
            "Status": "pending",
            "CustomerDetail": {
                "Name": "Juan",
                "Surname": "García",
                "Email": "juan@email.com"
            },
            "AmountsDetail": {
                "Currency": "EUR",
                "AmountFinal": 250.00
            }
        }
        
        formatted = handler._format_budget_basic_detail(budget)
        
        assert formatted["budget_id"] == "BDG123"
        assert formatted["origin"] == "web"
        assert formatted["hotel_id"] == "HTL001"
        assert formatted["status"] == "pending"
        assert formatted["customer"]["name"] == "Juan"
        assert formatted["amounts"]["currency"] == "EUR"
    
    def test_format_budget_basic_detail_minimal(self, handler):
        """Test formatting of minimal budget basic details."""
        budget = {
            "BudgetId": "BDG456",
            "Status": "expired"
        }
        
        formatted = handler._format_budget_basic_detail(budget)
        
        assert formatted["budget_id"] == "BDG456"
        assert formatted["status"] == "expired"
        assert formatted["customer"] is None or not formatted.get("customer")
    
    @pytest.mark.asyncio
    async def test_call_budget_search_rq_success_with_results(self):
        """Test the MCP tool handler for successful search with results."""
        with patch('tools.ctbudget.budget_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "budgets": [
                        {
                            "budget_id": "BDG123",
                            "hotel_id": "HTL001",
                            "status": "pending",
                            "creation_date": "2024-01-15T09:00:00Z",
                            "customer": {
                                "name": "Juan",
                                "surname": "García",
                                "email": "juan@email.com"
                            },
                            "amounts": {
                                "currency": "EUR",
                                "final": 250.00
                            }
                        }
                    ],
                    "pagination": {
                        "current_page": 1,
                        "total_pages": 1,
                        "total_records": 1,
                        "page_size": 10,
                        "has_next_page": False,
                        "has_previous_page": False
                    },
                    "search_criteria": {
                        "order_by": "creationdate",
                        "order_type": "desc",
                        "budget_ids": [],
                        "hotel_ids": [],
                        "date_from": None,
                        "date_to": None,
                        "filter_by": {}
                    },
                    "search_summary": {
                        "results_found": 1,
                        "total_available": 1,
                        "language": "es"
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 300}
                },
                "message": "Found 1 budget(s) on page 1 of 1"
            }
            
            arguments = {
                "order_by": "creationdate",
                "order_type": "desc"
            }
            result = await call_budget_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Search Results" in response_text
            assert "Results Found: 1 budget(s)" in response_text
            assert "BDG123" in response_text
            assert "Juan García" in response_text
            assert "EUR" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_search_rq_no_results(self):
        """Test the MCP tool handler for search with no results."""
        with patch('tools.ctbudget.budget_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "budgets": [],
                    "pagination": {
                        "current_page": 1,
                        "total_pages": 0,
                        "total_records": 0,
                        "page_size": 10,
                        "has_next_page": False,
                        "has_previous_page": False
                    },
                    "search_criteria": {
                        "order_by": "creationdate",
                        "order_type": "desc",
                        "budget_ids": [],
                        "hotel_ids": [],
                        "date_from": None,
                        "date_to": None,
                        "filter_by": {}
                    },
                    "search_summary": {
                        "results_found": 0,
                        "total_available": 0,
                        "language": "es"
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 100}
                },
                "message": "Found 0 budget(s) on page 1 of 0"
            }
            
            arguments = {
                "order_by": "creationdate",
                "order_type": "desc",
                "budget_ids": ["BDG999"]
            }
            result = await call_budget_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Search Results" in response_text
            assert "Results Found: 0 budget(s)" in response_text
            assert "No budgets found matching the search criteria" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_search_rq_with_filters(self):
        """Test the MCP tool handler for search with complex filters."""
        with patch('tools.ctbudget.budget_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "budgets": [
                        {
                            "budget_id": "BDG123",
                            "status": "pending",
                            "customer": {
                                "name": "Juan",
                                "country": "ES"
                            }
                        }
                    ],
                    "pagination": {
                        "current_page": 1,
                        "total_pages": 2,
                        "total_records": 15,
                        "page_size": 10,
                        "has_next_page": True,
                        "has_previous_page": False
                    },
                    "search_criteria": {
                        "order_by": "creationdate",
                        "order_type": "desc",
                        "budget_ids": ["BDG123"],
                        "hotel_ids": ["HTL001"],
                        "date_from": "2024-01-01",
                        "date_to": "2024-01-31",
                        "date_by": "creationdate",
                        "filter_by": {
                            "name": "Juan",
                            "status": ["pending"],
                            "client": {
                                "email": "juan@email.com"
                            }
                        }
                    },
                    "search_summary": {
                        "results_found": 1,
                        "total_available": 15,
                        "language": "es"
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 250}
                },
                "message": "Found 1 budget(s) on page 1 of 2"
            }
            
            arguments = {
                "order_by": "creationdate",
                "order_type": "desc",
                "filter_by": {
                    "name": "Juan",
                    "status": ["pending"]
                }
            }
            result = await call_budget_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Search Results" in response_text
            assert "BDG123" in response_text
            assert "Date Range (creationdate): 2024-01-01 to 2024-01-31" in response_text
            assert "Filters: Name: Juan; Status: pending; Email: juan@email.com" in response_text
            assert "Has Next Page: Yes" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_search_rq_failure(self):
        """Test the MCP tool handler for failed search."""
        with patch('tools.ctbudget.budget_search_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid search parameters",
                "error": {"code": "400", "details": "Invalid order_by field"}
            }
            
            arguments = {
                "order_by": "invalid_field",
                "order_type": "desc"
            }
            result = await call_budget_search_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Search Failed" in response_text
            assert "Invalid search parameters" in response_text
            assert "Troubleshooting" in response_text
