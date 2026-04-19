import sys
import os
import pytest
from unittest.mock import MagicMock

# Add backend/ to sys.path so tests can import backend modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mock_rag_system():
    """Fully mocked RAGSystem for API and integration tests."""
    rag = MagicMock()
    rag.query.return_value = ("Test answer about the course.", [])
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python Basics", "Advanced RAG"],
    }
    rag.session_manager.create_session.return_value = "test-session-123"
    rag.session_manager.get_conversation_history.return_value = None
    return rag


@pytest.fixture
def sample_sources():
    return [
        {"text": "Python Basics — Lesson 1", "link": "http://example.com/lesson/1"},
        {"text": "Python Basics — Lesson 2", "link": "http://example.com/lesson/2"},
    ]


@pytest.fixture
def sample_query_response(sample_sources):
    return {
        "answer": "Python is a high-level programming language.",
        "sources": sample_sources,
        "session_id": "test-session-123",
    }
