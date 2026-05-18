# RAG Document Q&A Codebase and Workflow Guide

This document explains the runnable application in this repository and how each part of the codebase participates in the application workflow.

## 1. What This Application Does

The application lets a user upload a PDF or TXT file, ask a question about that file, and receive an answer with retrieved source snippets.

The current runnable implementation is a full-stack app:

- Frontend: Next.js 14 with React and TypeScript.
- Backend: FastAPI with Python.
- Document parsing: `pypdf` for PDFs and UTF-8 decoding for text files.
- Retrieval: in-memory TF-IDF similarity search with scikit-learn.
- Answer generation: Hugging Face Inference API when `HF_API_TOKEN` is available, otherwise a local fallback summary.
- Runtime storage: process memory only.

Important: the current `rag-document-qa` app does not persist documents to a database. If the backend restarts, uploaded document chunks are lost.

## 2. Repository Layout

```text
RAG-Project/
|-- README.md                         # Top-level aspirational README; describes a fuller OpenAI/Pinecone version.
|-- main.py, routes.py, ...            # Top-level snapshot files from a different/older implementation.
|-- ci.yml, cd.yml                     # GitHub Actions workflow files, currently outside .github/workflows.
|-- docker-compose.yml                 # Top-level compose file.
|-- rag-document-qa/                   # Runnable application folder.
    |-- docker-compose.yml             # Runs backend and frontend together.
    |-- README.md                      # Currently empty.
    |-- CODEBASE_WORKFLOW.md           # This guide.
    |-- backend/
    |   |-- app/
    |   |   |-- main.py                # FastAPI app entry point.
    |   |   |-- api/routes.py          # API routes for ingest and query.
    |   |   |-- core/config.py         # Pydantic settings class.
    |   |   |-- models/schemas.py      # QueryRequest model, mostly unused.
    |   |   |-- services/
    |   |       |-- document_service.py # File text extraction, chunking, in-memory storage.
    |   |       |-- query_service.py    # Retrieval, Hugging Face call, fallback answer.
    |   |-- requirements.txt           # Python dependencies.
    |   |-- Dockerfile                 # Backend container.
    |   |-- tests/test_api.py          # Empty test file.
    |-- frontend/
        |-- src/app/layout.tsx         # Next.js root layout and metadata.
        |-- src/app/page.tsx           # Main page and hero content.
        |-- src/components/
        |   |-- ChatInterface.tsx      # Main upload and question UI.
        |   |-- FileUpload.tsx         # Empty placeholder file.
        |   |-- SourceCard.tsx         # Empty placeholder file.
        |-- src/lib/api.ts             # Browser API client for backend calls.
        |-- src/styles/globals.css     # Global styling.
        |-- package.json               # Frontend scripts and dependencies.
        |-- Dockerfile                 # Frontend container.
```

## 3. High-Level Architecture

```text
Browser
  |
  | User selects a PDF/TXT and asks a question
  v
Next.js frontend
  |
  | POST /api/ingest with multipart file
  | POST /api/query with JSON question
  v
FastAPI backend
  |
  | Extract text from uploaded document
  | Split text into overlapping chunks
  | Store chunks in process memory
  | Retrieve most relevant chunks using TF-IDF
  | Generate answer using Hugging Face or fallback logic
  v
JSON response with answer and source snippets
  |
  v
Frontend renders answer and source cards
```

## 4. Backend Workflow

### 4.1 Application Startup

File: `backend/app/main.py`

This file creates the FastAPI app:

- Sets the API title to `RAG Document Q&A API`.
- Enables CORS for `http://localhost:3000`.
- Includes the router from `app.api.routes`.
- Exposes two base routes:
  - `GET /` returns `{"message": "RAG API is running"}`.
  - `GET /health` returns `{"status": "healthy"}`.

The backend is launched by Docker with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4.2 API Routes

File: `backend/app/api/routes.py`

The router is mounted under `/api`.

