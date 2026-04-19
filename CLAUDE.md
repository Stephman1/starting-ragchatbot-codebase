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

## Ollama (local models — cost-free alternative)

Ollama models can be used instead of the Anthropic API for cost-sensitive users. No API key required.

**Setup:**
```bash
# Install Ollama (mac)
brew install ollama

# Pull a model with good tool-calling support
ollama pull llama3.1:8b   # recommended minimum
# or
ollama pull qwen2.5:7b
ollama pull mistral:7b
ollama pull gemma4:27b    # best quality, requires ~16 GB RAM
```

**`.env` configuration:**
```
PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b          # must support function/tool calling
OLLAMA_BASE_URL=http://localhost:11434/v1   # default, change if Ollama runs elsewhere
```

Ollama serves at `http://localhost:11434` by default. The `OLLAMA_BASE_URL` should point to the `/v1` path (OpenAI-compatible endpoint).

**Model requirements:** The model must support OpenAI-compatible function/tool calling. `llama3.2` (1B/3B) does support tool calling, but small models are less reliable in practice — they are more likely to hallucinate arguments or ignore the tool schema due to their limited capacity, not missing capability. `llama3.1:8b` or larger will follow tool schemas more consistently. Note: `llama3.2-vision` variants do **not** support tools in Ollama. Check `ollama ps` to confirm a model is loaded.

**Debug mode:**
```
DEBUG_RAG=true
```
Enables per-request pipeline tracing in the server logs: finish_reason, tool call args (before/after sanitization), tool results, and warnings when a model is not using the tool-calling API properly.

## Architecture

This is a RAG chatbot that answers questions about course materials stored as `.txt` files in `docs/`.

**Request flow:**
1. Browser (`frontend/`) POSTs `{ query, session_id }` to `POST /api/query`
2. `backend/app.py` (FastAPI) delegates to `RAGSystem.query()`
3. `RAGSystem` calls the AI provider (`AIGenerator` for Anthropic, `OllamaGenerator` for local Ollama) with the `search_course_content` tool available
4. The model either answers directly or calls the tool → `ToolManager` → `VectorStore.search()` → ChromaDB
5. If the tool was used, a second model call synthesizes the retrieved chunks into a final answer
6. Response + sources returned to the browser

**Key backend modules:**
- `rag_system.py` — main orchestrator, wires all components
- `ai_generator.py` — Anthropic client + `create_generator(config)` factory; handles the two-turn tool-use loop
- `ollama_generator.py` — Ollama client (OpenAI-compatible); same interface as `AIGenerator`; includes arg sanitization for small models that wrap values as `{"type": "x"}`
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
