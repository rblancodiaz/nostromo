#!/usr/bin/env python3
"""
MCP Performance Benchmark Suite
===============================

Performance testing and benchmarking tool for the Neobookings MCP Server.
Tests response times, throughput, and resource usage.

Usage:
    python benchmark_mcp.py
    python benchmark_mcp.py --quick
    python benchmark_mcp.py --concurrent 5
"""

import asyncio
import sys
import time
import statistics
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import psutil
import gc

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import NeobookingsConfig


@dataclass
class BenchmarkResult:
    """Individual benchmark result."""
    test_name: str
    duration_ms: float
    success: bool
    memory_usage_mb: float
    error: str = None


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results."""
    test_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    min_time_ms: float
    max_time_ms: float
    avg_time_ms: float
    median_time_ms: float
    p95_time_ms: float
    throughput_per_sec: float
    avg_memory_mb: float
    success_rate: float


class PerformanceBenchmark:
    """Performance benchmark runner."""
    
    def __init__(self, concurrent: int = 1, quick_mode: bool = False):
        self.concurrent = concurrent
        self.quick_mode = quick_mode
        self.config = None
        self.results: List[BenchmarkResult] = []
        
        # Benchmark test configurations
        self.benchmark_tests = {
            "authentication": {
                "description": "Authentication speed test",
                "runs": 10 if not quick_mode else 3,
                "timeout": 30
            },
            "hotel_search": {
                "description": "Hotel search performance",
                "runs": 20 if not quick_mode else 5,
                "timeout": 30
            },
            "zone_search": {
                "description": "Zone search performance",
                "runs": 15 if not quick_mode else 3,
                "timeout": 20
            },
            "budget_search": {
                "description": "Budget search performance",
                "runs": 10 if not quick_mode else 3,
                "timeout": 30
            },
            "concurrent_auth": {
                "description": "Concurrent authentication test",
                "runs": self.concurrent * 5,
                "timeout": 60
            }
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    async def setup(self):
        """Setup benchmark environment."""
        try:
            self.config = NeobookingsConfig.from_env()
            self.log("Configuration loaded successfully")
            
            # Warm up by loading tools
            import main
            self.log(f"Tools loaded: {len(main.ALL_TOOLS)} available")
            
            return True
        except Exception as e:
            self.log(f"Setup failed: {e}", "ERROR")
            return False
    
    async def single_auth_test(self) -> BenchmarkResult:
        """Single authentication test."""
        start_memory = self.get_memory_usage()
        start_time = time.time()
        
        try:
            from tools.ctauthentication.authenticator_rq import AuthenticatorRQHandler
            
            handler = AuthenticatorRQHandler()
            result = await handler.execute({"language": "es"})
            
            success = result.get("success", False)
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="authentication",
                duration_ms=duration_ms,
                success=success,
                memory_usage_mb=memory_usage,
                error=None if success else result.get("message", "Unknown error")
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="authentication",
                duration_ms=duration_ms,
                success=False,
                memory_usage_mb=memory_usage,
                error=str(e)
            )
    
    async def single_hotel_search_test(self) -> BenchmarkResult:
        """Single hotel search test."""
        start_memory = self.get_memory_usage()
        start_time = time.time()
        
        try:
            from tools.cthotelinventory.hotel_search_rq import HotelSearchRQHandler
            
            handler = HotelSearchRQHandler()
            result = await handler.execute({
                "page": 1,
                "num_results": 10,
                "language": "es"
            })
            
            success = result.get("success", False)
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="hotel_search",
                duration_ms=duration_ms,
                success=success,
                memory_usage_mb=memory_usage,
                error=None if success else result.get("message", "Unknown error")
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="hotel_search",
                duration_ms=duration_ms,
                success=False,
                memory_usage_mb=memory_usage,
                error=str(e)
            )
    
    async def single_zone_search_test(self) -> BenchmarkResult:
        """Single zone search test."""
        start_memory = self.get_memory_usage()
        start_time = time.time()
        
        try:
            from tools.ctgeosearch.zone_search_rq import ZoneSearchRQHandler
            
            handler = ZoneSearchRQHandler()
            result = await handler.execute({
                "order_by": "alphabetical",
                "order_type": "asc",
                "language": "es"
            })
            
            success = result.get("success", False)
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="zone_search",
                duration_ms=duration_ms,
                success=success,
                memory_usage_mb=memory_usage,
                error=None if success else result.get("message", "Unknown error")
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="zone_search",
                duration_ms=duration_ms,
                success=False,
                memory_usage_mb=memory_usage,
                error=str(e)
            )
    
    async def single_budget_search_test(self) -> BenchmarkResult:
        """Single budget search test."""
        start_memory = self.get_memory_usage()
        start_time = time.time()
        
        try:
            from tools.ctbudget.budget_search_rq import BudgetSearchRQHandler
            
            handler = BudgetSearchRQHandler()
            result = await handler.execute({
                "order_by": "creationdate",
                "order_type": "desc",
                "page": 1,
                "num_results": 5,
                "language": "es"
            })
            
            success = result.get("success", False)
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="budget_search",
                duration_ms=duration_ms,
                success=success,
                memory_usage_mb=memory_usage,
                error=None if success else result.get("message", "Unknown error")
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            memory_usage = self.get_memory_usage() - start_memory
            
            return BenchmarkResult(
                test_name="budget_search",
                duration_ms=duration_ms,
                success=False,
                memory_usage_mb=memory_usage,
                error=str(e)
            )
    
    async def concurrent_auth_test(self, count: int) -> List[BenchmarkResult]:
        """Concurrent authentication test."""
        tasks = []
        for i in range(count):
            tasks.append(self.single_auth_test())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        benchmark_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                benchmark_results.append(BenchmarkResult(
                    test_name="concurrent_auth",
                    duration_ms=0,
                    success=False,
                    memory_usage_mb=0,
                    error=str(result)
                ))
            else:
                result.test_name = "concurrent_auth"
                benchmark_results.append(result)
        
        return benchmark_results
    
    async def run_benchmark_series(self, test_name: str, test_func, runs: int) -> List[BenchmarkResult]:
        """Run a series of benchmark tests."""
        self.log(f"Running {test_name} benchmark ({runs} runs)")
        results = []
        
        for i in range(runs):
            if i > 0 and i % 5 == 0:
                self.log(f"  Completed {i}/{runs} runs")
                # Force garbage collection every 5 runs
                gc.collect()
                await asyncio.sleep(0.1)  # Brief pause
            
            if test_name == "concurrent_auth":
                # Special handling for concurrent test
                concurrent_results = await self.concurrent_auth_test(self.concurrent)
                results.extend(concurrent_results)
                break  # Only run once for concurrent test
            else:
                result = await test_func()
                results.append(result)
        
        return results
    
    def calculate_summary(self, test_name: str, results: List[BenchmarkResult]) -> BenchmarkSummary:
        """Calculate benchmark summary statistics."""
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        if not successful_results:
            return BenchmarkSummary(
                test_name=test_name,
                total_runs=len(results),
                successful_runs=0,
                failed_runs=len(failed_results),
                min_time_ms=0,
                max_time_ms=0,
                avg_time_ms=0,
                median_time_ms=0,
                p95_time_ms=0,
                throughput_per_sec=0,
                avg_memory_mb=0,
                success_rate=0
            )
        
        durations = [r.duration_ms for r in successful_results]
        memory_usage = [r.memory_usage_mb for r in successful_results]
        
        # Calculate statistics
        min_time = min(durations)
        max_time = max(durations)
        avg_time = statistics.mean(durations)
        median_time = statistics.median(durations)
        p95_time = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max_time
        
        # Calculate throughput (requests per second)
        total_test_time = sum(durations) / 1000  # Convert to seconds
        throughput = len(successful_results) / total_test_time if total_test_time > 0 else 0
        
        avg_memory = statistics.mean(memory_usage) if memory_usage else 0
        success_rate = len(successful_results) / len(results) * 100
        
        return BenchmarkSummary(
            test_name=test_name,
            total_runs=len(results),
            successful_runs=len(successful_results),
            failed_runs=len(failed_results),
            min_time_ms=min_time,
            max_time_ms=max_time,
            avg_time_ms=avg_time,
            median_time_ms=median_time,
            p95_time_ms=p95_time,
            throughput_per_sec=throughput,
            avg_memory_mb=avg_memory,
            success_rate=success_rate
        )
    
    async def run_all_benchmarks(self) -> Dict[str, BenchmarkSummary]:
        """Run all benchmark tests."""
        if not await self.setup():
            return {}
        
        summaries = {}
        total_start_time = time.time()
        
        self.log("🚀 Starting Performance Benchmark Suite")
        self.log(f"Configuration: Concurrent={self.concurrent}, Quick={'ON' if self.quick_mode else 'OFF'}")
        
        # Run each benchmark test
        for test_name, config in self.benchmark_tests.items():
            test_start_time = time.time()
            
            if test_name == "authentication":
                results = await self.run_benchmark_series(test_name, self.single_auth_test, config["runs"])
            elif test_name == "hotel_search":
                results = await self.run_benchmark_series(test_name, self.single_hotel_search_test, config["runs"])
            elif test_name == "zone_search":
                results = await self.run_benchmark_series(test_name, self.single_zone_search_test, config["runs"])
            elif test_name == "budget_search":
                results = await self.run_benchmark_series(test_name, self.single_budget_search_test, config["runs"])
            elif test_name == "concurrent_auth":
                results = await self.run_benchmark_series(test_name, None, config["runs"])
            else:
                continue
            
            test_duration = time.time() - test_start_time
            summary = self.calculate_summary(test_name, results)
            summaries[test_name] = summary
            
            self.log(f"✅ {test_name} completed in {test_duration:.1f}s "
                    f"(Success: {summary.success_rate:.1f}%, Avg: {summary.avg_time_ms:.0f}ms)")
        
        total_duration = time.time() - total_start_time
        self.log(f"🏁 All benchmarks completed in {total_duration:.1f}s")
        
        return summaries
    
    def print_detailed_summary(self, summaries: Dict[str, BenchmarkSummary]):
        """Print detailed benchmark summary."""
        print("\n" + "="*80)
        print("📊 PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        # Overall statistics
        total_runs = sum(s.total_runs for s in summaries.values())
        total_successful = sum(s.successful_runs for s in summaries.values())
        overall_success_rate = (total_successful / total_runs * 100) if total_runs > 0 else 0
        
        print(f"\n🎯 **Overall Statistics**")
        print(f"   • Total Tests: {total_runs}")
        print(f"   • Successful: {total_successful}")
        print(f"   • Success Rate: {overall_success_rate:.1f}%")
        print(f"   • Concurrency: {self.concurrent}")
        
        # Detailed results for each test
        for test_name, summary in summaries.items():
            test_display = test_name.replace("_", " ").title()
            
            print(f"\n📈 **{test_display}**")
            print(f"   • Runs: {summary.successful_runs}/{summary.total_runs} successful ({summary.success_rate:.1f}%)")
            print(f"   • Response Times:")
            print(f"     - Average: {summary.avg_time_ms:.0f}ms")
            print(f"     - Median: {summary.median_time_ms:.0f}ms")
            print(f"     - Min/Max: {summary.min_time_ms:.0f}ms / {summary.max_time_ms:.0f}ms")
            print(f"     - 95th Percentile: {summary.p95_time_ms:.0f}ms")
            print(f"   • Throughput: {summary.throughput_per_sec:.1f} requests/sec")
            print(f"   • Memory Usage: {summary.avg_memory_mb:.1f}MB average")
            
            if summary.failed_runs > 0:
                print(f"   • ⚠️  {summary.failed_runs} failed runs")
        
        # Performance grades
        print(f"\n🏆 **Performance Grades**")
        for test_name, summary in summaries.items():
            if summary.successful_runs == 0:
                grade = "F"
                grade_emoji = "❌"
            elif summary.avg_time_ms < 1000:
                grade = "A"
                grade_emoji = "🟢"
            elif summary.avg_time_ms < 2000:
                grade = "B"
                grade_emoji = "🔵"
            elif summary.avg_time_ms < 5000:
                grade = "C"
                grade_emoji = "🟡"
            else:
                grade = "D"
                grade_emoji = "🟠"
            
            test_display = test_name.replace("_", " ").title()
            print(f"   {grade_emoji} {test_display}: Grade {grade} ({summary.avg_time_ms:.0f}ms avg)")
        
        # Recommendations
        print(f"\n💡 **Recommendations**")
        recommendations = []
        
        # Response time recommendations
        slow_tests = [name for name, summary in summaries.items() if summary.avg_time_ms > 3000]
        if slow_tests:
            recommendations.append(f"Optimize slow operations: {', '.join(slow_tests)}")
        
        # Success rate recommendations
        failing_tests = [name for name, summary in summaries.items() if summary.success_rate < 90]
        if failing_tests:
            recommendations.append(f"Investigate reliability issues in: {', '.join(failing_tests)}")
        
        # Memory recommendations
        high_memory_tests = [name for name, summary in summaries.items() if summary.avg_memory_mb > 50]
        if high_memory_tests:
            recommendations.append(f"Review memory usage in: {', '.join(high_memory_tests)}")
        
        # Throughput recommendations
        low_throughput_tests = [name for name, summary in summaries.items() if summary.throughput_per_sec < 1]
        if low_throughput_tests:
            recommendations.append(f"Improve throughput for: {', '.join(low_throughput_tests)}")
        
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"   {i}. {rec}")
        else:
            print("   🎉 Performance looks good! No major issues detected.")
        
        print("\n" + "="*80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP Performance Benchmark Suite")
    parser.add_argument("--concurrent", "-c", type=int, default=1, help="Number of concurrent requests")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick benchmark mode (fewer runs)")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    # Validate concurrent parameter
    if args.concurrent < 1 or args.concurrent > 20:
        print("❌ Concurrent parameter must be between 1 and 20")
        sys.exit(1)
    
    benchmark = PerformanceBenchmark(
        concurrent=args.concurrent,
        quick_mode=args.quick
    )
    
    try:
        summaries = await benchmark.run_all_benchmarks()
        
        if summaries:
            benchmark.print_detailed_summary(summaries)
            
            # Save to file if requested
            if args.output:
                import json
                
                results_data = {
                    "timestamp": datetime.now().isoformat(),
                    "config": {
                        "concurrent": args.concurrent,
                        "quick_mode": args.quick
                    },
                    "summaries": {
                        name: {
                            "test_name": s.test_name,
                            "total_runs": s.total_runs,
                            "successful_runs": s.successful_runs,
                            "failed_runs": s.failed_runs,
                            "min_time_ms": s.min_time_ms,
                            "max_time_ms": s.max_time_ms,
                            "avg_time_ms": s.avg_time_ms,
                            "median_time_ms": s.median_time_ms,
                            "p95_time_ms": s.p95_time_ms,
                            "throughput_per_sec": s.throughput_per_sec,
                            "avg_memory_mb": s.avg_memory_mb,
                            "success_rate": s.success_rate
                        }
                        for name, s in summaries.items()
                    }
                }
                
                with open(args.output, 'w') as f:
                    json.dump(results_data, f, indent=2)
                print(f"\n💾 Results saved to: {args.output}")
            
            # Determine exit code based on results
            overall_success_rate = sum(s.successful_runs for s in summaries.values()) / sum(s.total_runs for s in summaries.values()) * 100
            if overall_success_rate >= 90:
                sys.exit(0)
            elif overall_success_rate >= 50:
                sys.exit(1)
            else:
                sys.exit(2)
        else:
            print("❌ No benchmark results generated")
            sys.exit(3)
    
    except KeyboardInterrupt:
        print("\n⏹️  Benchmark interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         MCP PERFORMANCE BENCHMARK                           ║
║                      Neobookings Server Performance Test                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    asyncio.run(main())
