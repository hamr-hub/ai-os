"""Tool Definitions for Agent System

Provides a registry system for defining and managing tools that agents can use.
"""
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import json


class ParameterType(str, Enum):
    """JSON Schema parameter types"""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Defines a tool parameter with JSON Schema validation"""
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    items: Optional[Dict[str, Any]] = None  # For array type

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format for OpenAI function calling"""
        schema: Dict[str, Any] = {
            "type": self.type.value,
            "description": self.description
        }

        if self.enum:
            schema["enum"] = self.enum

        if self.type in (ParameterType.NUMBER, ParameterType.INTEGER):
            if self.min_value is not None:
                schema["minimum"] = self.min_value
            if self.max_value is not None:
                schema["maximum"] = self.max_value

        if self.type == ParameterType.ARRAY and self.items:
            schema["items"] = self.items

        return schema


@dataclass
class ToolDefinition:
    """Defines a tool that can be called by an agent"""
    name: str
    description: str
    parameters: List[ToolParameter]
    handler: Optional[Callable[..., Awaitable[Any]]] = None
    category: str = "general"
    examples: List[Dict[str, Any]] = field(default_factory=list)
    dangerous: bool = False  # Mark tools that could have side effects
    requires_confirmation: bool = False  # Require user confirmation before execution

    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format"""
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolRegistry:
    """Registry for managing available tools"""

    _instance: Optional['ToolRegistry'] = None

    def __new__(cls) -> 'ToolRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: Dict[str, ToolDefinition] = {}
            cls._instance._categories: Dict[str, List[str]] = {}
            cls._instance._register_builtin_tools()
        return cls._instance

    def _register_builtin_tools(self) -> None:
        """Register built-in tools"""
        # System Information Tool
        self.register(ToolDefinition(
            name="get_system_info",
            description="Get current system information including CPU, memory, and GPU status",
            parameters=[],
            category="system",
            dangerous=False
        ))

        # Model Management Tools
        self.register(ToolDefinition(
            name="list_models",
            description="List all available models and their status",
            parameters=[],
            category="models",
            dangerous=False
        ))

        self.register(ToolDefinition(
            name="start_model",
            description="Start a specific model by name",
            parameters=[
                ToolParameter(
                    name="model_name",
                    type=ParameterType.STRING,
                    description="Name of the model to start",
                    required=True
                )
            ],
            category="models",
            dangerous=True,
            requires_confirmation=True
        ))

        self.register(ToolDefinition(
            name="stop_model",
            description="Stop a specific model by name",
            parameters=[
                ToolParameter(
                    name="model_name",
                    type=ParameterType.STRING,
                    description="Name of the model to stop",
                    required=True
                )
            ],
            category="models",
            dangerous=True,
            requires_confirmation=True
        ))

        self.register(ToolDefinition(
            name="switch_model",
            description="Switch to a specific model, stopping others if necessary",
            parameters=[
                ToolParameter(
                    name="model_name",
                    type=ParameterType.STRING,
                    description="Name of the model to switch to",
                    required=True
                )
            ],
            category="models",
            dangerous=True,
            requires_confirmation=True
        ))

        # GPU Management Tools
        self.register(ToolDefinition(
            name="get_gpu_status",
            description="Get detailed GPU status including memory usage and temperature",
            parameters=[],
            category="gpu",
            dangerous=False
        ))

        self.register(ToolDefinition(
            name="optimize_gpu_memory",
            description="Optimize GPU memory usage by clearing cache and adjusting parameters",
            parameters=[
                ToolParameter(
                    name="strategy",
                    type=ParameterType.STRING,
                    description="Optimization strategy to use",
                    enum=["conservative", "balanced", "aggressive"],
                    default="balanced",
                    required=False
                )
            ],
            category="gpu",
            dangerous=True,
            requires_confirmation=True
        ))

        # Chat Tools
        self.register(ToolDefinition(
            name="search_conversations",
            description="Search through conversation history",
            parameters=[
                ToolParameter(
                    name="query",
                    type=ParameterType.STRING,
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="limit",
                    type=ParameterType.INTEGER,
                    description="Maximum number of results to return",
                    default=10,
                    min_value=1,
                    max_value=100,
                    required=False
                )
            ],
            category="chat",
            dangerous=False
        ))

        # File Operations (if enabled)
        self.register(ToolDefinition(
            name="read_file",
            description="Read content from a file in the workspace",
            parameters=[
                ToolParameter(
                    name="file_path",
                    type=ParameterType.STRING,
                    description="Path to the file to read",
                    required=True
                )
            ],
            category="files",
            dangerous=False
        ))

        self.register(ToolDefinition(
            name="write_file",
            description="Write content to a file in the workspace",
            parameters=[
                ToolParameter(
                    name="file_path",
                    type=ParameterType.STRING,
                    description="Path to the file to write",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type=ParameterType.STRING,
                    description="Content to write to the file",
                    required=True
                )
            ],
            category="files",
            dangerous=True,
            requires_confirmation=True
        ))

        # Web Tools
        self.register(ToolDefinition(
            name="web_search",
            description="Search the web for information",
            parameters=[
                ToolParameter(
                    name="query",
                    type=ParameterType.STRING,
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="num_results",
                    type=ParameterType.INTEGER,
                    description="Number of results to return",
                    default=5,
                    min_value=1,
                    max_value=20,
                    required=False
                )
            ],
            category="web",
            dangerous=False
        ))

        # vLLM Management Tools
        self.register(ToolDefinition(
            name="get_vllm_metrics",
            description="Get vLLM inference engine metrics including running/waiting requests, cache usage, TTFT, TPOT, and throughput",
            parameters=[],
            category="vllm",
            dangerous=False
        ))

        self.register(ToolDefinition(
            name="restart_vllm_service",
            description="Restart the vLLM inference service (stops and starts the service with the current model)",
            parameters=[
                ToolParameter(
                    name="model_name",
                    type=ParameterType.STRING,
                    description="Name of the model to restart (uses current model if not specified)",
                    required=False
                )
            ],
            category="vllm",
            dangerous=True,
            requires_confirmation=True
        ))

        self.register(ToolDefinition(
            name="get_engine_status",
            description="Get status of all LLM engine backends (vLLM, SGLang, llama.cpp) including running state, port, and health",
            parameters=[],
            category="vllm",
            dangerous=False
        ))

        self.register(ToolDefinition(
            name="switch_engine",
            description="Switch the LLM engine backend (e.g., from vLLM to SGLang or vice versa)",
            parameters=[
                ToolParameter(
                    name="engine_type",
                    type=ParameterType.STRING,
                    description="Target engine type to switch to",
                    enum=["vllm", "sglang", "llamacpp"],
                    required=True
                ),
                ToolParameter(
                    name="model_name",
                    type=ParameterType.STRING,
                    description="Model name to use with the new engine",
                    required=False
                )
            ],
            category="vllm",
            dangerous=True,
            requires_confirmation=True
        ))

    def register(self, tool: ToolDefinition) -> None:
        """Register a new tool"""
        self._tools[tool.name] = tool

        if tool.category not in self._categories:
            self._categories[tool.category] = []
        self._categories[tool.category].append(tool.name)

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name"""
        if name in self._tools:
            tool = self._tools[name]
            self._categories[tool.category].remove(name)
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name"""
        return self._tools.get(name)

    def get_all(self) -> List[ToolDefinition]:
        """Get all registered tools"""
        return list(self._tools.values())

    def get_by_category(self, category: str) -> List[ToolDefinition]:
        """Get tools by category"""
        return [self._tools[name] for name in self._categories.get(category, [])]

    def get_openai_tools(self, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get tools in OpenAI function calling format"""
        if categories:
            tools = []
            for cat in categories:
                tools.extend(self.get_by_category(cat))
        else:
            tools = self.get_all()
        return [t.to_openai_function() for t in tools]

    def get_categories(self) -> List[str]:
        """Get all tool categories"""
        return list(self._categories.keys())

    def tool_exists(self, name: str) -> bool:
        """Check if a tool exists"""
        return name in self._tools

    def is_dangerous(self, name: str) -> bool:
        """Check if a tool requires confirmation"""
        tool = self.get(name)
        return tool.dangerous if tool else False

    def requires_confirmation(self, name: str) -> bool:
        """Check if a tool requires user confirmation"""
        tool = self.get(name)
        return tool.requires_confirmation if tool else False
