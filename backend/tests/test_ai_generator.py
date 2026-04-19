"""Tests for ai_generator.py and ollama_generator.py — tool format conversion,
arg sanitization, factory, and response handling."""
import json
from unittest.mock import MagicMock, patch, call
import pytest


ANTHROPIC_TOOL = {
    "name": "search_course_content",
    "description": "Search course materials",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "course_name": {"type": "string", "description": "Course name"},
            "lesson_number": {"type": "integer", "description": "Lesson number"},
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# OllamaGenerator._convert_tools
# ---------------------------------------------------------------------------

class TestConvertTools:
    def test_output_has_type_function(self):
        from ollama_generator import OllamaGenerator
        result = OllamaGenerator._convert_tools([ANTHROPIC_TOOL])
        assert result[0]["type"] == "function"

    def test_output_has_function_key(self):
        from ollama_generator import OllamaGenerator
        result = OllamaGenerator._convert_tools([ANTHROPIC_TOOL])
        assert "function" in result[0]

    def test_renames_input_schema_to_parameters(self):
        from ollama_generator import OllamaGenerator
        fn = OllamaGenerator._convert_tools([ANTHROPIC_TOOL])[0]["function"]
        assert "parameters" in fn
        assert "input_schema" not in fn

    def test_parameters_content_is_identical_to_input_schema(self):
        from ollama_generator import OllamaGenerator
        fn = OllamaGenerator._convert_tools([ANTHROPIC_TOOL])[0]["function"]
        assert fn["parameters"] == ANTHROPIC_TOOL["input_schema"]

    def test_preserves_tool_name(self):
        from ollama_generator import OllamaGenerator
        fn = OllamaGenerator._convert_tools([ANTHROPIC_TOOL])[0]["function"]
        assert fn["name"] == "search_course_content"

    def test_preserves_tool_description(self):
        from ollama_generator import OllamaGenerator
        fn = OllamaGenerator._convert_tools([ANTHROPIC_TOOL])[0]["function"]
        assert fn["description"] == "Search course materials"

    def test_converts_multiple_tools(self):
        from ollama_generator import OllamaGenerator
        second = {**ANTHROPIC_TOOL, "name": "another_tool"}
        result = OllamaGenerator._convert_tools([ANTHROPIC_TOOL, second])
        assert len(result) == 2

    def test_empty_list_returns_empty_list(self):
        from ollama_generator import OllamaGenerator
        assert OllamaGenerator._convert_tools([]) == []


# ---------------------------------------------------------------------------
# OllamaGenerator._sanitize_tool_args  (these tests FAIL before the fix)
# ---------------------------------------------------------------------------

class TestSanitizeToolArgs:
    def test_flattens_single_key_type_dict_to_string(self):
        """Core regression test: {'type': 'MCP'} → 'MCP'."""
        from ollama_generator import OllamaGenerator
        args = {"query": "what is MCP", "course_name": {"type": "MCP"}}
        result = OllamaGenerator._sanitize_tool_args(args)
        assert result["course_name"] == "MCP"

    def test_leaves_plain_string_unchanged(self):
        from ollama_generator import OllamaGenerator
        args = {"query": "what is RAG"}
        result = OllamaGenerator._sanitize_tool_args(args)
        assert result["query"] == "what is RAG"

    def test_leaves_integer_unchanged(self):
        from ollama_generator import OllamaGenerator
        args = {"query": "lesson content", "lesson_number": 3}
        result = OllamaGenerator._sanitize_tool_args(args)
        assert result["lesson_number"] == 3

    def test_leaves_none_unchanged(self):
        from ollama_generator import OllamaGenerator
        args = {"query": "test", "course_name": None}
        result = OllamaGenerator._sanitize_tool_args(args)
        assert result["course_name"] is None

    def test_does_not_flatten_multi_key_dict(self):
        """A dict with >1 key is not the {'type': x} pattern — leave it alone."""
        from ollama_generator import OllamaGenerator
        multi = {"type": "string", "description": "a field"}
        args = {"course_name": multi}
        result = OllamaGenerator._sanitize_tool_args(args)
        assert result["course_name"] == multi

    def test_handles_empty_args(self):
        from ollama_generator import OllamaGenerator
        assert OllamaGenerator._sanitize_tool_args({}) == {}


# ---------------------------------------------------------------------------
# create_generator factory
# ---------------------------------------------------------------------------

class TestCreateGenerator:
    def test_returns_ai_generator_for_anthropic(self):
        from ai_generator import create_generator, AIGenerator
        config = MagicMock()
        config.PROVIDER = "anthropic"
        config.ANTHROPIC_API_KEY = "test-key"
        config.ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
        assert isinstance(create_generator(config), AIGenerator)

    def test_returns_ollama_generator_for_ollama(self):
        from ai_generator import create_generator
        from ollama_generator import OllamaGenerator
        config = MagicMock()
        config.PROVIDER = "ollama"
        config.OLLAMA_MODEL = "llama3.2"
        config.OLLAMA_BASE_URL = "http://localhost:11434/v1"
        assert isinstance(create_generator(config), OllamaGenerator)

    def test_provider_check_is_case_insensitive(self):
        from ai_generator import create_generator, AIGenerator
        config = MagicMock()
        config.PROVIDER = "Anthropic"
        config.ANTHROPIC_API_KEY = "test-key"
        config.ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
        assert isinstance(create_generator(config), AIGenerator)

    def test_raises_value_error_for_unknown_provider(self):
        from ai_generator import create_generator
        config = MagicMock()
        config.PROVIDER = "openai"
        with pytest.raises(ValueError, match="openai"):
            create_generator(config)


# ---------------------------------------------------------------------------
# OllamaGenerator.generate_response
# ---------------------------------------------------------------------------

@pytest.fixture
def ollama_gen():
    """OllamaGenerator with a mocked OpenAI client."""
    from ollama_generator import OllamaGenerator
    mock_client = MagicMock()
    with patch("ollama_generator.OpenAI", return_value=mock_client):
        gen = OllamaGenerator("llama3.2", "http://localhost:11434/v1")
    gen._client = mock_client  # expose for assertions
    return gen, mock_client


class TestOllamaGeneratorResponse:
    def _make_choice(self, finish_reason, content=None, tool_calls=None):
        choice = MagicMock()
        choice.finish_reason = finish_reason
        choice.message.content = content
        choice.message.tool_calls = tool_calls or []
        return choice

    def test_returns_text_directly_when_no_tool_call(self, ollama_gen):
        gen, client = ollama_gen
        choice = self._make_choice("stop", content="Direct answer")
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        result = gen.generate_response("What is RAG?")
        assert result == "Direct answer"

    def test_calls_api_once_for_direct_response(self, ollama_gen):
        gen, client = ollama_gen
        choice = self._make_choice("stop", content="Answer")
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        gen.generate_response("Simple question")
        assert client.chat.completions.create.call_count == 1

    def test_calls_api_twice_when_tool_use_triggered(self, ollama_gen):
        gen, client = ollama_gen
        tool_call = MagicMock()
        tool_call.id = "call_1"
        tool_call.function.name = "search_course_content"
        tool_call.function.arguments = json.dumps({"query": "MCP"})

        first_choice = self._make_choice("tool_calls", tool_calls=[tool_call])
        second_choice = self._make_choice("stop", content="Synthesized answer")

        client.chat.completions.create.side_effect = [
            MagicMock(choices=[first_choice]),
            MagicMock(choices=[second_choice]),
        ]
        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "search results"

        result = gen.generate_response("Tell me about MCP course", tool_manager=mock_tm)
        assert result == "Synthesized answer"
        assert client.chat.completions.create.call_count == 2

    def test_tool_manager_execute_tool_is_called(self, ollama_gen):
        gen, client = ollama_gen
        tool_call = MagicMock()
        tool_call.id = "call_1"
        tool_call.function.name = "search_course_content"
        tool_call.function.arguments = json.dumps({"query": "MCP overview"})

        first_choice = self._make_choice("tool_calls", tool_calls=[tool_call])
        second_choice = self._make_choice("stop", content="Final")

        client.chat.completions.create.side_effect = [
            MagicMock(choices=[first_choice]),
            MagicMock(choices=[second_choice]),
        ]
        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "search results"

        gen.generate_response("MCP question", tool_manager=mock_tm)
        mock_tm.execute_tool.assert_called_once_with(
            "search_course_content", query="MCP overview"
        )

    def test_handle_tool_execution_sanitizes_dict_course_name(self, ollama_gen):
        """Regression test: dict args like {'type': 'MCP'} must be flattened to 'MCP'."""
        gen, client = ollama_gen

        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function.name = "search_course_content"
        # Malformed args as Ollama would produce them
        tool_call.function.arguments = json.dumps({
            "query": "what is MCP",
            "course_name": {"type": "MCP"},
        })

        assistant_msg = MagicMock()
        assistant_msg.tool_calls = [tool_call]
        initial_response = MagicMock(choices=[MagicMock(message=assistant_msg)])

        final_choice = self._make_choice("stop", content="Final answer")
        client.chat.completions.create.return_value = MagicMock(choices=[final_choice])

        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "search result"

        gen._handle_tool_execution(initial_response, [{"role": "user", "content": "q"}], mock_tm)

        # The critical assertion: execute_tool must receive "MCP" string, not the dict
        mock_tm.execute_tool.assert_called_once_with(
            "search_course_content",
            query="what is MCP",
            course_name="MCP",  # sanitized from {"type": "MCP"}
        )
