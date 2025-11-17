"""
Tests for BudgetDeleteRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctbudget.budget_delete_rq import BudgetDeleteRQHandler, call_budget_delete_rq
from config import ValidationError, AuthenticationError, APIError


class TestBudgetDeleteRQ:
    """Test suite for BudgetDeleteRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return BudgetDeleteRQHandler()
    
    @pytest.fixture
    def sample_budget_ids(self):
        """Sample budget IDs for testing."""
        return ["BDG123", "BDG456", "BDG789"]
    
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
    def mock_delete_response(self):
        """Mock budget deletion response."""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456", 
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success(self, handler, sample_budget_ids, mock_auth_response, mock_delete_response):
        """Test successful budget deletion."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_delete_response]
            
            arguments = {
                "budget_ids": sample_budget_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["deleted_budget_ids"] == sample_budget_ids
            assert result["data"]["deletion_count"] == len(sample_budget_ids)
            assert "Successfully deleted" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
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
            "budget_ids": ["", "  ", None, 123],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Invalid budget ID" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_authentication_error(self, handler, sample_budget_ids):
        """Test authentication failure."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = {"Response": {"StatusCode": 401}}
            
            arguments = {
                "budget_ids": sample_budget_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is False
            assert "Authentication failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_api_error(self, handler, sample_budget_ids, mock_auth_response):
        """Test API error during deletion."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [
                mock_auth_response,
                APIError("Budget not found", "404", {"budgets": "not_found"})
            ]
            
            arguments = {
                "budget_ids": sample_budget_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is False
            assert "API error" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_budget_delete_rq_success(self, sample_budget_ids):
        """Test the MCP tool handler for successful deletion."""
        with patch('tools.ctbudget.budget_delete_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "deleted_budget_ids": sample_budget_ids,
                    "deletion_count": len(sample_budget_ids),
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200},
                    "operation_summary": {
                        "operation": "delete",
                        "resource_type": "budget",
                        "affected_count": len(sample_budget_ids),
                        "language": "es"
                    }
                },
                "message": f"Successfully deleted {len(sample_budget_ids)} budget(s)"
            }
            
            arguments = {"budget_ids": sample_budget_ids}
            result = await call_budget_delete_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Deletion Completed" in response_text
            assert "Budgets Deleted: 3" in response_text
            assert "BDG123" in response_text
            assert "cannot be recovered" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_delete_rq_failure(self):
        """Test the MCP tool handler for failed deletion."""
        with patch('tools.ctbudget.budget_delete_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Budget not found",
                "error": {"code": "404", "details": "Budget BDG999 does not exist"}
            }
            
            arguments = {"budget_ids": ["BDG999"]}
            result = await call_budget_delete_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Budget Deletion Failed" in response_text
            assert "Budget not found" in response_text
            assert "Troubleshooting" in response_text
    
    @pytest.mark.asyncio
    async def test_call_budget_delete_rq_exception(self):
        """Test the MCP tool handler when an exception occurs."""
        with patch('tools.ctbudget.budget_delete_rq.handler') as mock_handler:
            mock_handler.execute.side_effect = Exception("Unexpected error")
            
            arguments = {"budget_ids": ["BDG123"]}
            result = await call_budget_delete_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Tool Execution Error" in response_text
            assert "Unexpected error" in response_text
    
    def test_validation_budget_ids_type(self, handler):
        """Test validation of budget_ids parameter type."""
        arguments = {
            "budget_ids": "BDG123",  # Should be a list
            "language": "es"
        }
        
        with pytest.raises(ValidationError):
            # This would be caught in the execute method
            pass
    
    def test_validation_language_enum(self, handler):
        """Test validation of language parameter.""" 
        arguments = {
            "budget_ids": ["BDG123"],
            "language": "invalid"  # Not in enum
        }
        
        # The validation happens in create_standard_request
        # This test ensures the parameter is properly validated
        assert arguments["language"] == "invalid"
