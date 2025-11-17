#!/usr/bin/env python3
"""
Quick MCP Connectivity Test
===========================

A lightweight script for quick connectivity and basic functionality testing
of the Neobookings MCP Server. This script focuses on essential checks only.

Usage:
    python quick_test.py
"""

import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import NeobookingsConfig, NeobookingsHTTPClient, create_authentication_request


class QuickTester:
    """Quick connectivity tester for MCP."""
    
    def __init__(self):
        self.start_time = time.time()
        self.tests_run = 0
        self.tests_passed = 0
    
    def log(self, message: str, status: str = "INFO"):
        """Log with timestamp and status."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")
    
    async def test_config(self):
        """Test configuration loading."""
        self.tests_run += 1
        try:
            config = NeobookingsConfig.from_env()
            required = ["client_code", "system_code", "username", "password", "base_url"]
            
            for field in required:
                if not getattr(config, field, None):
                    raise ValueError(f"Missing {field}")
            
            self.log(f"✅ Configuration OK (URL: {config.base_url})", "PASS")
            self.tests_passed += 1
            return config
            
        except Exception as e:
            self.log(f"❌ Configuration FAILED: {e}", "FAIL")
            return None
    
    async def test_connectivity(self, config):
        """Test API connectivity."""
        self.tests_run += 1
        if not config:
            self.log("❌ Connectivity SKIPPED (no config)", "SKIP")
            return False
        
        try:
            start = time.time()
            async with NeobookingsHTTPClient(config) as client:
                auth_request = create_authentication_request(config)
                response = await client.post("/AuthenticatorRQ", auth_request, require_auth=False)
                
                duration = (time.time() - start) * 1000
                
                if response.get("Token"):
                    self.log(f"✅ Connectivity OK ({duration:.0f}ms)", "PASS")
                    self.tests_passed += 1
                    return True
                else:
                    self.log(f"❌ Connectivity FAILED: No token received", "FAIL")
                    return False
                    
        except Exception as e:
            self.log(f"❌ Connectivity FAILED: {e}", "FAIL")
            return False
    
    async def test_tools_loading(self):
        """Test tools loading."""
        self.tests_run += 1
        try:
            import main
            
            total_tools = len(main.ALL_TOOLS)
            expected = 51
            
            if total_tools == expected:
                self.log(f"✅ Tools Loading OK ({total_tools}/{expected} tools)", "PASS")
                self.tests_passed += 1
                return True
            else:
                self.log(f"❌ Tools Loading FAILED: {total_tools}/{expected} tools", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"❌ Tools Loading FAILED: {e}", "FAIL")
            return False
    
    async def test_basic_functionality(self, config):
        """Test basic functionality with a simple search."""
        self.tests_run += 1
        if not config:
            self.log("❌ Basic Function SKIPPED (no config)", "SKIP")
            return False
        
        try:
            from tools.cthotelinventory.hotel_search_rq import HotelSearchRQHandler
            
            start = time.time()
            handler = HotelSearchRQHandler()
            result = await handler.execute({
                "page": 1,
                "num_results": 1,
                "language": "es"
            })
            duration = (time.time() - start) * 1000
            
            if result.get("success"):
                self.log(f"✅ Basic Function OK ({duration:.0f}ms)", "PASS")
                self.tests_passed += 1
                return True
            else:
                self.log(f"❌ Basic Function FAILED: {result.get('message', 'Unknown error')}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"❌ Basic Function FAILED: {e}", "FAIL")
            return False
    
    async def run_all_tests(self):
        """Run all quick tests."""
        self.log("🚀 Starting Quick MCP Test Suite")
        
        # Test configuration
        config = await self.test_config()
        
        # Test connectivity
        connectivity_ok = await self.test_connectivity(config)
        
        # Test tools loading
        tools_ok = await self.test_tools_loading()
        
        # Test basic functionality
        function_ok = await self.test_basic_functionality(config)
        
        # Summary
        total_time = time.time() - self.start_time
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        
        print("\n" + "="*60)
        print("📊 QUICK TEST SUMMARY")
        print("="*60)
        
        if self.tests_passed == self.tests_run:
            overall_status = "🟢 ALL TESTS PASSED"
        elif self.tests_passed >= self.tests_run * 0.5:
            overall_status = "🟡 PARTIAL SUCCESS"
        else:
            overall_status = "🔴 MULTIPLE FAILURES"
        
        print(f"Status: {overall_status}")
        print(f"Tests:  {self.tests_passed}/{self.tests_run} passed ({success_rate:.0f}%)")
        print(f"Time:   {total_time:.2f}s")
        
        # Individual test status
        print(f"\nComponent Status:")
        print(f"  • Configuration: {'✅ OK' if config else '❌ FAIL'}")
        print(f"  • Connectivity:  {'✅ OK' if connectivity_ok else '❌ FAIL'}")
        print(f"  • Tools Loading: {'✅ OK' if tools_ok else '❌ FAIL'}")
        print(f"  • Basic Function:{'✅ OK' if function_ok else '❌ FAIL'}")
        
        if self.tests_passed == self.tests_run:
            print(f"\n🎉 MCP Server is ready for use!")
        else:
            print(f"\n⚠️  Some issues detected. Run 'python test_mcp_health.py --verbose' for detailed diagnostics.")
        
        print("="*60)
        
        return self.tests_passed == self.tests_run


async def main():
    """Main entry point."""
    tester = QuickTester()
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    print("🔬 Quick MCP Connectivity Test")
    print("-" * 30)
    asyncio.run(main())
