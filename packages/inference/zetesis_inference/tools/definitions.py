"""Tool definitions in the OpenAI function-calling format that Qwen understands."""

TOOL_DEFINITIONS = {
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. Use this when you need "
                "up-to-date facts, recent developments, specific data, or to verify claims. "
                "Returns a list of relevant snippets with source URLs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and include relevant keywords.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    "knowledge_search": {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": (
                "Search the user's personal knowledge base of previous research outputs. "
                "Use this to find relevant prior research, build on existing findings, "
                "or check if a topic has already been investigated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Semantic search query over previous research outputs.",
                    }
                },
                "required": ["query"],
            },
        },
    },
}

# All available tool names
ALL_TOOL_NAMES = list(TOOL_DEFINITIONS.keys())


def get_tool_definitions(tool_names: list[str]) -> list[dict]:
    """Get tool definitions for a list of tool names."""
    return [TOOL_DEFINITIONS[name] for name in tool_names if name in TOOL_DEFINITIONS]
