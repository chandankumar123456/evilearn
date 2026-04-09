# Backend — API & Orchestration Layer

> The backend is a **control system**, not a reasoning entity. It routes requests, validates input, triggers the AI pipeline, and stores results. All intelligence lives in the AI Engine; all data operations live in the Data Layer.

## Overview

The EviLearn backend is a FastAPI application that serves as the orchestration layer between the React frontend and the AI reasoning engine. It handles document upload processing, validation pipeline execution, session management, feedback collection, and history retrieval.

## Technology

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Framework | FastAPI | REST API with automatic OpenAPI docs |
| ASGI Server | Uvicorn | Production-ready async server |
| Validation | Pydantic v2 | Strict request/response/pipeline schema enforcement |
| File Upload | `python-multipart` | Multipart form data parsing |
| Embeddings | EmbeddingService | Embedding generation via LLM API (OpenAI/Groq) |
| LLM Client | Groq / OpenAI SDK | Optional LLM for claim extraction & explanation |

## Architecture

```mermaid
graph TB
    subgraph "Backend Application (app.py)"
        MW[CORS Middleware]
        EP[API Endpoints]
        INIT[Service Initialization]
    end

    subgraph "Services"
        DB[Database<br/>SQLite]
        DP[DocumentProcessor<br/>PyMuPDF]
        CH[TextChunker]
        ES[EmbeddingService<br/>LLM API]
        VS[VectorStore<br/>ChromaDB — storage only]
        PIP[ValidationPipeline<br/>LangGraph]
        LLM[LLM Client<br/>Groq / OpenAI]
    end

    FE[Frontend<br/>React] <-->|REST API| MW
    MW --> EP
    INIT --> DB & DP & CH & ES & VS & PIP & LLM
    EP --> DB
    EP --> DP
    EP --> CH
    EP --> ES
    EP --> VS
    EP --> PIP
    PIP --> LLM
    PIP --> ES
```

## API Endpoints

### Health Check

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Returns service status |

**Response:**
```json
{"status": "ok", "service": "EviLearn API", "version": "1.0.0"}
```

---

### Document Upload

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload-documents` | Upload and process a PDF or text file |

**Request:** `multipart/form-data` with `file` field

**Response Schema — `DocumentResponse`:**
```json
{
  "document_id": "uuid",
  "file_name": "document.pdf",
  "status": "ready",
  "page_count": 15,
  "message": "Document processed successfully. 42 chunks created."
}
```

**Validation:**
- File extension must be `.pdf` or `.txt`
- File must not be empty
- File size must not exceed `MAX_FILE_SIZE_MB` (default: 50 MB)

**Processing pipeline:**
1. Validate file type and size
2. Generate document ID (UUID)
3. Insert document record in SQLite (status: `processing`)
4. Extract text via `DocumentProcessor`
5. Chunk text via `TextChunker` (500 chars, 50 overlap)
6. Generate embeddings via `EmbeddingService` (LLM API)
7. Store chunks + pre-computed embeddings in ChromaDB
8. Store chunks in SQLite
9. Update document status to `ready`

**Error responses:**
| Code | Condition |
|------|-----------|
| 400 | Unsupported file type |
| 400 | Empty file |
| 400 | File exceeds size limit |
| 400 | PDF corrupted or no extractable text |
| 500 | Unexpected processing failure |

---

### List Documents

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/documents` | List all uploaded documents |

**Response:**
```json
{
  "documents": [
    {
      "document_id": "uuid",
      "file_name": "doc.pdf",
      "upload_time": "2024-01-15T10:30:00",
      "status": "ready",
      "page_count": 10
    }
  ]
}
```

---

### Process Input (Validate)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/process-input` | Submit text for validation through the AI pipeline |

**Request Schema — `ProcessInputRequest`:**
```json
{
  "input_text": "Photosynthesis converts CO2 into glucose using sunlight."
}
```

