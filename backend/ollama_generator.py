import json
import logging
from openai import OpenAI
from typing import List, Optional, Dict, Any

logger = logging.getLogger("rag.ollama")


class OllamaGenerator:
    """Handles interactions with a local Ollama model via its OpenAI-compatible API."""

    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- **One search per query maximum**
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, model: str, base_url: str, debug: bool = False):
        # api_key="ollama" is a required non-empty placeholder; Ollama ignores it
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model = model
        self.debug = debug

    def _dbg(self, msg: str):
        if self.debug:
            logger.debug(msg)

    @staticmethod
    def _sanitize_tool_args(args: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize args from local models that wrap scalar values as {'type': value}.

        Some local Ollama models produce e.g. {"course_name": {"type": "MCP"}} instead
        of {"course_name": "MCP"}.  Detect the pattern (single-key dict whose only key
        is "type") and unwrap it so downstream code receives the plain scalar value.
        """
        result = {}
        for key, value in args.items():
            if isinstance(value, dict) and list(value.keys()) == ["type"]:
                result[key] = value["type"]
            else:
                result[key] = value
        return result

    @staticmethod
    def _looks_like_text_tool_call(content: str) -> bool:
        """Detect when a small model outputs a tool call as plain text instead of using
        the function-calling API (finish_reason=stop but content is JSON)."""
        if not content:
            return False
        stripped = content.strip()
        return stripped.startswith("{") and (
            '"name"' in stripped or '"function"' in stripped or "tool_call" in stripped.lower()
        )

    @staticmethod
    def _convert_tools(anthropic_tools: List[Dict]) -> List[Dict]:
        """Convert Anthropic tool format to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t["input_schema"],
                },
            }
            for t in anthropic_tools
        ]

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        self._dbg(f"--- New query ---")
        self._dbg(f"Model: {self.model}")
        self._dbg(f"Query: {query[:120]!r}")
        self._dbg(f"History present: {bool(conversation_history)}")
        self._dbg(f"Tools available: {len(tools) if tools else 0}")

        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 800,
        }

        if tools:
            converted = self._convert_tools(tools)
            kwargs["tools"] = converted
            kwargs["tool_choice"] = "auto"
            if self.debug:
                tool_names = [t["function"]["name"] for t in converted]
                self._dbg(f"Tool definitions sent: {tool_names}")

        response = self.client.chat.completions.create(**kwargs)
        finish_reason = response.choices[0].finish_reason
        content = response.choices[0].message.content

        self._dbg(f"Response finish_reason: {finish_reason!r}")

        if finish_reason == "tool_calls":
            self._dbg("Tool call requested by model — executing...")
            return self._handle_tool_execution(response, messages, tool_manager)

        # Detect the common small-model failure: outputting a JSON tool call as plain text
        if self._looks_like_text_tool_call(content or ""):
            logger.warning(
                f"[RAG] Model '{self.model}' returned a tool call as plain text instead of "
                f"using the function-calling API (finish_reason='{finish_reason}'). "
                f"Tool calling is not working reliably with this model. "
                f"Small models (1B/3B) support the tool-calling API but may not follow "
                f"schemas consistently. A larger model will be more reliable "
                f"(e.g. llama3.1:8b, mistral:7b, qwen2.5:7b, gemma4:27b)."
            )
            self._dbg(f"Raw text tool call output: {(content or '')[:300]}")

        self._dbg(f"Direct text response: {(content or '')[:200]!r}")
        return content

    def _handle_tool_execution(self, initial_response, messages: List, tool_manager) -> str:
        assistant_message = initial_response.choices[0].message
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            raw_args = json.loads(tool_call.function.arguments)
            sanitized_args = self._sanitize_tool_args(raw_args)

            self._dbg(f"Tool call: {tool_call.function.name}")
            self._dbg(f"  Raw args:       {raw_args}")
            if raw_args != sanitized_args:
                self._dbg(f"  Sanitized args: {sanitized_args}  ← args were normalized")
            else:
                self._dbg(f"  Args (no change needed): {sanitized_args}")

            result = tool_manager.execute_tool(tool_call.function.name, **sanitized_args)

            self._dbg(f"  Tool result ({len(result)} chars): {result[:300]!r}")

            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result}
            )

        final = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            max_tokens=800,
        )
        final_content = final.choices[0].message.content
        self._dbg(f"Final synthesized response: {(final_content or '')[:200]!r}")
        return final_content
