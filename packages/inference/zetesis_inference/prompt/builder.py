from zetesis_core.enums import RequestType
from zetesis_inference.prompt.templates import SYSTEM_PROMPTS


def build_messages(
    query: str, request_type: RequestType, context: str | None = None
) -> list[dict[str, str]]:
    """Build a chat message list for the model's chat template."""
    system_prompt = SYSTEM_PROMPTS[request_type]

    user_content = query
    if context:
        user_content = f"Background context:\n{context}\n\nQuestion:\n{query}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