**Response Schema — `ProcessInputResponse`:**
```json
{
  "session_id": "uuid",
  "input_type": "answer",
  "claims": [
    {
      "claim_id": "uuid",
      "claim_text": "Photosynthesis converts CO2 into glucose.",
      "status": "supported",
      "confidence_score": 0.87,
      "evidence": [
        {"snippet": "...", "page_number": 12}
      ],
      "explanation": "This claim is supported by evidence..."
    }
  ],
  "message": ""
}
```

**Error responses:**
| Code | Condition |
|------|-----------|
| 400 | No documents uploaded (knowledge base empty) |
| 400 | Invalid/empty input text |
| 500 | Pipeline stage failure |

---

### Get Results

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/get-results/{session_id}` | Retrieve results for a specific session |

**Response:**
```json
{
  "session_id": "uuid",
  "input_text": "original text",
  "input_type": "answer",
  "claims": [...]
}
```

**Error responses:**
| Code | Condition |
|------|-----------|
| 404 | Session not found |

---

### Submit Feedback

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/submit-feedback` | Submit accept/reject feedback for a claim |

**Request Schema — `FeedbackRequest`:**
```json
{
  "claim_id": "uuid",
  "session_id": "uuid",
  "decision": "accept"
}
```

`decision` must match the pattern `^(accept|reject)$`.

**Response Schema — `FeedbackResponse`:**
```json
{
  "feedback_id": "uuid",
  "message": "Feedback 'accept' recorded for claim <claim_id>."
}
```

**Error responses:**
| Code | Condition |
|------|-----------|
| 404 | Session not found |
| 422 | Invalid decision value (not `accept` or `reject`) |

---

### Edit Claim

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/edit-claim` | Edit a claim and re-run the validation pipeline |

**Request Schema — `EditClaimRequest`:**
```json
{
  "claim_id": "uuid",
  "session_id": "uuid",
  "new_claim_text": "Updated claim text to validate"
}
```

**Response:** Same as `ProcessInputResponse`.

**Behavior:** Re-runs the full validation pipeline on `new_claim_text`, stores new claims and results under the same session.

**Error responses:**
| Code | Condition |
|------|-----------|
| 404 | Session not found |
| 500 | Pipeline execution failure |

---

### History

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/history` | Retrieve complete validation history |

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "uuid",
      "input_text": "...",
      "input_type": "answer",
      "created_at": "2024-01-15T10:30:00",
      "claims": [...],
      "results": [...],
      "feedback": [...]
    }
  ]
}
```

---

### Evaluate Reasoning (Stress Test)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/evaluate-reasoning` | Stress-test reasoning robustness for a student answer |

**Request Schema — `EvaluateReasoningRequest`:**
```json
{
  "problem": "Solve for x: 2x + 4 = 10",
  "student_answer": "x = 3 because we divide both sides by 2",
  "confidence": 80
}
```

| Field | Type | Validation |
|-------|------|------------|
| `problem` | `string` | Optional — the problem being solved |
| `student_answer` | `string` | Required, `min_length=1` — the student's reasoning/answer |
| `confidence` | `integer` | Required, `0–100` — student's self-reported confidence |

**Response Schema — `EvaluateReasoningResponse`:**
```json
{
  "stress_test_results": [
    "FAILS when: x = 0 (at: division step) — Division by zero"
  ],
  "weakness_summary": [
    {
      "type": "overgeneralization",
      "detail": "Assumes all values are positive without justification"
    }
  ],
  "robustness_summary": {
    "robustness_score": 0.4,
    "summary": "Reasoning fails under multiple edge cases",
    "level": "low"
  },
  "adversarial_questions": [
    "What happens when x = 0?"
  ]
}
```

**Error responses:**
| Code | Condition |
|------|-----------|
| 400 | Empty or missing student answer |
| 500 | Stress test engine failure |

### Simulate Thinking (Graph-Based Cognitive Reasoning)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/simulate-thinking` | Simulate multi-level cognitive reasoning as structured graphs |

