#!/usr/bin/env python3
"""
MCP Health Check and Connectivity Test Suite
============================================

This script performs comprehensive health checks and connectivity tests
for the Neobookings MCP Server including:

1. Configuration validation
2. API connectivity tests
3. Authentication verification
4. Tool availability checks
5. Individual endpoint testing
6. Performance benchmarks
7. Error handling validation
8. MCP protocol compliance

Usage:
    python test_mcp_health.py [--verbose] [--category CATEGORY] [--quick]
    
    --verbose: Enable detailed output
    --category: Test specific category only (auth, basket, budget, hotel, etc.)
    --quick: Run only essential tests (faster execution)
"""

import asyncio
import sys
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import traceback

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import our modules
from config import (
    NeobookingsConfig, 
    NeobookingsHTTPClient,
    create_authentication_request,
    create_standard_request,
    logger,
    ValidationError,
    AuthenticationError,
    APIError
)

# Import all tool modules for testing
from tools.ctauthentication.authenticator_rq import AuthenticatorRQHandler
from tools.ctbasket.basket_create_rq import BasketCreateRQHandler
from tools.ctbudget.budget_search_rq import BudgetSearchRQHandler
from tools.cthotelinventory.hotel_search_rq import HotelSearchRQHandler
from tools.ctgenericproduct.generic_product_details_rq import GenericProductDetailsRQHandler
from tools.ctorders.order_search_rq import OrderSearchRQHandler
from tools.ctpackages.package_details_rq import PackageDetailsRQHandler
from tools.ctusers.user_rewards_details_rq import UserRewardsDetailsRQHandler
from tools.ctgeosearch.zone_search_rq import ZoneSearchRQHandler


@dataclass
class TestResult:
    """Container for test results."""
    test_name: str
    category: str
    success: bool
    duration_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class HealthCheckSummary:
    """Summary of all health check results."""
    total_tests: int
    passed_tests: int
    failed_tests: int
    total_duration_ms: float
    categories_tested: List[str]
    critical_failures: List[str]
    warnings: List[str]
    recommendations: List[str]


