#!/usr/bin/env python3
"""
Interactive MCP Endpoint Tester
===============================

An interactive testing tool for individual MCP endpoints.
Allows testing specific tools with custom parameters.

Usage:
    python test_endpoints.py
    python test_endpoints.py --tool hotel_search_rq
    python test_endpoints.py --list-tools
"""

import asyncio
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class EndpointTester:
    """Interactive endpoint testing tool."""
    
    def __init__(self):
        self.available_tools = {}
        self.load_tools()
    
    def load_tools(self):
        """Load all available tools and their handlers."""
        try:
            import main
            
            # Create mapping of tool names to handlers
            for tool_name, handler_func in main.TOOL_HANDLERS.items():
                # Get the tool definition
                tool_def = None
                for tool in main.ALL_TOOLS:
                    if tool.name == tool_name:
                        tool_def = tool
                        break
                
                if tool_def:
                    self.available_tools[tool_name] = {
                        "handler": handler_func,
                        "definition": tool_def,
                        "category": self.get_tool_category(tool_name, main.TOOL_CATEGORIES)
                    }
            
            print(f"✅ Loaded {len(self.available_tools)} tools")
            
        except Exception as e:
            print(f"❌ Failed to load tools: {e}")
            sys.exit(1)
    
    def get_tool_category(self, tool_name: str, categories: Dict) -> str:
        """Get the category for a tool."""
        for category, tools in categories.items():
            if tool_name in tools:
                return category
        return "unknown"
    
    def list_tools(self):
        """List all available tools organized by category."""
        print("\n📋 Available MCP Tools")
        print("=" * 50)
        
        # Group tools by category
        by_category = {}
        for tool_name, tool_info in self.available_tools.items():
            category = tool_info["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(tool_name)
        
        # Display by category
        for category, tools in sorted(by_category.items()):
            category_display = category.replace("_", " ").title()
            print(f"\n📁 {category_display} ({len(tools)} tools):")
            for tool in sorted(tools):
                tool_def = self.available_tools[tool]["definition"]
                description = tool_def.description.split('\n')[1].strip() if '\n' in tool_def.description else tool_def.description[:80]
                print(f"   • {tool}: {description}")
        
        print(f"\n💡 Total: {len(self.available_tools)} tools available")
        print("   Use --tool <tool_name> to test a specific tool")
    
    def get_tool_info(self, tool_name: str):
        """Get detailed information about a specific tool."""
        if tool_name not in self.available_tools:
            print(f"❌ Tool '{tool_name}' not found")
            return None
        
        tool_info = self.available_tools[tool_name]
        tool_def = tool_info["definition"]
        
        print(f"\n🔧 Tool: {tool_name}")
        print("=" * 50)
        print(f"📁 Category: {tool_info['category'].replace('_', ' ').title()}")
        print(f"📝 Description:")
        
        # Clean and display description
        desc_lines = tool_def.description.strip().split('\n')
        for line in desc_lines:
            if line.strip():
                print(f"   {line.strip()}")
        
        # Display input schema
        print(f"\n📥 Input Parameters:")
        schema = tool_def.inputSchema
        if schema and "properties" in schema:
            self.display_schema(schema["properties"], indent="   ")
        else:
            print("   No parameters required")
        
        return tool_info
    
    def display_schema(self, properties: Dict, indent: str = ""):
        """Display schema properties in a readable format."""
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "unknown")
            description = prop_info.get("description", "No description")
            required = prop_info.get("required", False)
            default = prop_info.get("default")
            enum_values = prop_info.get("enum")
            
            # Build property line
            prop_line = f"{indent}• {prop_name} ({prop_type})"
            if required:
                prop_line += " [REQUIRED]"
            if default is not None:
                prop_line += f" [default: {default}]"
            
            print(prop_line)
            print(f"{indent}  {description}")
            
            if enum_values:
                print(f"{indent}  Valid values: {', '.join(map(str, enum_values))}")
            
            # Handle nested objects
            if prop_type == "object" and "properties" in prop_info:
                print(f"{indent}  Properties:")
                self.display_schema(prop_info["properties"], indent + "    ")
    
    def get_sample_arguments(self, tool_name: str) -> Dict[str, Any]:
        """Generate sample arguments for a tool."""
        tool_info = self.available_tools.get(tool_name)
        if not tool_info:
            return {}
        
        schema = tool_info["definition"].inputSchema
        if not schema or "properties" not in schema:
            return {}
        
        samples = {}
        properties = schema["properties"]
        
        # Generate sample values based on common patterns
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "string")
            default = prop_info.get("default")
            enum_values = prop_info.get("enum")
            
            if default is not None:
                samples[prop_name] = default
            elif enum_values:
                samples[prop_name] = enum_values[0]
            elif prop_type == "string":
                if "language" in prop_name.lower():
                    samples[prop_name] = "es"
                elif "date" in prop_name.lower():
                    samples[prop_name] = "2024-12-01"
                elif "id" in prop_name.lower():
                    samples[prop_name] = "sample_id_123"
                else:
                    samples[prop_name] = "sample_value"
            elif prop_type == "number" or prop_type == "integer":
                if "page" in prop_name.lower():
                    samples[prop_name] = 1
                elif "num_results" in prop_name.lower() or "limit" in prop_name.lower():
                    samples[prop_name] = 10
                else:
                    samples[prop_name] = 1
            elif prop_type == "boolean":
                samples[prop_name] = False
            elif prop_type == "array":
                samples[prop_name] = []
            elif prop_type == "object":
                samples[prop_name] = {}
        
        return samples
    
    async def test_tool(self, tool_name: str, arguments: Dict[str, Any] = None):
        """Test a specific tool with given arguments."""
        if tool_name not in self.available_tools:
            print(f"❌ Tool '{tool_name}' not found")
            return False
        
        tool_info = self.available_tools[tool_name]
        handler = tool_info["handler"]
        
        # Use provided arguments or generate samples
        if arguments is None:
            arguments = self.get_sample_arguments(tool_name)
        
        print(f"\n🧪 Testing tool: {tool_name}")
        print("-" * 40)
        print(f"📥 Arguments: {json.dumps(arguments, indent=2)}")
        
        start_time = datetime.now()
        
        try:
            # Call the tool handler
            result = await handler(arguments)
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            print(f"⏱️  Duration: {duration:.0f}ms")
            print(f"✅ Test completed successfully")
            
            # Display result
            if result and len(result) > 0:
                print(f"\n📤 Result ({len(result)} item(s)):")
                for i, item in enumerate(result):
                    if hasattr(item, 'text'):
                        # TextContent
                        text = item.text
                        if len(text) > 500:
                            text = text[:500] + "... (truncated)"
                        print(f"   [{i+1}] Text: {text}")
                    elif hasattr(item, 'type'):
                        # Other content types
                        print(f"   [{i+1}] Type: {item.type}")
                    else:
                        print(f"   [{i+1}] {str(item)[:200]}")
            else:
                print(f"\n📤 Result: Empty or no result")
            
            return True
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            print(f"⏱️  Duration: {duration:.0f}ms")
            print(f"❌ Test failed: {str(e)}")
            
            # Show traceback in verbose mode
            import traceback
            print(f"\n🔍 Error details:")
            print(traceback.format_exc())
            
            return False
    
    async def interactive_mode(self):
        """Run in interactive mode."""
        print("\n🎮 Interactive MCP Endpoint Tester")
        print("=" * 40)
        print("Commands:")
        print("  list - Show all available tools")
        print("  info <tool_name> - Show tool information")
        print("  test <tool_name> - Test tool with sample data")
        print("  custom <tool_name> - Test tool with custom arguments")
        print("  quit - Exit")
        
        while True:
            try:
                command = input("\n> ").strip().split()
                if not command:
                    continue
                
                cmd = command[0].lower()
                
                if cmd == "quit" or cmd == "exit":
                    print("👋 Goodbye!")
                    break
                elif cmd == "list":
                    self.list_tools()
                elif cmd == "info" and len(command) > 1:
                    tool_name = command[1]
                    self.get_tool_info(tool_name)
                elif cmd == "test" and len(command) > 1:
                    tool_name = command[1]
                    await self.test_tool(tool_name)
                elif cmd == "custom" and len(command) > 1:
                    tool_name = command[1]
                    print(f"\n📝 Enter custom arguments for {tool_name} (JSON format):")
                    print("   Example: {\"language\": \"es\", \"page\": 1}")
                    args_input = input("Arguments: ").strip()
                    
                    if args_input:
                        try:
                            custom_args = json.loads(args_input)
                            await self.test_tool(tool_name, custom_args)
                        except json.JSONDecodeError as e:
                            print(f"❌ Invalid JSON: {e}")
                    else:
                        await self.test_tool(tool_name)
                else:
                    print("❌ Unknown command or missing arguments")
                    print("   Use 'list' to see available tools")
            
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Interactive MCP Endpoint Tester")
    parser.add_argument("--tool", "-t", help="Test specific tool")
    parser.add_argument("--list-tools", action="store_true", help="List all available tools")
    parser.add_argument("--args", "-a", help="Tool arguments as JSON string")
    
    args = parser.parse_args()
    
    tester = EndpointTester()
    
    try:
        if args.list_tools:
            tester.list_tools()
        elif args.tool:
            # Test specific tool
            tool_name = args.tool
            
            # Parse arguments if provided
            tool_args = None
            if args.args:
                try:
                    tool_args = json.loads(args.args)
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON arguments: {e}")
                    sys.exit(1)
            
            # Show tool info first
            tester.get_tool_info(tool_name)
            
            # Test the tool
            success = await tester.test_tool(tool_name, tool_args)
            sys.exit(0 if success else 1)
        else:
            # Interactive mode
            await tester.interactive_mode()
    
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🔧 MCP Endpoint Tester v1.0")
    asyncio.run(main())