**Request Body (`ThinkingSimulationRequest`):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `problem` | `string` | Yes | Problem or question to simulate reasoning for |
| `student_answer` | `string` | No | Student answer/reasoning to compare against |

**Response (`ThinkingSimulationResponse`):**

| Field | Type | Description |
|-------|------|-------------|
| `cognitive_profiles` | `CognitiveProfile[]` | 3 profiles with constraint rules (allowed/forbidden ops, max abstraction) |
| `reasoning_graphs` | `ReasoningGraph[]` | 3 structured reasoning graphs (nodes + edges + decisions + abstraction metrics) |
| `strategy_distributions` | `StrategyDistribution[]` | Strategy % distributions per level (direct, rule_based, transformation, etc.) |
| `structural_comparison` | `StructuralComparison` | Comparison by graph shape, strategy distribution, abstraction flow |
| `gap_analysis` | `GapItem[]` | Structural gap insights (each with severity + source) |
| `student_graph` | `StudentGraph` | Student reasoning converted to graph structure (if student_answer provided) |
| `validation_passed` | `bool` | Whether all cognitive constraints were satisfied |
| `validation_notes` | `string[]` | Details of any constraint fixes applied |

**Key Schemas:**

| Schema | Description |
|--------|-------------|
| `ReasoningNode` | step_id, operation_type, concept_used, input/output, reasoning, abstraction_level, strategy_type |
| `ReasoningEdge` | from_step_id → to_step_id, relation_type (derives/transforms/simplifies) |
| `DecisionPoint` | decision_point, alternatives_considered, chosen_path_reason |
| `AbstractionMetrics` | average_abstraction, max_abstraction, transitions, flow |

**Error Codes:**

| Status | Cause |
|--------|-------|
| 400 | Empty problem text |
| 500 | Thinking simulation engine failure |

### Optimize Cognitive Load

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/optimize-cognitive-load` | Optimize explanation cognitive load for a user |

**Request Schema — `CognitiveLoadRequest`:**
```json
{
  "explanation": "First, we identify the problem. Then, we recall the power rule...",
  "user_id": "default"
}
```

| Field | Type | Validation |
|-------|------|------------|
| `explanation` | `string` | Required, `min_length=1` — raw explanation text to optimize |
| `user_id` | `string` | Optional, default `"default"` — user identifier for state tracking |

**Response Schema — `CognitiveLoadResponse`:**
```json
{
  "adapted_explanation": [
    {
      "step_id": "s1",
      "content": "First, identify the problem type...",
      "concepts": ["problem recognition"],
      "abstraction_level": "concrete",
      "depends_on": []
    }
  ],
  "load_state": "optimal",
  "control_actions": [
    {
      "action": "maintain",
      "reason": "Load matches capacity — maintaining current structure"
    }
  ],
  "user_state": {
    "user_id": "default",
    "understanding_level": 0.5,
    "reasoning_stability": 0.52,
    "learning_speed": 0.52,
    "overload_signals": 0,
    "interaction_count": 1
  },
  "load_metrics": {
    "step_density": 3.33,
    "concept_gap": 1.0,
    "memory_demand": 2.0,
    "total_load": 5.16
  },
  "reasoning_mode": "medium"
}
```

**Key Schemas:**

| Schema | Description |
|--------|-------------|
| `ExplanationStep` | step_id, content, concepts, abstraction_level (concrete/semi-abstract/abstract), depends_on |
| `UserCognitiveState` | user_id, understanding_level, reasoning_stability, learning_speed, overload_signals, interaction_count |
| `CognitiveLoadMetrics` | step_density, concept_gap, memory_demand, total_load |
| `ControlAction` | action, reason |

**Error Codes:**

| Status | Cause |
|--------|-------|
| 400 | Empty explanation text |
| 500 | Cognitive load optimizer failure |

---

## Pipeline Orchestration

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI (app.py)
    participant Pipeline as ValidationPipeline
    participant Graph as LangGraph StateGraph
    participant DB as SQLite

    Client->>FastAPI: POST /process-input
    FastAPI->>FastAPI: Validate request (Pydantic)
    FastAPI->>DB: Check ready documents exist
    FastAPI->>Pipeline: pipeline.execute(input_text)
    Pipeline->>Graph: graph.invoke(initial_state)
    Note over Graph: 5-stage sequential execution<br/>All data validated via Pydantic
    Note over Graph: + conditional stress_test_node
    Graph-->>Pipeline: final_state
    Pipeline->>Pipeline: Validate output via FinalClaimResult
    Pipeline-->>FastAPI: {input_type, claims[]}
    FastAPI->>FastAPI: Validate via ClaimResult BEFORE storage
    FastAPI->>DB: create_session()
    FastAPI->>DB: insert_claims() (validated only)
    FastAPI->>DB: insert_results() (validated only)
    FastAPI-->>Client: ProcessInputResponse
```