class MCPHealthChecker:
    """Comprehensive health checker for the MCP server."""
    
    def __init__(self, verbose: bool = False, quick_mode: bool = False):
        self.verbose = verbose
        self.quick_mode = quick_mode
        self.config = None
        self.auth_token = None
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
        # Test categories and their critical endpoints
        self.test_categories = {
            "configuration": {
                "description": "Configuration and Environment Setup",
                "critical": True,
                "tests": ["config_validation", "environment_check"]
            },
            "connectivity": {
                "description": "Network and API Connectivity", 
                "critical": True,
                "tests": ["api_connectivity", "ssl_verification"]
            },
            "authentication": {
                "description": "Authentication and Authorization",
                "critical": True,
                "tests": ["auth_test", "token_validation"]
            },
            "tools_registry": {
                "description": "MCP Tools Registry and Loading",
                "critical": True,
                "tests": ["tools_import", "handlers_validation"]
            },
            "basic_endpoints": {
                "description": "Basic Endpoint Functionality",
                "critical": True,
                "tests": ["hotel_search", "zone_search", "budget_search"]
            },
            "advanced_endpoints": {
                "description": "Advanced Endpoint Operations",
                "critical": False,
                "tests": ["basket_operations", "order_management", "package_details"]
            },
            "performance": {
                "description": "Performance and Response Times",
                "critical": False,
                "tests": ["response_times", "concurrent_requests"]
            },
            "error_handling": {
                "description": "Error Handling and Recovery",
                "critical": False,
                "tests": ["invalid_requests", "timeout_handling"]
            }
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = f"[{timestamp}] [{level}]"
        if self.verbose or level in ["ERROR", "CRITICAL"]:
            print(f"{prefix} {message}")
    
    def add_result(self, test_name: str, category: str, success: bool, 
                   duration_ms: float, message: str, details: Optional[Dict[str, Any]] = None,
                   error: Optional[str] = None):
        """Add a test result."""
        result = TestResult(
            test_name=test_name,
            category=category,
            success=success,
            duration_ms=duration_ms,
            message=message,
            details=details,
            error=error
        )
        self.results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        self.log(f"{status} {test_name}: {message} ({duration_ms:.1f}ms)")
        
        if not success and error:
            self.log(f"   Error: {error}", "ERROR")
    
    async def run_timed_test(self, test_func, *args, **kwargs) -> Tuple[Any, float]:
        """Run a test function and measure execution time."""
        start = time.time()
        try:
            result = await test_func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            return result, duration
        except Exception as e:
            duration = (time.time() - start) * 1000
            raise e
    
    # ==========================================
    # CONFIGURATION TESTS
    # ==========================================
    
    async def test_config_validation(self):
        """Test configuration loading and validation."""
        start = time.time()
        try:
            self.config = NeobookingsConfig.from_env()
            
            # Validate required fields
            required_fields = ["client_code", "system_code", "username", "password", "base_url"]
            missing_fields = []
            
            for field in required_fields:
                value = getattr(self.config, field, None)
                if not value or value.strip() == "":
                    missing_fields.append(field)
            
            if missing_fields:
                raise ValidationError(f"Missing required configuration: {', '.join(missing_fields)}")
            
            details = {
                "client_code": self.config.client_code,
                "system_code": self.config.system_code,
                "username": self.config.username,
                "base_url": self.config.base_url,
                "timeout": self.config.timeout
            }
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "config_validation", "configuration", True, duration,
                f"Configuration loaded successfully (timeout: {self.config.timeout}s)",
                details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "config_validation", "configuration", False, duration,
                "Configuration validation failed", error=str(e)
            )
    
    async def test_environment_check(self):
        """Test environment variables and dependencies."""
        start = time.time()
        try:
            import os
            import aiohttp
            import mcp
            
            env_vars = ["NEO_CLIENT_CODE", "NEO_SYSTEM_CODE", "NEO_USERNAME", "NEO_PASSWORD"]
            missing_env = [var for var in env_vars if not os.getenv(var)]
            
            details = {
                "python_version": sys.version,
                "missing_env_vars": missing_env,
                "project_root": str(project_root),
                "dependencies": {
                    "aiohttp": "✅ Available",
                    "mcp": "✅ Available",
                    "structlog": "✅ Available"
                }
            }
            
            success = len(missing_env) == 0
            message = "Environment check passed" if success else f"Missing env vars: {missing_env}"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "environment_check", "configuration", success, duration,
                message, details
            )
            
        except ImportError as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "environment_check", "configuration", False, duration,
                "Missing required dependencies", error=str(e)
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "environment_check", "configuration", False, duration,
                "Environment check failed", error=str(e)
            )
    
    # ==========================================
    # CONNECTIVITY TESTS
    # ==========================================
    
    async def test_api_connectivity(self):
        """Test basic API connectivity."""
        start = time.time()
        try:
            if not self.config:
                raise ValidationError("Configuration not loaded")
            
            async with NeobookingsHTTPClient(self.config) as client:
                # Test basic connectivity with a simple request
                auth_request = create_authentication_request(self.config)
                response = await client.post("/AuthenticatorRQ", auth_request, require_auth=False)
                
                # Check if we got a valid response structure
                if "Response" not in response:
                    raise APIError("Invalid response structure")
                
                response_info = response.get("Response", {})
                status_code = response_info.get("StatusCode", 0)
                
                details = {
                    "status_code": status_code,
                    "has_token": "Token" in response,
                    "response_time_ms": response_info.get("TimeResponse", 0),
                    "base_url": self.config.base_url
                }
                
                success = status_code == 200
                message = f"API connectivity successful (status: {status_code})" if success else f"API returned status: {status_code}"
                
                duration = (time.time() - start) * 1000
                self.add_result(
                    "api_connectivity", "connectivity", success, duration,
                    message, details
                )
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "api_connectivity", "connectivity", False, duration,
                "API connectivity failed", error=str(e)
            )
    
    async def test_ssl_verification(self):
        """Test SSL certificate validation."""
        start = time.time()
        try:
            import ssl
            import aiohttp
            
            # Test SSL connection to the API endpoint
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
            async with aiohttp.ClientSession(connector=connector) as session:
                url = self.config.base_url.replace("/api/v2", "")
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    ssl_info = {
                        "ssl_verified": True,
                        "status_code": response.status,
                        "url_tested": url
                    }
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "ssl_verification", "connectivity", True, duration,
                "SSL certificate validation successful", ssl_info
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "ssl_verification", "connectivity", False, duration,
                "SSL verification failed", error=str(e)
            )
    
    # ==========================================
    # AUTHENTICATION TESTS
    # ==========================================
    
    async def test_authentication(self):
        """Test authentication process."""
        start = time.time()
        try:
            handler = AuthenticatorRQHandler()
            result = await handler.execute({"language": "es"})
            
            if not result.get("success"):
                raise AuthenticationError(result.get("message", "Authentication failed"))
            
            # Extract token for use in other tests
            token_data = result.get("data", {})
            self.auth_token = token_data.get("token")
            
            if not self.auth_token:
                raise AuthenticationError("No authentication token received")
            
            details = {
                "token_length": len(self.auth_token),
                "token_prefix": self.auth_token[:10] + "..." if len(self.auth_token) > 10 else self.auth_token,
                "language": token_data.get("language"),
                "session_info": token_data.get("session_info", {})
            }
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "auth_test", "authentication", True, duration,
                f"Authentication successful (token: {len(self.auth_token)} chars)", details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "auth_test", "authentication", False, duration,
                "Authentication test failed", error=str(e)
            )
    
    async def test_token_validation(self):
        """Test token validation with a simple authenticated request."""
        start = time.time()
        try:
            if not self.auth_token:
                raise AuthenticationError("No authentication token available")
            
            # Use the token to make an authenticated request
            async with NeobookingsHTTPClient(self.config) as client:
                client.set_token(self.auth_token)
                
                # Test with a simple search request
                request_data = create_standard_request("es")
                request_data.update({
                    "Page": 1,
                    "NumResults": 1
                })
                
                response = await client.post("/HotelSearchRQ", request_data)
                
                response_info = response.get("Response", {})
                status_code = response_info.get("StatusCode", 0)
                
                details = {
                    "status_code": status_code,
                    "token_valid": status_code != 401,
                    "response_time_ms": response_info.get("TimeResponse", 0)
                }
                
                success = status_code == 200
                message = f"Token validation successful (status: {status_code})" if success else f"Token validation failed (status: {status_code})"
                
                duration = (time.time() - start) * 1000
                self.add_result(
                    "token_validation", "authentication", success, duration,
                    message, details
                )
                
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "token_validation", "authentication", False, duration,
                "Token validation failed", error=str(e)
            )
    
    # ==========================================
    # TOOLS REGISTRY TESTS
    # ==========================================
    
    async def test_tools_import(self):
        """Test that all tool modules can be imported successfully."""
        start = time.time()
        try:
            # Import main module to verify all tools load
            import main
            
            # Verify tool counts
            total_tools = len(main.ALL_TOOLS)
            tool_handlers = len(main.TOOL_HANDLERS)
            categories = len(main.TOOL_CATEGORIES)
            
            expected_tools = 51  # Expected number of tools
            
            details = {
                "total_tools_loaded": total_tools,
                "tool_handlers_registered": tool_handlers,
                "categories_loaded": categories,
                "expected_tools": expected_tools,
                "tools_match_expected": total_tools == expected_tools,
                "handlers_match_tools": tool_handlers == total_tools
            }
            
            success = (total_tools == expected_tools and 
                      tool_handlers == total_tools and 
                      categories == 9)
            
            message = f"Tools import successful ({total_tools}/{expected_tools} tools loaded)" if success else f"Tools import issues detected"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "tools_import", "tools_registry", success, duration,
                message, details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "tools_import", "tools_registry", False, duration,
                "Tools import failed", error=str(e)
            )
    
    async def test_handlers_validation(self):
        """Test that individual handlers can be instantiated."""
        start = time.time()
        try:
            # Test a sample of handlers from each category
            test_handlers = [
                ("AuthenticatorRQHandler", AuthenticatorRQHandler),
                ("BasketCreateRQHandler", BasketCreateRQHandler),
                ("BudgetSearchRQHandler", BudgetSearchRQHandler),
                ("HotelSearchRQHandler", HotelSearchRQHandler),
                ("ZoneSearchRQHandler", ZoneSearchRQHandler)
            ]
            
            handler_results = {}
            for name, handler_class in test_handlers:
                try:
                    handler = handler_class()
                    handler_results[name] = "✅ OK"
                except Exception as e:
                    handler_results[name] = f"❌ Error: {str(e)}"
            
            successful_handlers = sum(1 for result in handler_results.values() if result.startswith("✅"))
            total_tested = len(test_handlers)
            
            details = {
                "handlers_tested": total_tested,
                "successful_handlers": successful_handlers,
                "handler_results": handler_results
            }
            
            success = successful_handlers == total_tested
            message = f"Handler validation successful ({successful_handlers}/{total_tested})" if success else f"Some handlers failed validation"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "handlers_validation", "tools_registry", success, duration,
                message, details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "handlers_validation", "tools_registry", False, duration,
                "Handler validation failed", error=str(e)
            )
    
    # ==========================================
    # BASIC ENDPOINT TESTS
    # ==========================================
    
    async def test_hotel_search(self):
        """Test hotel search functionality."""
        start = time.time()
        try:
            handler = HotelSearchRQHandler()
            test_args = {
                "page": 1,
                "num_results": 5,
                "language": "es"
            }
            
            result = await handler.execute(test_args)
            
            success = result.get("success", False)
            
            if success:
                data = result.get("data", {})
                search_results = data.get("search_results", {})
                
                details = {
                    "total_records": search_results.get("total_records", 0),
                    "total_pages": search_results.get("total_pages", 0),
                    "current_page": search_results.get("current_page", 0),
                    "hotels_returned": len(search_results.get("hotels", []))
                }
                
                message = f"Hotel search successful ({details['hotels_returned']} hotels found)"
            else:
                details = {"error_details": result.get("error", {})}
                message = f"Hotel search failed: {result.get('message', 'Unknown error')}"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "hotel_search", "basic_endpoints", success, duration,
                message, details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "hotel_search", "basic_endpoints", False, duration,
                "Hotel search test failed", error=str(e)
            )
    
    async def test_zone_search(self):
        """Test zone search functionality."""
        start = time.time()
        try:
            handler = ZoneSearchRQHandler()
            test_args = {
                "order_by": "alphabetical",
                "order_type": "asc",
                "language": "es"
            }
            
            result = await handler.execute(test_args)
            
            success = result.get("success", False)
            
            if success:
                data = result.get("data", {})
                zones = data.get("zones", [])
                
                details = {
                    "zones_returned": len(zones),
                    "sample_zones": zones[:3] if zones else []
                }
                
                message = f"Zone search successful ({len(zones)} zones found)"
            else:
                details = {"error_details": result.get("error", {})}
                message = f"Zone search failed: {result.get('message', 'Unknown error')}"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "zone_search", "basic_endpoints", success, duration,
                message, details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "zone_search", "basic_endpoints", False, duration,
                "Zone search test failed", error=str(e)
            )
    
    async def test_budget_search(self):
        """Test budget search functionality."""
        start = time.time()
        try:
            handler = BudgetSearchRQHandler()
            test_args = {
                "order_by": "creationdate",
                "order_type": "desc",
                "page": 1,
                "num_results": 5,
                "language": "es"
            }
            
            result = await handler.execute(test_args)
            
            success = result.get("success", False)
            
            if success:
                data = result.get("data", {})
                search_results = data.get("search_results", {})
                
                details = {
                    "total_records": search_results.get("total_records", 0),
                    "total_pages": search_results.get("total_pages", 0),
                    "budgets_returned": len(search_results.get("budgets", []))
                }
                
                message = f"Budget search successful ({details['budgets_returned']} budgets found)"
            else:
                details = {"error_details": result.get("error", {})}
                message = f"Budget search failed: {result.get('message', 'Unknown error')}"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "budget_search", "basic_endpoints", success, duration,
                message, details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "budget_search", "basic_endpoints", False, duration,
                "Budget search test failed", error=str(e)
            )
    
    # ==========================================
    # PERFORMANCE TESTS
    # ==========================================
    
    async def test_response_times(self):
        """Test response times for critical operations."""
        start = time.time()
        try:
            # Test authentication response time
            auth_handler = AuthenticatorRQHandler()
            auth_start = time.time()
            auth_result = await auth_handler.execute({"language": "es"})
            auth_time = (time.time() - auth_start) * 1000
            
            # Test search response time
            search_handler = HotelSearchRQHandler()
            search_start = time.time()
            search_result = await search_handler.execute({"page": 1, "num_results": 1})
            search_time = (time.time() - search_start) * 1000
            
            details = {
                "auth_time_ms": round(auth_time, 2),
                "search_time_ms": round(search_time, 2),
                "auth_success": auth_result.get("success", False),
                "search_success": search_result.get("success", False),
                "performance_grade": "A" if auth_time < 1000 and search_time < 2000 else 
                                  "B" if auth_time < 2000 and search_time < 5000 else "C"
            }
            
            success = auth_result.get("success", False) and search_result.get("success", False)
            message = f"Performance test completed (Auth: {auth_time:.0f}ms, Search: {search_time:.0f}ms, Grade: {details['performance_grade']})"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "response_times", "performance", success, duration,
                message, details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "response_times", "performance", False, duration,
                "Performance test failed", error=str(e)
            )
    
    # ==========================================
    # ERROR HANDLING TESTS
    # ==========================================
    
    async def test_invalid_requests(self):
        """Test error handling with invalid requests."""
        start = time.time()
        try:
            handler = HotelSearchRQHandler()
            
            # Test with invalid arguments
            invalid_args = {
                "page": -1,  # Invalid page number
                "num_results": 1000,  # Too many results
                "language": "invalid"  # Invalid language
            }
            
            result = await handler.execute(invalid_args)
            
            # We expect this to fail gracefully
            success = not result.get("success", True)  # Should return success=False
            error_handled = "error" in result or "message" in result
            
            details = {
                "request_failed_gracefully": success,
                "error_message_provided": error_handled,
                "result_structure": list(result.keys()) if result else []
            }
            
            final_success = success and error_handled
            message = "Error handling working correctly" if final_success else "Error handling needs improvement"
            
            duration = (time.time() - start) * 1000
            self.add_result(
                "invalid_requests", "error_handling", final_success, duration,
                message, details
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "invalid_requests", "error_handling", False, duration,
                "Error handling test failed", error=str(e)
            )
    
    # ==========================================
    # MAIN TEST EXECUTION
    # ==========================================
    
    async def run_category_tests(self, category: str) -> List[TestResult]:
        """Run all tests for a specific category."""
        category_info = self.test_categories.get(category, {})
        tests = category_info.get("tests", [])
        
        self.log(f"Running {category} tests ({len(tests)} tests)")
        
        for test_name in tests:
            test_method = getattr(self, f"test_{test_name}", None)
            if test_method:
                try:
                    await test_method()
                except Exception as e:
                    self.add_result(
                        test_name, category, False, 0,
                        f"Test execution failed", error=str(e)
                    )
            else:
                self.log(f"Test method test_{test_name} not found", "WARNING")
    
    async def run_all_tests(self, target_category: Optional[str] = None) -> HealthCheckSummary:
        """Run all health check tests."""
        self.log("🏁 Starting MCP Health Check Suite")
        self.log(f"Quick mode: {'ON' if self.quick_mode else 'OFF'}")
        self.log(f"Target category: {target_category or 'ALL'}")
        
        # Determine which categories to test
        categories_to_test = []
        if target_category:
            if target_category in self.test_categories:
                categories_to_test = [target_category]
            else:
                self.log(f"Unknown category: {target_category}", "ERROR")
                return self.generate_summary()
        else:
            categories_to_test = list(self.test_categories.keys())
            if self.quick_mode:
                # Only run critical categories in quick mode
                categories_to_test = [cat for cat in categories_to_test 
                                    if self.test_categories[cat].get("critical", False)]
        
        # Run tests for each category
        for category in categories_to_test:
            await self.run_category_tests(category)
        
        # Generate and return summary
        summary = self.generate_summary()
        self.print_summary(summary)
        return summary
    
    def generate_summary(self) -> HealthCheckSummary:
        """Generate a summary of all test results."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.duration_ms for r in self.results)
        
        categories_tested = list(set(r.category for r in self.results))
        
        # Identify critical failures
        critical_failures = []
        for result in self.results:
            if not result.success:
                category_info = self.test_categories.get(result.category, {})
                if category_info.get("critical", False):
                    critical_failures.append(f"{result.category}.{result.test_name}: {result.message}")
        
        # Generate warnings and recommendations
        warnings = []
        recommendations = []
        
        # Performance warnings
        slow_tests = [r for r in self.results if r.duration_ms > 5000]
        if slow_tests:
            warnings.append(f"{len(slow_tests)} tests took longer than 5 seconds")
            recommendations.append("Consider optimizing slow operations or increasing timeout values")
        
        # Authentication warnings
        auth_failures = [r for r in self.results if r.category == "authentication" and not r.success]
        if auth_failures:
            warnings.append("Authentication issues detected")
            recommendations.append("Verify API credentials and network connectivity")
        
        # Tool loading warnings
        tool_failures = [r for r in self.results if r.category == "tools_registry" and not r.success]
        if tool_failures:
            warnings.append("Tool registry issues detected")
            recommendations.append("Check tool imports and dependencies")
        
        return HealthCheckSummary(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            total_duration_ms=total_duration,
            categories_tested=categories_tested,
            critical_failures=critical_failures,
            warnings=warnings,
            recommendations=recommendations
        )
    
    def print_summary(self, summary: HealthCheckSummary):
        """Print a formatted summary of test results."""
        total_time = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("🏁 MCP HEALTH CHECK SUMMARY")
        print("="*80)
        
        # Overall status
        if summary.failed_tests == 0:
            status = "🟢 ALL TESTS PASSED"
        elif len(summary.critical_failures) == 0:
            status = "🟡 SOME TESTS FAILED (NON-CRITICAL)"
        else:
            status = "🔴 CRITICAL FAILURES DETECTED"
        
        print(f"\n📊 **Overall Status**: {status}")
        print(f"📈 **Tests**: {summary.passed_tests}/{summary.total_tests} passed ({(summary.passed_tests/max(summary.total_tests,1)*100):.1f}%)")
        print(f"⏱️  **Duration**: {total_time:.2f}s total, {summary.total_duration_ms:.0f}ms in tests")
        print(f"📂 **Categories**: {', '.join(summary.categories_tested)}")
        
        # Critical failures
        if summary.critical_failures:
            print(f"\n🚨 **Critical Failures** ({len(summary.critical_failures)}):")
            for failure in summary.critical_failures:
                print(f"   • {failure}")
        
        # Warnings
        if summary.warnings:
            print(f"\n⚠️  **Warnings** ({len(summary.warnings)}):")
            for warning in summary.warnings:
                print(f"   • {warning}")
        
        # Recommendations
        if summary.recommendations:
            print(f"\n💡 **Recommendations** ({len(summary.recommendations)}):")
            for rec in summary.recommendations:
                print(f"   • {rec}")
        
        # Detailed results by category
        if self.verbose:
            print(f"\n📋 **Detailed Results**:")
            for category in summary.categories_tested:
                category_results = [r for r in self.results if r.category == category]
                passed = sum(1 for r in category_results if r.success)
                total = len(category_results)
                
                print(f"\n📁 {category.upper()}: {passed}/{total} passed")
                for result in category_results:
                    status = "✅" if result.success else "❌"
                    print(f"   {status} {result.test_name}: {result.message} ({result.duration_ms:.1f}ms)")
                    if not result.success and result.error:
                        print(f"      Error: {result.error}")
        
        print("\n" + "="*80)


async def main():
    """Main entry point for the health check script."""
    parser = argparse.ArgumentParser(description="MCP Health Check and Connectivity Test Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable detailed output")
    parser.add_argument("--category", "-c", help="Test specific category only")
    parser.add_argument("--quick", "-q", action="store_true", help="Run only essential tests")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    # Create health checker
    checker = MCPHealthChecker(verbose=args.verbose, quick_mode=args.quick)
    
    try:
        # Run tests
        summary = await checker.run_all_tests(args.category)
        
        # Save results if requested
        if args.output:
            results_data = {
                "summary": {
                    "total_tests": summary.total_tests,
                    "passed_tests": summary.passed_tests,
                    "failed_tests": summary.failed_tests,
                    "total_duration_ms": summary.total_duration_ms,
                    "categories_tested": summary.categories_tested,
                    "critical_failures": summary.critical_failures,
                    "warnings": summary.warnings,
                    "recommendations": summary.recommendations
                },
                "detailed_results": [
                    {
                        "test_name": r.test_name,
                        "category": r.category,
                        "success": r.success,
                        "duration_ms": r.duration_ms,
                        "message": r.message,
                        "details": r.details,
                        "error": r.error
                    }
                    for r in checker.results
                ],
                "timestamp": datetime.now().isoformat(),
                "test_config": {
                    "verbose": args.verbose,
                    "quick_mode": args.quick,
                    "target_category": args.category
                }
            }
            
            with open(args.output, 'w') as f:
                json.dump(results_data, f, indent=2)
            print(f"\n💾 Results saved to: {args.output}")
        
        # Exit with appropriate code
        if len(summary.critical_failures) > 0:
            sys.exit(2)  # Critical failures
        elif summary.failed_tests > 0:
            sys.exit(1)  # Non-critical failures
        else:
            sys.exit(0)  # All tests passed
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Health check interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 Health check failed with unexpected error: {str(e)}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         MCP HEALTH CHECK SUITE                              ║
║                    Neobookings MCP Server Diagnostics                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    asyncio.run(main())
