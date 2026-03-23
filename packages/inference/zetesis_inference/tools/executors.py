"""Tool executor functions. Each takes parsed arguments and returns a string result."""

import logging
import httpx

logger = logging.getLogger(__name__)


async def execute_web_search(query: str) -> str:
    """Execute a web search via the Brave Search API."""
    from zetesis_core.config import settings

    if not settings.brave_search_api_key:
        return "Error: Brave Search API key not configured. Set BRAVE_SEARCH_API_KEY in .env"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.brave_search_api_key,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("web", {}).get("results", [])
        if not results:
            return f"No results found for: {query}"

        lines = []
        for r in results[:5]:
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("description", "")
            lines.append(f"**{title}**\n{url}\n{snippet}")

        return "\n\n".join(lines)

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Search failed: {e}"


async def execute_knowledge_search(query: str) -> str:
    """Search the Zetesis knowledge base using embeddings."""
    try:
        from zetesis_server.services.embedding import generate_embedding
        from zetesis_server.db.engine import async_session
        from sqlalchemy import text

        embedding = await generate_embedding(query)
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with async_session() as db:
            stmt = text("""
                SELECT o.content, r.query,
                       1 - (o.embedding <=> CAST(:embedding AS vector)) as score
                FROM outputs o
                JOIN requests r ON r.id = o.request_id
                WHERE o.embedding IS NOT NULL
                ORDER BY o.embedding <=> CAST(:embedding AS vector)
                LIMIT 3
            """)
            result = await db.execute(stmt, {"embedding": embedding_str})
            rows = result.mappings().all()

        if not rows:
            return "No previous research found in the knowledge base."

        lines = []
        for r in rows:
            if r["score"] < 0.1:
                continue
            lines.append(
                f"**Previous research** (relevance: {r['score']:.2f})\n"
                f"Query: {r['query']}\n"
                f"Output (first 500 chars): {r['content'][:500]}"
            )

        return "\n\n---\n\n".join(lines) if lines else "No sufficiently relevant previous research found."

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return f"Knowledge search failed: {e}"


# Registry mapping tool names to executor functions
TOOL_EXECUTORS = {
    "web_search": execute_web_search,
    "knowledge_search": execute_knowledge_search,
}


async def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments."""
    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        return f"Unknown tool: {tool_name}"

    if tool_name == "web_search":
        return await executor(arguments.get("query", ""))
    elif tool_name == "knowledge_search":
        return await executor(arguments.get("query", ""))
    else:
        return f"No executor for tool: {tool_name}"
