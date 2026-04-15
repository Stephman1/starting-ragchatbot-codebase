# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run any Python file
uv run python <file.py>

# Run the server (from repo root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

Requires `ANTHROPIC_API_KEY` in a `.env` file at the repo root (see `.env.example`).

## Architecture

This is a RAG chatbot that answers questions about course materials stored as `.txt` files in `docs/`.

**Request flow:**
1. Browser (`frontend/`) POSTs `{ query, session_id }` to `POST /api/query`
2. `backend/app.py` (FastAPI) delegates to `RAGSystem.query()`
3. `RAGSystem` calls Claude via `AIGenerator` with the `search_course_content` tool available
4. Claude either answers directly or calls the tool → `ToolManager` → `VectorStore.search()` → ChromaDB
5. If the tool was used, a second Claude call synthesizes the retrieved chunks into a final answer
6. Response + sources returned to the browser

**Key backend modules:**
- `rag_system.py` — main orchestrator, wires all components
- `ai_generator.py` — Anthropic client; handles the two-turn tool-use loop (first call may trigger tool use, second call synthesizes results)
- `vector_store.py` — ChromaDB wrapper with two collections: `course_catalog` (one doc per course, used for semantic course-name resolution) and `course_content` (chunked text, used for similarity search)
- `search_tools.py` — defines the `search_course_content` Anthropic tool and `ToolManager`
- `document_processor.py` — parses `.txt` course files into `Course`/`Lesson`/`CourseChunk` objects with sentence-based chunking
- `session_manager.py` — in-memory conversation history keyed by session ID (last 2 exchanges)
- `config.py` — single `Config` dataclass; model, chunk size, ChromaDB path, etc.

**On startup**, `app.py` ingests all `.txt` files from `docs/` into ChromaDB. Re-ingestion is skipped if a course title already exists in the vector store.

**Course document format** expected by `document_processor.py`:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <title>
Lesson Link: <url>
<lesson content...>

Lesson 2: <title>
...
```

**ChromaDB** is persisted locally at `./chroma_db` (relative to `backend/`). Delete this directory to force a full re-ingest.
