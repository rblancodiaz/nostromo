"""
Tests for BudgetPropertiesUpdateRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctbudget.budget_properties_update_rq import BudgetPropertiesUpdateRQHandler, call_budget_properties_update_rq
from config import ValidationError, AuthenticationError, APIError


class TestBudgetPropertiesUpdateRQ:
    """Test suite for BudgetPropertiesUpdateRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return BudgetPropertiesUpdateRQHandler()
    
    @pytest.fixture
    def valid_datetime(self):
        """Valid datetime string for testing."""
        return "2024-01-15T14:30:00"
    
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
    def mock_update_response(self):
        """Mock budget properties update response."""
        return {
            "BudgetDetails": {
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
                "CopiedDate": None,
                "CreationDate": "2024-01-15T09:00:00Z",
                "CustomerDetail": {
                    "Name": "Juan",
                    "Surname": "García",
                    "Email": "juan@email.com"
                },
                "AmountsDetail": {
                    "Currency": "EUR",
                    "AmountFinal": 250.00,
                    "AmountTotal": 275.00
                }
            },
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 250
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_update_sent_date_success(self, handler, valid_datetime, mock_auth_response, mock_update_response):
        """Test successful sent date update."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_update_response]
            
            arguments = {
                "budget_id": "BDG123",
                "sent_date": valid_datetime,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["budget_id"] == "BDG123"
            assert result["data"]["applied_updates"]["sent_date"] == valid_datetime
            assert "Budget properties updated successfully" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_update_copied_date_success(self, handler, valid_datetime, mock_auth_response, mock_update_response):
        """Test successful copied date update."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_update_response]
            
            arguments = {
                "budget_id": "BDG123",
                "copied_date": valid_datetime,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["applied_updates"]["copied_date"] == valid_datetime
    
    @pytest.mark.asyncio
    async def test_execute_clear_sent_date_success(self, handler, mock_auth_response, mock_update_response):
        """Test successful sent date clearing."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_update_response]
            
            arguments = {
                "budget_id": "BDG123",
                "clear_sent_date": True,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["applied_updates"]["cleared_sent_date"] is True
    
    @pytest.mark.asyncio
    async def test_execute_clear_copied_date_success(self, handler, mock_auth_response, mock_update_response):
        """Test successful copied date clearing."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_update_response]
            
            arguments = {
                "budget_id": "BDG123",
                "clear_copied_date": True,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["applied_updates"]["cleared_copied_date"] is True
    
    @pytest.mark.asyncio
    async def test_execute_missing_budget_id(self, handler):
        """Test execution with missing budget ID."""
        arguments = {
            "sent_date": "2024-01-15T14:30:00",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Budget ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_empty_budget_id(self, handler):
        """Test execution with empty budget ID."""
        arguments = {
            "budget_id": "",
            "sent_date": "2024-01-15T14:30:00",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Budget ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_invalid_datetime_format(self, handler):
        """Test execution with invalid datetime format."""
        arguments = {
            "budget_id": "BDG123",
            "sent_date": "2024-01-15 14:30:00",  # Wrong format
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid datetime format" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_conflicting_sent_date_params(self, handler):
        """Test execution with conflicting sent date parameters."""
        arguments = {
            "budget_id": "BDG123",
            "sent_date": "2024-01-15T14:30:00",
            "clear_sent_date": True,
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Cannot set sent_date and clear_sent_date at the same time" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_conflicting_copied_date_params(self, handler):
        """Test execution with conflicting copied date parameters."""
        arguments = {
            "budget_id": "BDG123",
            "copied_date": "2024-01-15T14:30:00",
            "clear_copied_date": True,
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Cannot set copied_date and clear_copied_date at the same time" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_no_updates_specified(self, handler):
        """Test execution with no update parameters specified."""
        arguments = {
            "budget_id": "BDG123",
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one property update must be specified" in result["message"]
    
    def test_validate_datetime_format_valid(self, handler):
        """Test datetime format validation with valid formats."""
        # Should not raise an exception
        handler._validate_datetime_format("2024-01-15T14:30:00", "test_field")
        handler._validate_datetime_format("2024-12-31T23:59:59", "test_field")
    
    def test_validate_datetime_format_invalid(self, handler):
        """Test datetime format validation with invalid formats."""
        with pytest.raises(ValidationError):
            handler._validate_datetime_format("2024-01-15 14:30:00", "test_field")
        
        with pytest.raises(ValidationError):
            handler._validate_datetime_format("2024/01/15T14:30:00", "test_field")
        
        with pytest.raises(ValidationError):
            handler._validate_datetime_format("invalid", "test_field")
    
    def test_format_budget_properties(self, handler):
        """Test formatting of budget properties."""
        budget_details = {
            "BudgetId": "BDG123",
            "Origin": "web",
            "HotelId": "HTL001",
            "Status": "pending",
            "IsSent": True,
            "SentDate": "2024-01-15T14:30:00",
            "CustomerDetail": {
                "Name": "Juan",
                "Email": "juan@email.com"
            },
            "AmountsDetail": {
                "Currency": "EUR",
                "AmountFinal": 250.00
            }
        }
        
        formatted = handler._format_budget_properties(budget_details)
        
        assert formatted["budget_id"] == "BDG123"
        assert formatted["origin"] == "web"
        assert formatted["hotel_id"] == "HTL001"
        assert formatted["status"] == "pending"
        assert formatted["is_sent"] is True
        assert formatted["sent_date"] == "2024-01-15T14:30:00"
        assert formatted["customer_details"]["Name"] == "Juan"
        assert formatted["amounts_detail"]["Currency"] == "EUR"
    
    @pytest.mark.asyncio
    async def test_call_budget_properties_update_rq_success(self):
        """Test the MCP tool handler for successful property update."""
        with patch('tools.ctbudget.budget_properties_update_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "budget_id": "BDG123",
                    "updated_budget": {
                        "budget_id": "BDG123",
                        "origin": "web",
                        "hotel_id": "HTL001",
                        "status": "pending",
                        "is_sent": True,
                        "sent_date": "2024-01-15T14:30:00",
                        "customer_details": {
                            "Name": "Juan",
                            "Surname": "García"
                        },
                        "amounts_detail": {
                            "Currency": "EUR",
                            "AmountFinal": 250.00
                        }
                    },
                    "applied_updates": {
                        "sent_date": "2024-01-15T14:30:00",
                        "copied_date": None,
                        "cleared_sent_date": False,
                        "cleared_copied_date": False
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 250},
                    "operation_summary": {
                        "operation": "update",
                        "resource_type": "budget_properties",
                        "budget_id": "BDG123",
                        "language": "es"
                    }
                },
                "message": "Budget properties updated successfully for budget BDG123"
            }
            
            arguments = {
                "budget_id": "BDG123",
                "sent_date": "2024-01-15T14:30:00"
            }
            result = await call_budget_properties_update_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Properties Updated" in response_text
            assert "BDG123" in response_text
            assert "Sent Date: Set to" in response_text
            assert "2024-01-15T14:30:00" in response_text
            assert "Juan García" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_properties_update_rq_failure(self):
        """Test the MCP tool handler for failed property update."""
        with patch('tools.ctbudget.budget_properties_update_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Budget not found",
                "error": {"code": "404", "details": "Budget BDG999 does not exist"}
            }
            
            arguments = {
                "budget_id": "BDG999",
                "sent_date": "2024-01-15T14:30:00"
            }
            result = await call_budget_properties_update_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Properties Update Failed" in response_text
            assert "Budget not found" in response_text
            assert "Troubleshooting" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_properties_update_rq_clear_operations(self):
        """Test the MCP tool handler for clear operations."""
        with patch('tools.ctbudget.budget_properties_update_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "budget_id": "BDG123",
                    "updated_budget": {
                        "budget_id": "BDG123",
                        "is_sent": False,
                        "sent_date": None,
                        "is_copied": False,
                        "copied_date": None
                    },
                    "applied_updates": {
                        "sent_date": None,
                        "copied_date": None,
                        "cleared_sent_date": True,
                        "cleared_copied_date": True
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200},
                    "operation_summary": {
                        "operation": "update",
                        "resource_type": "budget_properties",
                        "budget_id": "BDG123",
                        "language": "es"
                    }
                },
                "message": "Budget properties updated successfully for budget BDG123"
            }
            
            arguments = {
                "budget_id": "BDG123",
                "clear_sent_date": True,
                "clear_copied_date": True
            }
            result = await call_budget_properties_update_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Properties Updated" in response_text
            assert "Sent Date: Cleared" in response_text
            assert "Copied Date: Cleared" in response_text