Available endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/test` | Simple route check. |
| `POST` | `/api/ingest` | Accepts an uploaded file, extracts text, chunks it, and stores it in memory. |
| `POST` | `/api/query` | Accepts a question, retrieves relevant chunks, and returns an answer. |

`POST /api/ingest` flow:

1. Receives an uploaded file as `UploadFile`.
2. Reads the full file into bytes.
3. Creates a new `DocumentService`.
4. Calls `DocumentService.ingest(file_bytes, file.filename)`.
5. Returns upload metadata including document ID and chunk count.

`POST /api/query` flow:

1. Receives JSON shaped like:

   ```json
   {
     "question": "What is this document about?"
   }
   ```

2. Creates a new `QueryService`.
3. Calls `QueryService.answer_question(request.question)`.
4. Returns:

   ```json
   {
     "answer": "...",
     "sources": [...]
   }
   ```

### 4.3 Document Ingestion Service

File: `backend/app/services/document_service.py`

This service is responsible for reading a file and converting it into searchable text chunks.

Key module-level state:

```python
DOCUMENT_STORE: Dict[str, List[dict]] = {}
```

This global dictionary is the current document store. It is not persisted outside Python memory.

Important methods:

#### `extract_text(file_bytes, filename)`

Behavior:

- If the filename ends with `.pdf`, it uses `PdfReader` from `pypdf`.
- It loops through every page and calls `page.extract_text()`.
- If the file is not a PDF, it decodes the file bytes as UTF-8 text with errors ignored.

Practical implication:

- Text-based PDFs work.
- Scanned image PDFs usually fail because there is no embedded text.
- TXT files work if their content can be decoded reasonably as text.

#### `chunk_text(text, chunk_size=900, overlap=150)`

Behavior:

- Splits text using fixed character windows.
- Each chunk is up to 900 characters.
- Consecutive chunks overlap by 150 characters.

Why overlap exists:

- It reduces the chance that important context is split across two chunks.

#### `ingest(file_bytes, filename)`

Behavior:

1. Extracts text.
2. Rejects empty text.
3. Chunks the text.
4. Creates a UUID document ID.
5. Clears `DOCUMENT_STORE`.
6. Stores the new document chunks under that document ID.
7. Returns upload metadata.

Important detail:

```python
DOCUMENT_STORE.clear()
```

This means only one uploaded document is active at a time. Uploading a second document removes the previous document from memory.

### 4.4 Query Service

File: `backend/app/services/query_service.py`

This service retrieves relevant chunks and generates an answer.

#### `retrieve_context(question, top_k=5)`

Behavior:

1. Reads all chunks from `DOCUMENT_STORE`.
2. If no chunks exist, returns empty context and no sources.
3. Builds a TF-IDF matrix from all chunk texts plus the user question.
4. Computes cosine similarity between the question vector and every chunk vector.
5. Selects the top 5 chunks by similarity.
6. Builds:
   - `context`: concatenated retrieved chunk text.
   - `sources`: source objects with document name, truncated text, and similarity score.

This is retrieval, but it is not vector database retrieval. It recalculates TF-IDF vectors at query time from in-memory chunks.

#### `generate_with_huggingface(question, context)`

Behavior:

1. Reads `HF_API_TOKEN` from environment variables.
2. If no token exists, returns `None`.
3. Sends the prompt to Hugging Face model `google/flan-t5-base`.
4. Returns generated text when Hugging Face responds successfully.
5. Returns `None` if the request fails or returns a non-200 response.

This method uses the external Hugging Face Inference API, so it needs network access and a valid token.

#### `fallback_answer(question, context)`

Behavior:

- Splits retrieved context into sentences.
- Selects up to seven readable sentences longer than 50 characters.
- Formats them as bullet points.

This is used when Hugging Face is unavailable, missing a token, or returns an error.

#### `answer_question(question)`

Complete flow:

1. Calls `retrieve_context`.
2. If there is no uploaded document, returns:

   ```text
   Please upload a PDF or TXT file first.
   ```

3. Attempts Hugging Face generation.
4. If Hugging Face returns an answer, uses it.
5. Otherwise, uses the fallback answer.
6. Returns answer and sources.

### 4.5 Backend Configuration

File: `backend/app/core/config.py`

This defines a `Settings` class with fields for:

- `hf_api_token`
- `pinecone_api_key`
- `pinecone_index_name`
- `pinecone_cloud`
- `pinecone_region`
- `cors_origins`

Current caveat:

- The active services do not import `settings`.
- `QueryService` reads `HF_API_TOKEN` directly with `os.getenv`.
- Pinecone settings exist but are not used by the current runnable implementation.

### 4.6 Backend Dependencies

File: `backend/requirements.txt`

Main dependencies:

- `fastapi`, `uvicorn`: API server.
- `python-multipart`: file upload support.
- `pypdf`: PDF text extraction.
- `httpx`, `requests`: HTTP clients.
- `pytest`: test runner.
- `ruff`, `black`: linting and formatting.
- `openai`, `pinecone`, `pydantic-settings`: installed but not actively used by the current in-folder services.

Note: `query_service.py` uses `sklearn`, but `scikit-learn` is not listed in `backend/requirements.txt`. The local environment may already have it installed, but a clean Docker build may fail unless `scikit-learn` is added.

## 5. Frontend Workflow

### 5.1 Next.js Entry Point

File: `frontend/src/app/layout.tsx`

This file:

- Imports global CSS.
- Sets metadata title and description.
- Renders the page body.

### 5.2 Home Page

File: `frontend/src/app/page.tsx`

This file renders:

- The marketing/hero section.
- The `ChatInterface` component.

It does not manage state itself. All upload and question behavior lives inside `ChatInterface`.

### 5.3 Main UI Component

File: `frontend/src/components/ChatInterface.tsx`

This is the core frontend component.

State variables:

| State | Purpose |
|---|---|
| `file` | Currently selected PDF/TXT file. |
| `uploaded` | Whether the selected file has already been sent to the backend. |
| `question` | User's typed question. |
| `answer` | Answer returned by backend or validation/error text. |
| `sources` | Retrieved source chunks returned by backend. |
| `loading` | Button/loading state while API calls are running. |

Main user flow:

1. User selects a file.
2. Component stores the file in state and resets previous answers/sources.
3. User types a question.
4. User clicks `Ask AI`.
5. `handleAsk()` validates that a file and question exist.
6. If the file has not been uploaded yet, it calls `uploadDocument(file)`.
7. It then calls `askQuestion(question)`.
8. It renders the answer.
9. It renders retrieved source snippets with similarity scores.

Important behavior:

- Upload happens lazily when the user asks the first question.
- Selecting a new file sets `uploaded` back to `false`.
- Asking multiple questions about the same selected file skips re-upload after the first successful upload.

### 5.4 API Client

File: `frontend/src/lib/api.ts`

This file centralizes browser-to-backend calls.

Backend URL:

```ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

