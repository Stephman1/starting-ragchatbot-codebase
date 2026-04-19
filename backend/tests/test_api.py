"""Tests for FastAPI API endpoints — /api/query and /api/courses.

Uses an inline test app that mirrors the real app's routes without the static
file mount or ChromaDB initialisation, both of which require a real filesystem.
"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Inline models (mirror app.py so we can swap the real app cleanly)
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[Any]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def build_test_app(rag):
    """Return a FastAPI app wired to *rag* (a real or mock RAGSystem)."""
    app = FastAPI()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or rag.session_manager.create_session()
            answer, sources = rag.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(mock_rag_system):
    return TestClient(build_test_app(mock_rag_system))


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    def test_returns_200_for_valid_query(self, client):
        resp = client.post("/api/query", json={"query": "What is RAG?"})
        assert resp.status_code == 200

    def test_response_has_answer_field(self, client):
        assert "answer" in client.post("/api/query", json={"query": "What is RAG?"}).json()

    def test_response_has_sources_field(self, client):
        assert "sources" in client.post("/api/query", json={"query": "What is RAG?"}).json()

    def test_response_has_session_id_field(self, client):
        assert "session_id" in client.post("/api/query", json={"query": "What is RAG?"}).json()

    def test_answer_is_string(self, client):
        assert isinstance(client.post("/api/query", json={"query": "Q"}).json()["answer"], str)

    def test_sources_is_list(self, client):
        assert isinstance(client.post("/api/query", json={"query": "Q"}).json()["sources"], list)

    def test_explicit_session_id_is_echoed_back(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer", [])
        resp = client.post("/api/query", json={"query": "Q", "session_id": "my-session"})
        assert resp.json()["session_id"] == "my-session"

    def test_session_id_auto_generated_when_omitted(self, client, mock_rag_system):
        mock_rag_system.session_manager.create_session.return_value = "generated-id"
        mock_rag_system.query.return_value = ("Answer", [])
        resp = client.post("/api/query", json={"query": "Q"})
        assert resp.json()["session_id"] == "generated-id"

    def test_returns_422_when_query_field_missing(self, client):
        assert client.post("/api/query", json={}).status_code == 422

    def test_returns_500_when_rag_raises(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB failure")
        resp = client.post("/api/query", json={"query": "Q", "session_id": "s"})
        assert resp.status_code == 500

    def test_500_detail_contains_exception_message(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB failure")
        resp = client.post("/api/query", json={"query": "Q", "session_id": "s"})
        assert "DB failure" in resp.json()["detail"]

    def test_sources_reflect_rag_output(self, client, mock_rag_system, sample_sources):
        mock_rag_system.query.return_value = ("Answer", sample_sources)
        resp = client.post("/api/query", json={"query": "Q", "session_id": "s"})
        assert resp.json()["sources"] == sample_sources

    def test_rag_query_called_with_correct_query_text(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer", [])
        client.post("/api/query", json={"query": "Tell me about MCP", "session_id": "s"})
        call_args = mock_rag_system.query.call_args
        assert call_args[0][0] == "Tell me about MCP"


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:
    def test_returns_200(self, client):
        assert client.get("/api/courses").status_code == 200

    def test_response_has_total_courses(self, client):
        assert "total_courses" in client.get("/api/courses").json()

    def test_response_has_course_titles(self, client):
        assert "course_titles" in client.get("/api/courses").json()

    def test_total_courses_is_integer(self, client):
        assert isinstance(client.get("/api/courses").json()["total_courses"], int)

    def test_course_titles_is_list(self, client):
        assert isinstance(client.get("/api/courses").json()["course_titles"], list)

    def test_total_courses_matches_analytics(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["A", "B", "C"],
        }
        assert client.get("/api/courses").json()["total_courses"] == 3

    def test_course_titles_match_analytics(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Python Basics", "Advanced RAG"],
        }
        assert "Python Basics" in client.get("/api/courses").json()["course_titles"]

    def test_title_count_matches_total_courses(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["A", "B"],
        }
        data = client.get("/api/courses").json()
        assert len(data["course_titles"]) == data["total_courses"]

    def test_returns_500_when_analytics_raises(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("Analytics error")
        assert client.get("/api/courses").status_code == 500

    def test_500_detail_contains_exception_message(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("Analytics error")
        assert "Analytics error" in client.get("/api/courses").json()["detail"]
