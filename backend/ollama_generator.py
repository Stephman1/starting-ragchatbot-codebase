import json
from openai import OpenAI
from typing import List, Optional, Dict, Any


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

    def __init__(self, model: str, base_url: str):
        # api_key="ollama" is a required non-empty placeholder; Ollama ignores it
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model = model

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
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)

        if response.choices[0].finish_reason == "tool_calls" and tool_manager:
            return self._handle_tool_execution(response, messages, tool_manager)

        return response.choices[0].message.content

    def _handle_tool_execution(self, initial_response, messages: List, tool_manager) -> str:
        assistant_message = initial_response.choices[0].message
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = tool_manager.execute_tool(tool_call.function.name, **args)
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result}
            )

        final = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            max_tokens=800,
        )
        return final.choices[0].message.content
