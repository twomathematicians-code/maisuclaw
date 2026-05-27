"""
maisuclaw v0.3.0 — Tool Registry
Manages all available tools and their execution.
"""

from tools.file_tool import execute as file_execute
from tools.code_tool import execute as code_execute
from tools.calc_tool import execute as calc_execute
from tools import web_tool


# Tool definitions for the AI model
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "file_operations",
            "description": "Read, write, list, search files and get file info on the local filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "list", "search", "info"],
                        "description": "Action to perform"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for 'write' action)"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (for 'search' action)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute Python code and return the output. Use for calculations, data processing, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute"
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate mathematical expressions safely",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate (supports +, -, *, /, ^, %, parentheses)"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet using DuckDuckGo. Returns titles, URLs and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
]


async def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name and return the result."""
    if name == "file_operations":
        return file_execute(arguments.get("action", ""), arguments)
    elif name == "execute_code":
        return code_execute(arguments.get("code", ""))
    elif name == "calculator":
        return calc_execute(arguments.get("expression", ""))
    elif name == "web_search":
        return await web_tool.search(arguments.get("query", ""))
    else:
        return f"Unknown tool: {name}"
