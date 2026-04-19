"""Tests for rag_system.py — RAGSystem.query() and VectorStore defensive checks."""
from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config():
    config = MagicMock()
    config.PROVIDER = "ollama"
    config.ANTHROPIC_API_KEY = ""
    config.ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
    config.OLLAMA_MODEL = "llama3.2"
    config.OLLAMA_BASE_URL = "http://localhost:11434/v1"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_RESULTS = 5
    config.MAX_HISTORY = 2
    config.CHROMA_PATH = "./test_chroma"
    return config


# ---------------------------------------------------------------------------
# Fixture: RAGSystem with mocked heavy dependencies
# ---------------------------------------------------------------------------

@pytest.fixture
def rag():
    config = make_config()
    with (
        patch("rag_system.VectorStore"),
        patch("rag_system.DocumentProcessor"),
        patch("rag_system.create_generator") as mock_gen_factory,
    ):
        mock_gen = MagicMock()
        mock_gen.generate_response.return_value = "Test response"
        mock_gen_factory.return_value = mock_gen

        from rag_system import RAGSystem
        system = RAGSystem(config)
        yield system


# ---------------------------------------------------------------------------
# RAGSystem.query
# ---------------------------------------------------------------------------

class TestRAGSystemQuery:
    def test_query_returns_tuple(self, rag):
        result = rag.query("What is RAG?")
        assert isinstance(result, tuple)

    def test_query_first_element_is_string(self, rag):
        response, _ = rag.query("What is RAG?")
        assert isinstance(response, str)

    def test_query_second_element_is_list(self, rag):
        _, sources = rag.query("What is RAG?")
        assert isinstance(sources, list)

    def test_query_without_session_id_works(self, rag):
        response, _ = rag.query("General question", session_id=None)
        assert isinstance(response, str)

    def test_query_passes_tools_to_generator(self, rag):
        rag.query("Tell me about MCP", session_id=None)
        call_kwargs = rag.ai_generator.generate_response.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] is not None

    def test_query_passes_tool_manager_to_generator(self, rag):
        rag.query("Tell me about MCP", session_id=None)
        call_kwargs = rag.ai_generator.generate_response.call_args.kwargs
        assert call_kwargs["tool_manager"] is rag.tool_manager

    def test_query_resets_sources_after_each_call(self, rag):
        with patch.object(rag.tool_manager, "reset_sources") as mock_reset:
            rag.query("First query", session_id=None)
            rag.query("Second query", session_id=None)
        assert mock_reset.call_count == 2

    def test_query_with_session_stores_exchange_in_history(self, rag):
        session_id = rag.session_manager.create_session()
        rag.query("What is RAG?", session_id=session_id)
        history = rag.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "What is RAG?" in history

    def test_query_without_session_does_not_store_history(self, rag):
        rag.query("What is RAG?", session_id=None)
        # No session created, so history store should have no sessions
        # (the session_manager.sessions dict stays empty)
        assert rag.session_manager.sessions == {}

    def test_query_passes_conversation_history_when_session_exists(self, rag):
        session_id = rag.session_manager.create_session()
        # First query to populate history
        rag.query("First question", session_id=session_id)
        # Reset call tracking
        rag.ai_generator.generate_response.reset_mock()
        # Second query should have history
        rag.query("Second question", session_id=session_id)
        call_kwargs = rag.ai_generator.generate_response.call_args.kwargs
        assert call_kwargs["conversation_history"] is not None

    def test_query_no_conversation_history_on_first_call(self, rag):
        session_id = rag.session_manager.create_session()
        rag.query("First question", session_id=session_id)
        call_kwargs = rag.ai_generator.generate_response.call_args.kwargs
        assert call_kwargs["conversation_history"] is None


# ---------------------------------------------------------------------------
# VectorStore._resolve_course_name defensive check
# ---------------------------------------------------------------------------

class TestVectorStoreDefensiveCheck:
    """Tests that VectorStore._resolve_course_name handles non-string input safely."""

    def _make_vector_store(self):
        """Create a VectorStore with mocked ChromaDB client."""
        from vector_store import VectorStore
        with patch("vector_store.chromadb.PersistentClient"), \
             patch("vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"):
            vs = VectorStore.__new__(VectorStore)
            vs.max_results = 5
            vs.course_catalog = MagicMock()
            vs.course_content = MagicMock()
            vs.embedding_function = MagicMock()
        return vs

    def test_resolve_course_name_returns_none_for_dict_input(self):
        vs = self._make_vector_store()
        # Before the fix, this would throw into ChromaDB and print an error.
        # After the fix, it returns None immediately without touching ChromaDB.
        result = vs._resolve_course_name({"type": "MCP"})
        assert result is None

    def test_resolve_course_name_does_not_call_chroma_with_dict(self):
        vs = self._make_vector_store()
        vs._resolve_course_name({"type": "MCP"})
        vs.course_catalog.query.assert_not_called()

    def test_resolve_course_name_works_normally_for_string(self):
        vs = self._make_vector_store()
        vs.course_catalog.query.return_value = {
            "documents": [["MCP: Build Rich-Context AI Apps with Anthropic"]],
            "metadatas": [[{"title": "MCP: Build Rich-Context AI Apps with Anthropic"}]],
        }
        result = vs._resolve_course_name("MCP")
        assert result == "MCP: Build Rich-Context AI Apps with Anthropic"
