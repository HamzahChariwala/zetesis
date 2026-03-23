import asyncio
import json
import logging
import re

from zetesis_core.enums import RequestType
from zetesis_core.interfaces import InferenceBackend
from zetesis_core.models import GenerationParams
from zetesis_inference.prompt.builder import build_messages
from zetesis_inference.tools.definitions import get_tool_definitions
from zetesis_inference.tools.executors import execute_tool
from zetesis_server.db.models import OutputRow
from zetesis_server.queue.manager import QueueManager
from zetesis_server.services.embedding import generate_embedding

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5

# Qwen 2.5 native format: <tool_call>{"name": ..., "arguments": ...}</tool_call>
TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)

# Qwen 3.x alternate format: <tool_call>{"name": ..., "arguments": ...}</tool_call>
# (same pattern, but Qwen 3 sometimes also uses <function=name><parameter=key>value</parameter></function>)
QWEN3_TOOL_PATTERN = re.compile(
    r"<function=(\w+)>\s*<parameter=(\w+)>\s*(.*?)\s*</parameter>\s*</function>", re.DOTALL
)

THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


def clean_output(text: str) -> str:
    """Remove thinking blocks and other model artifacts from the output."""
    text = THINK_PATTERN.sub("", text)
    return text.strip()


def parse_tool_calls(text: str) -> list[dict]:
    """Parse tool calls from model output. Handles both Qwen 2.5 and 3.x formats."""
    calls = []

    # Try Qwen 2.5 native format first: <tool_call>{"name": ..., "arguments": ...}</tool_call>
    for match in TOOL_CALL_PATTERN.finditer(text):
        try:
            parsed = json.loads(match.group(1))
            if "name" in parsed and "arguments" in parsed:
                calls.append(parsed)
        except json.JSONDecodeError:
            continue

    if calls:
        return calls

    # Try Qwen 3.x format: <function=name><parameter=key>value</parameter></function>
    for match in QWEN3_TOOL_PATTERN.finditer(text):
        func_name = match.group(1)
        param_name = match.group(2)
        param_value = match.group(3).strip()
        calls.append({"name": func_name, "arguments": {param_name: param_value}})

    return calls


class InferenceWorker:
    def __init__(self, queue: QueueManager, backend: InferenceBackend):
        self._queue = queue
        self._backend = backend
        self._running = False
        self._poll_interval = 0.5
        self._max_poll_interval = 5.0

    async def run(self):
        self._running = True
        logger.info("InferenceWorker started")
        while self._running:
            request = await self._queue.dequeue()
            if request is None:
                await asyncio.sleep(self._poll_interval)
                self._poll_interval = min(self._poll_interval * 1.5, self._max_poll_interval)
                continue

            self._poll_interval = 0.5
            logger.info(f"Processing request {request.id}: {request.query[:80]}")

            try:
                messages = build_messages(
                    query=request.query,
                    request_type=RequestType(request.type),
                    context=request.context,
                )
                params = GenerationParams()
                tool_names = request.tools or []
                tool_defs = get_tool_definitions(tool_names) if tool_names else None

                if tool_defs:
                    result = await self._agentic_loop_tracked(
                        messages, params, request.model_id, tool_defs
                    )
                else:
                    # Simple single-shot generation
                    result = await self._backend.generate(
                        messages, params, model_path=request.model_id
                    )

                result.text = clean_output(result.text)
                truncated = result.token_count >= params.max_tokens
                embedding = await generate_embedding(result.text)

                output = OutputRow(
                    request_id=request.id,
                    content=result.text,
                    model_id=result.model_id,
                    inference_time_ms=result.inference_time_ms,
                    token_count=result.token_count,
                    truncated=truncated,
                    embedding=embedding,
                )
                await self._queue.complete(request.id, output)
                logger.info(
                    f"Completed request {request.id} in {result.inference_time_ms}ms "
                    f"({result.token_count} tokens, embedding generated)"
                )
            except Exception as e:
                logger.error(f"Failed request {request.id}: {e}")
                await self._queue.fail(request.id, str(e))

    async def _agentic_loop_tracked(
        self,
        messages: list[dict],
        params: GenerationParams,
        model_path: str | None,
        tool_defs: list[dict],
    ):
        """Run the agentic tool-calling loop and return a single GenerationResult."""
        from zetesis_core.models import GenerationResult
        import time

        total_tokens = 0
        total_ms = 0
        start = time.monotonic()

        for round_num in range(MAX_TOOL_ROUNDS):
            result = await self._backend.generate(
                messages, params, model_path=model_path, tools=tool_defs
            )
            total_tokens += result.token_count
            total_ms += result.inference_time_ms

            # Check if the model made tool calls
            tool_calls = parse_tool_calls(result.text)
            if not tool_calls:
                # No tool calls — this is the final answer
                return GenerationResult(
                    text=result.text,
                    token_count=total_tokens,
                    inference_time_ms=total_ms,
                    model_id=result.model_id,
                )

            # Execute tool calls and add results to messages
            messages.append({"role": "assistant", "content": result.text})
            logger.info(
                f"  Round {round_num + 1}: {len(tool_calls)} tool call(s): "
                f"{[tc['name'] for tc in tool_calls]}"
            )

            for tc in tool_calls:
                tool_result = await execute_tool(tc["name"], tc["arguments"])
                messages.append({"role": "tool", "content": tool_result})
                logger.info(f"    {tc['name']}({tc['arguments']}) → {len(tool_result)} chars")

        # Hit max rounds — do one final generation without tools to force an answer
        logger.info(f"  Hit max tool rounds ({MAX_TOOL_ROUNDS}), generating final answer")
        messages.append({
            "role": "user",
            "content": "Please provide your final answer now based on all the information gathered.",
        })
        result = await self._backend.generate(messages, params, model_path=model_path)
        total_tokens += result.token_count
        total_ms += result.inference_time_ms

        return GenerationResult(
            text=result.text,
            token_count=total_tokens,
            inference_time_ms=total_ms,
            model_id=result.model_id,
        )

    def stop(self):
        self._running = False