### Stress Test Orchestration

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI (app.py)
    participant Pipeline as ValidationPipeline

    Client->>FastAPI: POST /evaluate-reasoning
    FastAPI->>FastAPI: Validate request (EvaluateReasoningRequest)
    FastAPI->>Pipeline: pipeline.evaluate_reasoning(problem, student_answer, confidence)
    Pipeline->>Pipeline: Run stress_test_node (conditional)
    Note over Pipeline: Concept extraction → Assumption extraction<br/>→ Constraint extraction → Weakness analysis<br/>→ Edge case generation → Adversarial scenarios<br/>→ Failure analysis → Robustness scoring<br/>→ Adversarial question generation
    Pipeline-->>FastAPI: stress_test_output
    FastAPI->>FastAPI: Validate via EvaluateReasoningResponse
    FastAPI-->>Client: EvaluateReasoningResponse
```

### Thinking Simulation Orchestration

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI (app.py)
    participant TSE as ThinkingSimulationEngine

    Client->>FastAPI: POST /simulate-thinking
    FastAPI->>FastAPI: Validate request (ThinkingSimulationRequest)
    FastAPI->>TSE: thinking_engine.simulate(problem, student_answer)
    TSE->>TSE: graph.invoke(initial_state)
    Note over TSE: Node 1: Generate cognitive profiles with constraints
    Note over TSE: Node 2: Generate 3 structurally divergent graphs
    Note over TSE: Node 3: Validate constraints, fix violations
    Note over TSE: Node 4: Compute strategy distributions
    Note over TSE: Node 5: Compute abstraction metrics
    Note over TSE: Node 6: Structural comparison (shape, strategy, abstraction)
    Note over TSE: Node 7 (conditional): Convert student answer to graph
    Note over TSE: Node 8: Generate structural gap insights
    TSE-->>FastAPI: thinking simulation results
    FastAPI->>FastAPI: Validate via ThinkingSimulationResponse schemas
    FastAPI-->>Client: ThinkingSimulationResponse
```

### Cognitive Load Optimization Orchestration

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI (app.py)
    participant CLO as CognitiveLoadOptimizer

    Client->>FastAPI: POST /optimize-cognitive-load
    FastAPI->>FastAPI: Validate request (CognitiveLoadRequest)
    FastAPI->>CLO: optimizer.optimize(explanation, user_id)
    CLO->>CLO: graph.invoke(initial_state)
    Note over CLO: Node 1: Analyze explanation into steps, concepts, abstraction
    Note over CLO: Node 2: Load/initialize user cognitive state
    Note over CLO: Node 3: Compute cognitive load (step density, concept gap, memory)
    Note over CLO: Node 4: Compare load vs capacity → overload/optimal/underload
    Note over CLO: Node 5: Adjust granularity (split/merge/checkpoint)
    Note over CLO: Node 6: Validate and clean restructured steps
    Note over CLO: Node 7: Update user state, decide loop/end
    alt Load not optimal & iterations remaining
        Note over CLO: Loop back to Node 3 (re-estimate load)
    end
    CLO-->>FastAPI: adapted explanation + load state + user state
    FastAPI->>FastAPI: Validate via CognitiveLoadResponse schemas
    FastAPI-->>Client: CognitiveLoadResponse