Functions:

#### `uploadDocument(file)`

- Creates `FormData`.
- Appends the file under field name `file`.
- Sends `POST ${API_URL}/api/ingest`.
- Throws an error if the response is not successful.

#### `askQuestion(question)`

- Sends `POST ${API_URL}/api/query`.
- Uses JSON body `{ question }`.
- Throws an error if the response is not successful.

### 5.5 Styling

File: `frontend/src/styles/globals.css`

This file controls all visual styling:

- Page background.
- Hero section.
- Upload panel.
- File button.
- Question textarea.
- Answer and source blocks.
- Mobile layout adjustments.

There are no CSS modules or Tailwind utility classes in the current components, even though `tailwind.config.js` exists as a placeholder.

### 5.6 Placeholder Components

Files:

- `frontend/src/components/FileUpload.tsx`
- `frontend/src/components/SourceCard.tsx`

Both files are currently empty. Their responsibilities are implemented directly inside `ChatInterface.tsx`.

## 6. End-to-End Request Flow

### 6.1 First Question After Selecting a File

```text
User selects file
  |
  v
ChatInterface stores File object
  |
  v
User types question and clicks Ask AI
  |
  v
handleAsk validates file and question
  |
  v
uploadDocument(file)
  |
  v
POST http://localhost:8000/api/ingest
  |
  v
FastAPI route reads file bytes
  |
  v
DocumentService.extract_text
  |
  v
DocumentService.chunk_text
  |
  v
DOCUMENT_STORE is cleared and replaced with new chunks
  |
  v
Frontend marks uploaded=true
  |
  v
askQuestion(question)
  |
  v
POST http://localhost:8000/api/query
  |
  v
QueryService.retrieve_context
  |
  v
TF-IDF similarity ranks chunks
  |
  v
QueryService.generate_with_huggingface
  |
  | if HF works
  v
Hugging Face answer
  |
  | otherwise
  v
Fallback bullet summary
  |
  v
Frontend renders answer and sources
```

### 6.2 Later Questions About the Same File

```text
User changes only the question
  |
  v
handleAsk sees uploaded=true
  |
  v
Skips /api/ingest
  |
  v
Calls /api/query directly
```

### 6.3 Selecting a Different File

```text
User selects a new file
  |
  v
ChatInterface sets uploaded=false
  |
  v
Next Ask AI click uploads the new file
  |
  v
Backend clears old DOCUMENT_STORE and stores new chunks
```

## 7. Running the Application

### Option A: Docker Compose

From `rag-document-qa/`:

```bash
docker-compose up --build
```

Expected services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Backend health: `http://localhost:8000/health`
- FastAPI docs: `http://localhost:8000/docs`

Docker Compose passes this frontend environment variable:

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Option B: Manual Backend

From `rag-document-qa/backend/`:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

For Hugging Face generation:

```bash
set HF_API_TOKEN=your_token_here
```

PowerShell:

```powershell
$env:HF_API_TOKEN="your_token_here"
```

If no token is provided, the fallback answer still works.

### Option C: Manual Frontend

From `rag-document-qa/frontend/`:

