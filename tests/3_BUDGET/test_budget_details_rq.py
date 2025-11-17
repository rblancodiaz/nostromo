"""
Tests for BudgetDetailsRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctbudget.budget_details_rq import BudgetDetailsRQHandler, call_budget_details_rq
from config import ValidationError, AuthenticationError, APIError


class TestBudgetDetailsRQ:
    """Test suite for BudgetDetailsRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return BudgetDetailsRQHandler()
    
    @pytest.fixture
    def sample_budget_ids(self):
        """Sample budget IDs for testing."""
        return ["BDG123", "BDG456"]
    
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
    def mock_budget_details_response(self):
        """Mock budget details response."""
        return {
            "BudgetDetails": [
                {
                    "Id": "BDG123",
                    "HotelId": "HTL001",
                    "CreationUser": "user123",
                    "BudgetLang": "es",
                    "Status": "pending",
                    "CreationDate": "2024-01-15T09:00:00Z",
                    "LastUpdate": "2024-01-15T10:15:00Z",
                    "IsSent": True,
                    "sentDate": "2024-01-15T10:00:00Z",
                    "IsCopied": False,
                    "CustomerDetail": {
                        "Name": "Juan",
                        "Surname": "García",
                        "Email": "juan.garcia@email.com",
                        "Phone": "+34666777888",
                        "Country": "ES",
                        "City": "Madrid"
                    },
                    "BasketDetail": {
                        "Origin": "web",
                        "Rewards": True,
                        "AllowDeposit": True,
                        "AllowFullPayment": True,
                        "AllowInstallments": False,
                        "AllowEstablishment": True,
                        "AmountsDetail": {
                            "Currency": "EUR",
                            "AmountFinal": 250.00,
                            "AmountTotal": 275.00,
                            "AmountBase": 225.00,
                            "AmountTaxes": 25.00,
                            "AmountTouristTax": 15.00,
                            "AmountOffers": 30.00,
                            "AmountExtras": 20.00
                        }
                    },
                    "BillingDetails": {
                        "Name": "Juan García SL",
                        "Cif": "B12345678",
                        "Address": "Calle Mayor 123",
                        "City": "Madrid",
                        "Country": "ES"
                    }
                }
            ],
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 300
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success(self, handler, sample_budget_ids, mock_auth_response, mock_budget_details_response):
        """Test successful budget details retrieval."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_budget_details_response]
            
            arguments = {
                "budget_ids": sample_budget_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["budget_details"]) == 1
            assert result["data"]["budget_details"][0]["id"] == "BDG123"
            assert result["data"]["found_count"] == 1
            assert "Retrieved details for 1 budget(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_empty_budget_ids(self, handler):
        """Test execution with empty budget IDs list."""
        arguments = {
            "budget_ids": [],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one budget ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_budget_ids(self, handler):
        """Test execution with invalid budget IDs."""
        arguments = {
            "budget_ids": ["", "  ", None],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid budget ID" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_no_results_found(self, handler, sample_budget_ids, mock_auth_response):
        """Test when no budget details are found."""
        empty_response = {
            "BudgetDetails": [],
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
            
            arguments = {
                "budget_ids": sample_budget_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["budget_details"]) == 0
            assert result["data"]["found_count"] == 0
    
    @pytest.mark.asyncio
    async def test_format_budget_details_complete(self, handler):
        """Test formatting of complete budget details."""
        budget_detail = {
            "Id": "BDG123",
            "HotelId": "HTL001",
            "CreationUser": "user123",
            "Status": "pending",
            "CustomerDetail": {
                "Name": "Juan",
                "Surname": "García",
                "Email": "juan@email.com"
            },
            "BasketDetail": {
                "Origin": "web",
                "AmountsDetail": {
                    "Currency": "EUR",
                    "AmountFinal": 100.00
                }
            }
        }
        
        formatted = handler._format_budget_details(budget_detail)
        
        assert formatted["id"] == "BDG123"
        assert formatted["hotel_id"] == "HTL001"
        assert formatted["customer"]["name"] == "Juan"
        assert formatted["basket"]["origin"] == "web"
        assert formatted["basket"]["amounts"]["currency"] == "EUR"
    
    @pytest.mark.asyncio
    async def test_format_budget_details_minimal(self, handler):
        """Test formatting of minimal budget details."""
        budget_detail = {
            "Id": "BDG456",
            "Status": "expired"
        }
        
        formatted = handler._format_budget_details(budget_detail)
        
        assert formatted["id"] == "BDG456"
        assert formatted["status"] == "expired"
        assert formatted["customer"] is None or not formatted.get("customer")
    
    @pytest.mark.asyncio
    async def test_call_budget_details_rq_success(self, sample_budget_ids):
        """Test the MCP tool handler for successful details retrieval."""
        with patch('tools.ctbudget.budget_details_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "budget_details": [{
                        "id": "BDG123",
                        "hotel_id": "HTL001",
                        "status": "pending",
                        "creation_date": "2024-01-15T09:00:00Z",
                        "customer": {
                            "name": "Juan",
                            "surname": "García",
                            "email": "juan@email.com"
                        },
                        "basket": {
                            "amounts": {
                                "currency": "EUR",
                                "final": 250.00
                            }
                        }
                    }],
                    "found_count": 1,
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 300},
                    "query_summary": {
                        "requested_count": 1,
                        "found_count": 1,
                        "language": "es"
                    }
                },
                "message": "Retrieved details for 1 budget(s)"
            }
            
            arguments = {"budget_ids": ["BDG123"]}
            result = await call_budget_details_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Details Retrieved" in response_text
            assert "BDG123" in response_text
            assert "Juan García" in response_text
            assert "EUR" in response_text
            assert "250.0" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_details_rq_no_results(self):
        """Test the MCP tool handler when no budgets are found."""
        with patch('tools.ctbudget.budget_details_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "budget_details": [],
                    "found_count": 0,
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 100},
                    "query_summary": {
                        "requested_count": 1,
                        "found_count": 0,
                        "language": "es"
                    }
                },
                "message": "Retrieved details for 0 budget(s)"
            }
            
            arguments = {"budget_ids": ["BDG999"]}
            result = await call_budget_details_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Details Retrieved" in response_text
            assert "Found: 0 budget(s)" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_details_rq_failure(self):
        """Test the MCP tool handler for failed details retrieval."""
        with patch('tools.ctbudget.budget_details_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Budget not found",
                "error": {"code": "404", "details": "Budget BDG999 does not exist"}
            }
            
            arguments = {"budget_ids": ["BDG999"]}
            result = await call_budget_details_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Failed to Retrieve Budget Details" in response_text
            assert "Budget not found" in response_text
            assert "Troubleshooting" in response_text
