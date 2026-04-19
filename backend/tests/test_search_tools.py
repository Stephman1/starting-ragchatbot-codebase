"""Tests for search_tools.py — CourseSearchTool and ToolManager."""
from unittest.mock import MagicMock
import pytest

from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def tool(mock_store):
    return CourseSearchTool(mock_store)


@pytest.fixture
def manager(tool):
    mgr = ToolManager()
    mgr.register_tool(tool)
    return mgr


# ---------------------------------------------------------------------------
# Tool definition structure
# ---------------------------------------------------------------------------

class TestCourseSearchToolDefinition:
    def test_has_name_field(self, tool):
        assert "name" in tool.get_tool_definition()

    def test_has_description_field(self, tool):
        assert "description" in tool.get_tool_definition()

    def test_has_input_schema_field(self, tool):
        assert "input_schema" in tool.get_tool_definition()

    def test_name_is_search_course_content(self, tool):
        assert tool.get_tool_definition()["name"] == "search_course_content"

    def test_schema_type_is_object(self, tool):
        assert tool.get_tool_definition()["input_schema"]["type"] == "object"

    def test_schema_required_contains_query(self, tool):
        required = tool.get_tool_definition()["input_schema"]["required"]
        assert "query" in required

    def test_schema_query_property_is_string_type(self, tool):
        props = tool.get_tool_definition()["input_schema"]["properties"]
        assert props["query"]["type"] == "string"

    def test_schema_has_optional_course_name_property(self, tool):
        props = tool.get_tool_definition()["input_schema"]["properties"]
        assert "course_name" in props

    def test_schema_has_optional_lesson_number_property(self, tool):
        props = tool.get_tool_definition()["input_schema"]["properties"]
        assert "lesson_number" in props


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

class TestCourseSearchToolExecute:
    def _results_with_content(self):
        return SearchResults(
            documents=["Lesson content about MCP"],
            metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
            distances=[0.1],
        )

    def test_returns_string_when_results_found(self, tool, mock_store):
        mock_store.search.return_value = self._results_with_content()
        mock_store.get_lesson_link.return_value = "http://example.com/1"
        result = tool.execute(query="what is MCP")
        assert isinstance(result, str)

    def test_result_contains_course_title(self, tool, mock_store):
        mock_store.search.return_value = self._results_with_content()
        mock_store.get_lesson_link.return_value = None
        result = tool.execute(query="what is MCP")
        assert "MCP Course" in result

    def test_returns_no_results_message_when_empty(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        result = tool.execute(query="nonexistent topic")
        assert "No relevant content found" in result

    def test_returns_store_error_message(self, tool, mock_store):
        mock_store.search.return_value = SearchResults.empty("No course found matching 'X'")
        result = tool.execute(query="something", course_name="X")
        assert "No course found" in result

    def test_execute_with_string_course_name_calls_store(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        tool.execute(query="MCP overview", course_name="MCP")
        mock_store.search.assert_called_once()
        _, kwargs = mock_store.search.call_args
        assert kwargs["course_name"] == "MCP"

    def test_execute_with_dict_course_name_returns_string(self, tool, mock_store):
        # Defensive: even if a malformed dict slips through, the tool returns a string
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        result = tool.execute(query="what is MCP", course_name={"type": "MCP"})
        assert isinstance(result, str)

    def test_sources_tracked_after_results(self, tool, mock_store):
        mock_store.search.return_value = self._results_with_content()
        mock_store.get_lesson_link.return_value = "http://example.com/1"
        tool.execute(query="what is MCP")
        assert len(tool.last_sources) == 1
        assert "MCP Course" in tool.last_sources[0]["text"]


# ---------------------------------------------------------------------------
# ToolManager
# ---------------------------------------------------------------------------

class TestToolManager:
    def test_get_definitions_returns_list(self, manager):
        assert isinstance(manager.get_tool_definitions(), list)

    def test_registered_tool_appears_in_definitions(self, manager):
        names = [d["name"] for d in manager.get_tool_definitions()]
        assert "search_course_content" in names

    def test_execute_known_tool_returns_string(self, manager, mock_store):
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        result = manager.execute_tool("search_course_content", query="test")
        assert isinstance(result, str)

    def test_execute_unknown_tool_returns_error_string(self, manager):
        result = manager.execute_tool("no_such_tool", query="test")
        assert isinstance(result, str)
        assert "no_such_tool" in result or "not found" in result.lower()

    def test_reset_sources_clears_tool_sources(self, manager, mock_store):
        mock_store.search.return_value = SearchResults(
            documents=["content"],
            metadata=[{"course_title": "Course A", "lesson_number": 1}],
            distances=[0.2],
        )
        mock_store.get_lesson_link.return_value = None
        manager.execute_tool("search_course_content", query="test")
        assert len(manager.get_last_sources()) > 0
        manager.reset_sources()
        assert manager.get_last_sources() == []

    def test_register_tool_without_name_raises(self):
        bad_tool = MagicMock()
        bad_tool.get_tool_definition.return_value = {}  # no 'name' key
        mgr = ToolManager()
        with pytest.raises(ValueError):
            mgr.register_tool(bad_tool)