```bash
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## 8. API Reference

### `GET /`

Returns:

```json
{
  "message": "RAG API is running"
}
```

### `GET /health`

Returns:

```json
{
  "status": "healthy"
}
```

### `GET /api/test`

Returns:

```json
{
  "message": "API route working"
}
```

### `POST /api/ingest`

Request:

- Content type: `multipart/form-data`
- Field: `file`
- Supported by current extraction logic: `.pdf`, `.txt`, and any non-PDF text-like file that can decode as UTF-8.

Example:

```bash
curl -X POST http://localhost:8000/api/ingest -F "file=@sample.pdf"
```

Response:

```json
{
  "message": "Document uploaded successfully",
  "document_id": "uuid",
  "filename": "sample.pdf",
  "chunks": 12
}
```

### `POST /api/query`

Request:

```json
{
  "question": "What are the key points?"
}
```

Example:

```bash
curl -X POST http://localhost:8000/api/query ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"What are the key points?\"}"
```

Response:

```json
{
  "answer": "Here are the key points from the uploaded document:\n\n- ...",
  "sources": [
    {
      "document_name": "sample.pdf",
      "text": "Source chunk preview...",
      "score": 0.42
    }
  ]
}
```

## 9. Current Limitations and Gaps

These are important for understanding the codebase accurately:

- The in-folder `README.md` is empty.
- `backend/tests/test_api.py` is empty, so there is no active test coverage.
- `backend/app/models/schemas.py` defines `QueryRequest`, but `routes.py` defines a separate `QueryRequest` instead of importing it.
- `backend/app/core/config.py` defines Pinecone-related settings, but the active services do not use Pinecone.
- `openai` and `pinecone` are installed in `requirements.txt`, but the active `rag-document-qa/backend/app/services` implementation uses Hugging Face plus TF-IDF.
- `query_service.py` imports scikit-learn, but `scikit-learn` is missing from `backend/requirements.txt`.
- Documents are stored only in process memory.
- Uploading a new document removes the previous document.
- PDF support depends on extractable text; scanned PDFs need OCR, which is not implemented.
- `FileUpload.tsx` and `SourceCard.tsx` are empty placeholders.
- `tailwind.config.js`, `next.config.js`, `pyproject.toml`, `.env.example`, `.env.local.example`, and `pytest.ini` are empty placeholders.
- Top-level root files describe a more advanced OpenAI/Pinecone architecture, but they are not the same as the runnable in-folder app.

## 10. Difference Between Current App and Top-Level Blueprint

The top-level `README.md`, `document_service.py`, `query_service.py`, and `routes.py` describe or implement a more production-style RAG system:

- LangChain loaders.
- OpenAI embeddings.
- Pinecone vector database.
- OpenAI chat completions.
- Server-sent streaming route `/api/stream`.
- Richer Pydantic response models.

The runnable `rag-document-qa/backend/app` code is simpler:

- No LangChain.
- No OpenAI.
- No Pinecone upsert/query.
- No streaming endpoint.
- Uses `DOCUMENT_STORE` memory.
- Uses TF-IDF retrieval.
- Optionally uses Hugging Face `google/flan-t5-base`.

When learning or debugging the current app, use the files under `rag-document-qa/` as the source of truth.

## 11. Mental Model for Development

Use this checklist when changing the application:

1. If you change how files are uploaded, update both `ChatInterface.tsx` and `/api/ingest`.
2. If you change request or response shapes, update `frontend/src/lib/api.ts`, `ChatInterface.tsx`, and backend route models together.
3. If you change retrieval, start in `backend/app/services/query_service.py`.
4. If you change parsing or chunking, start in `backend/app/services/document_service.py`.
5. If you add persistence or vector database support, replace or wrap `DOCUMENT_STORE`.
6. If you add multi-document support, remove `DOCUMENT_STORE.clear()` and introduce a document selection or namespace strategy.
7. If you add real tests, cover `/health`, `/api/ingest`, `/api/query`, empty document handling, and no-document query behavior.

## 12. Suggested Next Improvements

Highest-impact improvements:

1. Add `scikit-learn` to `backend/requirements.txt`.
2. Move the useful top-level README content into `rag-document-qa/README.md`, but correct it to match the actual implementation.
3. Add real backend tests in `backend/tests/test_api.py`.
4. Remove duplicate `QueryRequest` definitions and use models from `backend/app/models/schemas.py`.
5. Extract upload and source rendering into `FileUpload.tsx` and `SourceCard.tsx`.
6. Decide whether the project should stay simple with TF-IDF or become the Pinecone/OpenAI implementation described by the top-level files.
7. Add persistent storage if uploaded documents must survive backend restarts.