```

## Request & Output Validation (Pydantic Schemas)

All request bodies are validated by Pydantic v2 models defined in `schemas.py`:

| Schema | Fields | Validation |
|--------|--------|------------|
| `ProcessInputRequest` | `input_text` | `min_length=1` |
| `FeedbackRequest` | `claim_id`, `session_id`, `decision` | `decision` matches `^(accept\|reject)$` |
| `EditClaimRequest` | `claim_id`, `session_id`, `new_claim_text` | `new_claim_text` has `min_length=1` |
| `EvaluateReasoningRequest` | `problem`, `student_answer`, `confidence` | `student_answer` has `min_length=1`, `confidence` ∈ [0, 100] |
| `ThinkingSimulationRequest` | `problem`, `student_answer` | `problem` has `min_length=1` |
| `CognitiveLoadRequest` | `explanation`, `user_id` | `explanation` has `min_length=1` |

**Output validation (BEFORE storage):**

| Schema | Fields | Validation |
|--------|--------|------------|
| `ClaimResult` | `claim_id`, `claim_text`, `status`, `confidence_score`, `evidence`, `explanation` | `status` ∈ {supported, weakly_supported, unsupported}, `confidence_score` ∈ [0.0, 1.0] |
| `FinalClaimResult` | Same as ClaimResult | Pipeline-internal validation at every stage |
| `HistoryClaimItem` | `claim_id`, `session_id`, `claim_text` | Fully typed, no loose dicts |
| `HistoryFeedbackItem` | `feedback_id`, `claim_id`, `session_id`, `user_decision`, `created_at` | Fully typed |
| `EvaluateReasoningResponse` | `stress_test_results`, `weakness_summary`, `robustness_summary`, `adversarial_questions` | All fields required, typed |
| `WeaknessItem` | `type`, `detail` | Both non-empty strings |
| `RobustnessSummary` | `robustness_score`, `summary`, `level` | `robustness_score` ∈ [0.0, 1.0], `level` ∈ {low, medium, high} |
| `ThinkingSimulationResponse` | `cognitive_profiles`, `reasoning_graphs`, `strategy_distributions`, `structural_comparison`, `gap_analysis`, `student_graph`, `validation_passed`, `validation_notes` | All types validated via field_validator |
| `ReasoningNode` | `step_id`, `operation_type`, `concept_used`, `abstraction_level`, `strategy_type` | `abstraction_level` ∈ {LOW, MEDIUM, HIGH}, `strategy_type` ∈ {direct_application, rule_based, transformation, reduction, optimization} |
| `ReasoningEdge` | `from_step_id`, `to_step_id`, `relation_type` | `relation_type` ∈ {derives, transforms, simplifies} |
| `GapItem` | `insight`, `severity`, `source` | `severity` ∈ {info, warning, critical}, `source` ∈ {structural, strategy, abstraction, comparison} |
| `CognitiveLoadResponse` | `adapted_explanation`, `load_state`, `control_actions`, `user_state`, `load_metrics`, `reasoning_mode` | `load_state` ∈ {overload, optimal, underload}, `reasoning_mode` ∈ {fine-grained, medium, coarse} |
| `ExplanationStep` | `step_id`, `content`, `concepts`, `abstraction_level`, `depends_on` | `abstraction_level` ∈ {concrete, semi-abstract, abstract} |
| `UserCognitiveState` | `user_id`, `understanding_level`, `reasoning_stability`, `learning_speed`, `overload_signals`, `interaction_count` | Levels ∈ [0.0, 1.0], counts ≥ 0 |
| `CognitiveLoadMetrics` | `step_density`, `concept_gap`, `memory_demand`, `total_load` | All ≥ 0.0 |
| `ControlAction` | `action`, `reason` | Both non-empty strings |

All pipeline output is validated via `ClaimResult` **before** being inserted into the database. If validation fails, the request is rejected with HTTP 500.

Invalid requests receive a `422 Unprocessable Entity` response with Pydantic validation errors.

## Session & State Handling

- **Sessions are created per validation request.** Each `POST /process-input` creates a new session.
- **Session ID is a UUID** generated by the Database module.
- **No authentication.** Sessions are not user-scoped.
- **Session data is immutable** once created (except for feedback additions and claim edits).
- **Edited claims** are appended to the existing session, not replaced.

## Audit Logging

Every user action is persisted in SQLite:

| Action | Stored Data |
|--------|-------------|
| Document upload | `document_id`, `file_name`, `upload_time`, `status`, `page_count` |
| Validation request | `session_id`, `input_text`, `input_type`, `created_at` |
| Claim extraction | `claim_id`, `session_id`, `claim_text` |
| Verification result | `result_id`, `claim_id`, `session_id`, `status`, `confidence_score`, `evidence` (JSON), `explanation` |
| User feedback | `feedback_id`, `claim_id`, `session_id`, `user_decision`, `created_at` |

## Feedback Handling

| Decision | Description | Storage |
|----------|-------------|---------|
| `accept` | User agrees with the verification result | Stored in `feedback` table |
| `reject` | User disagrees with the verification result | Stored in `feedback` table |
| `edit` | User modifies claim text and re-validates | New claims/results appended to session |

Feedback does **not** modify existing results. It is recorded for audit purposes only. The system does not learn from feedback.

## Error Handling

| Scenario | HTTP Code | Detail |
|----------|-----------|--------|
| No documents uploaded | 400 | "No knowledge base available. Please upload documents first." |
| Unsupported file type | 400 | Lists allowed extensions |
| Empty file | 400 | "Uploaded file is empty." |
| File too large | 400 | States maximum size |
| Corrupted PDF | 400 | DocumentProcessor error message |
| Empty input text | 400 | Planner or Pydantic validation error |
| Invalid feedback decision | 422 | Pydantic pattern validation |
| Session not found | 404 | "Session not found." |
| Pipeline stage failure | 500 | Stage-specific error message |
| Document processing failure | 500 | "Document processing failed: ..." |

All errors use FastAPI's `HTTPException` with structured JSON responses.

## CORS Configuration

Configured via the `CORS_ORIGINS` environment variable (comma-separated list):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Default: localhost:5173, localhost:3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Default origins: `http://localhost:5173` (Vite dev server), `http://localhost:3000`.

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLITE_DB_PATH` | `./evilearn.db` | SQLite database file path |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB persistence directory |
| `LLM_API_KEY` | `""` | API key for Groq or OpenAI (required for embeddings) |
| `LLM_MODEL` | `llama3-8b-8192` | LLM model name |
| `LLM_PROVIDER` | `groq` | `groq` or `openai` |
| `EMBEDDING_MODEL` | `text-embedding-ada-002` | Embedding model name |
| `TOP_K_RESULTS` | `5` | Number of evidence chunks to retrieve |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size in MB |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |

## Response Format

All responses are **structured JSON**, never conversational text. The API returns:
- Typed Pydantic models for success responses
- `HTTPException` with `detail` field for errors
- No streaming, no server-sent events

## Running the Server

```bash
cd backend
pip install -r requirements.txt
python -m backend.main
```

The server starts on `http://0.0.0.0:8000` with auto-reload enabled.

## Limitations

- **No authentication or authorization.** All endpoints are publicly accessible.
- **No rate limiting.** No protection against excessive requests.
- **Synchronous pipeline execution.** Long validation requests block the event loop.
- **No file deletion endpoint.** Documents can only be added, not removed via the API.
- **No pagination** on list endpoints (`/documents`, `/history`).
- **No WebSocket support.** No real-time progress updates during pipeline execution.
- **Single-process deployment.** No worker pool or horizontal scaling.
