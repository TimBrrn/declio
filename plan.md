# Plan: Full API Cost Tracking Dashboard (LLM + STT + TTS)

## Goal
Track every API call's cost across all 3 services (OpenAI LLM, Deepgram STT, ElevenLabs TTS), persist per-turn data, and display it in the frontend — per-call detail, per-message breakdown, and aggregated dashboard in EUR.

## Review Decisions (from /plan-eng-review)
- **Pricing**: lives ONLY in `token_usage.py` (DRY — no duplication in settings)
- **EUR conversion**: backend-only (DRY — frontend receives EUR directly)
- **ConversationPort**: 3-tuple return + test helper `_mock_llm_response()` in conftest
- **DB table**: `api_usage` (not `llm_usage`) — generalized for LLM + STT + TTS
- **STT/TTS**: integrated now (lightweight — arithmetic on existing data)
- **Tests**: 6 extra edge case tests added (unknown model, usage=None, 0 turns, empty DB, etc.)

## Architecture Overview

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                     DATA CAPTURE LAYER                           │
  ├──────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  OpenAI GPT-4o ──▶ openai_conversation.py                       │
  │    Returns TokenUsage(prompt=N, completion=M, model="gpt-4o")    │
  │    → thinking_node accumulates in CallState.token_turns          │
  │                                                                  │
  │  Deepgram Nova-2 ──▶ pipeline tracks call duration               │
  │    Cost = duration_seconds / 60 × $0.0043/min                    │
  │    → computed in pipeline.get_metrics()                          │
  │                                                                  │
  │  ElevenLabs v2 ──▶ pipeline._speak() counts chars               │
  │    Cost = total_chars / 1000 × $0.30/1K chars                    │
  │    → accumulated in pipeline._tts_chars, computed in get_metrics()│
  └──────────────────────────┬───────────────────────────────────────┘
                             │ at call end
                             ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                     PERSISTENCE LAYER                            │
  ├──────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  call_records (extended)          api_usage (NEW)                │
  │  ┌─────────────────────────┐     ┌──────────────────────────┐   │
  │  │ ... existing fields      │     │ id                       │   │
  │  │ + total_cost_usd         │     │ call_record_id (FK, idx) │   │
  │  │ + total_cost_eur         │     │ service: llm|stt|tts     │   │
  │  │ + llm_cost_usd           │     │ turn_index               │   │
  │  │ + stt_cost_usd           │     │ prompt_tokens (LLM only) │   │
  │  │ + tts_cost_usd           │     │ completion_tokens (LLM)  │   │
  │  │ + tts_chars_total        │     │ total_tokens (LLM)       │   │
  │  └─────────────────────────┘     │ cost_usd                 │   │
  │                                   │ model/service_detail     │   │
  │                                   │ tool_name (LLM only)     │   │
  │                                   │ chars (TTS only)         │   │
  │                                   │ duration_s (STT only)    │   │
  │                                   │ created_at               │   │
  │                                   └──────────────────────────┘   │
  └──────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                     API LAYER                                    │
  ├──────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  GET /api/calls/              → cost columns on each record      │
  │  GET /api/calls/{id}/usage    → per-turn breakdown (all services)│
  │  GET /api/usage/summary       → aggregated totals + by-service   │
  └──────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                     FRONTEND                                     │
  ├──────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  Dashboard.tsx   → 2 new StatCards: "Cout total", "Cout/appel"   │
  │  CallHistory.tsx → new "Cout" column (EUR)                       │
  │  CallUsageModal  → per-turn detail table (LLM turns + STT + TTS)│
  └──────────────────────────────────────────────────────────────────┘
```

---

## Pricing Reference (all constants in token_usage.py)

| Service | Model | Unit | Price (USD) |
|---|---|---|---|
| LLM | gpt-4o | per 1M input tokens | $2.50 |
| LLM | gpt-4o | per 1M output tokens | $10.00 |
| LLM | gpt-4o-mini | per 1M input tokens | $0.15 |
| LLM | gpt-4o-mini | per 1M output tokens | $0.60 |
| STT | Deepgram Nova-2 | per minute | $0.0043 |
| TTS | ElevenLabs Multilingual v2 | per 1K characters | $0.30 |

**Example call (4 LLM turns, 2min duration, 500 chars TTS):**
- LLM: (6000×2.50 + 1200×10.00) / 1M = $0.027
- STT: 2 × $0.0043 = $0.0086
- TTS: 0.5 × $0.30 = $0.15
- **Total: $0.186 ≈ 0.17 EUR**

---

## Step-by-step Implementation

### Step 1: Domain — TokenUsage value object + pricing constants

**File:** `backend/src/domain/value_objects/token_usage.py` (NEW)

```python
@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = "gpt-4o"

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING["gpt-4o"])
        return (
            self.prompt_tokens * pricing["input"]
            + self.completion_tokens * pricing["output"]
        ) / 1_000_000

# All pricing constants — single source of truth
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}
DEEPGRAM_PRICE_PER_MINUTE = 0.0043   # Nova-2
ELEVENLABS_PRICE_PER_1K_CHARS = 0.30  # Multilingual v2
USD_TO_EUR = 0.92
```

### Step 2: Update ConversationPort protocol

**File:** `backend/src/domain/ports/conversation_port.py` (MODIFY)

```python
async def chat_with_tools(...) -> tuple[str, list[ToolCall], TokenUsage]:
```

### Step 3: Update OpenAI adapter to return TokenUsage

**File:** `backend/src/infrastructure/adapters/openai_conversation.py` (MODIFY)

Build `TokenUsage` from `response.usage`, return as 3rd element.
Handle `usage=None` → `TokenUsage()` with warning log.

### Step 4: Update CallState

**File:** `backend/src/application/graph/state.py` (MODIFY)

```python
token_turns: list[dict]  # per-LLM-turn token data
```

### Step 5: Update thinking_node to accumulate tokens

**File:** `backend/src/application/graph/nodes/thinking.py` (MODIFY)

Unpack 3-tuple. Build turn record dict. Append to `token_turns`.
`tool_name`: join multiple with "+" if >1.

### Step 6: Update pipeline — TTS char tracking + metrics

**File:** `backend/src/infrastructure/audio/pipeline.py` (MODIFY)

- Add `self._tts_chars: int = 0` to `__init__`
- In `_speak()`, add: `self._tts_chars += len(text)`
- In `get_metrics()`, compute:
  - `stt_cost_usd = (duration_seconds / 60) * DEEPGRAM_PRICE_PER_MINUTE`
  - `tts_cost_usd = (self._tts_chars / 1000) * ELEVENLABS_PRICE_PER_1K_CHARS`
  - `llm_cost_usd = sum(turn["cost_usd"] for turn in token_turns)`
  - `total_cost_usd = llm + stt + tts`
  - `total_cost_eur = total_cost_usd * USD_TO_EUR`
  - Return all of these + `token_turns` + `tts_chars_total`

### Step 7: New DB model — ApiUsageModel + extend CallRecordModel

**File:** `backend/src/infrastructure/persistence/models.py` (MODIFY)

```python
class ApiUsageModel(SQLModel, table=True):
    __tablename__ = "api_usage"

    id: str = Field(default_factory=..., primary_key=True)
    call_record_id: str = Field(foreign_key="call_records.id", index=True)
    service: str = ""          # "llm", "stt", "tts"
    turn_index: int = 0        # LLM turn number (0 for stt/tts summary)
    prompt_tokens: int = 0     # LLM only
    completion_tokens: int = 0 # LLM only
    total_tokens: int = 0      # LLM only
    cost_usd: float = 0.0
    model: str = ""            # "gpt-4o", "nova-2", "eleven_multilingual_v2"
    tool_name: str | None = None  # LLM only
    chars: int = 0             # TTS only
    duration_seconds: float = 0.0  # STT only
    created_at: datetime = Field(default_factory=...)
```

Extend `CallRecordModel`:
```python
total_cost_usd: float = 0.0
total_cost_eur: float = 0.0
llm_cost_usd: float = 0.0
stt_cost_usd: float = 0.0
tts_cost_usd: float = 0.0
tts_chars_total: int = 0
total_prompt_tokens: int = 0
total_completion_tokens: int = 0
total_tokens: int = 0
```

### Step 8: Update webhook persistence

**File:** `backend/src/api/webhooks/telnyx_webhook.py` (MODIFY)

In `call.hangup`:
1. Create `CallRecordModel` with all cost aggregate fields
2. `session.flush()`
3. Create `ApiUsageModel` rows:
   - One per LLM turn (from `metrics["token_turns"]`)
   - One for STT (service="stt", cost from duration)
   - One for TTS (service="tts", cost from chars)
4. `session.commit()`

### Step 9: API endpoints

**File:** `backend/src/api/routes/usage.py` (NEW)

```python
@router.get("/summary")
def usage_summary(date_from, date_to, session):
    # Aggregate from call_records:
    # total_calls, total_cost_eur, avg_cost_per_call_eur,
    # llm_cost_total, stt_cost_total, tts_cost_total,
    # total_tokens, avg_tokens_per_call
```

**File:** `backend/src/api/routes/calls.py` (MODIFY)

```python
@router.get("/{call_id}/usage")
def call_usage(call_id, session):
    # SELECT * FROM api_usage WHERE call_record_id = X ORDER BY service, turn_index
```

### Step 10: Settings — EUR conversion only

**File:** `backend/src/infrastructure/config/settings.py` (MODIFY)

```python
usd_to_eur: float = 0.92  # Static rate, override in .env if needed
```

Note: This is a backup/override. Primary EUR conversion uses `USD_TO_EUR` from `token_usage.py`. The setting allows runtime override without redeploy.

### Step 11: Register route in FastAPI app

**File:** `backend/src/api/main.py` (MODIFY)

### Step 12: Frontend types

**File:** `frontend/src/api/client.ts` (MODIFY)

```typescript
// Extend CallRecord:
total_cost_eur: number
llm_cost_usd: number
stt_cost_usd: number
tts_cost_usd: number
total_tokens: number

// New types:
export interface ApiUsageEntry {
  id: string
  service: 'llm' | 'stt' | 'tts'
  turn_index: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  model: string
  tool_name: string | null
  chars: number
  duration_seconds: number
}

export interface UsageSummary {
  total_calls: number
  total_cost_eur: number
  avg_cost_per_call_eur: number
  llm_cost_total_eur: number
  stt_cost_total_eur: number
  tts_cost_total_eur: number
  total_tokens: number
  avg_tokens_per_call: number
}
```

### Step 13: Dashboard cost stat cards

**File:** `frontend/src/pages/Dashboard.tsx` (MODIFY)

Add 2 stat cards using `UsageSummary`:
- "Cout total" — `total_cost_eur` EUR
- "Cout moyen/appel" — `avg_cost_per_call_eur` EUR

### Step 14: CallHistory cost column

**File:** `frontend/src/pages/CallHistory.tsx` (MODIFY)

New "Cout" column: `call.total_cost_eur.toFixed(3)` EUR. Backend provides EUR directly.

### Step 15: Per-call usage detail modal

**File:** `frontend/src/components/CallUsageModal.tsx` (NEW)

Shows:
- LLM turns table: turn | tool | prompt_tokens | completion_tokens | cost
- STT row: duration | cost
- TTS row: chars | cost
- Total row

### Step 16: Update CLI chat script

**File:** `backend/scripts/cli_chat.py` (MODIFY)

Unpack 3-tuple. Display token usage + cost per turn in terminal.

### Step 17: Test helper + existing test updates

**File:** `backend/tests/conftest.py` (NEW or MODIFY)

```python
from backend.src.domain.value_objects.token_usage import TokenUsage

def _mock_llm_response(text: str = "", tools=None):
    """Helper — returns 3-tuple with default TokenUsage for test mocks."""
    return (text, tools or [], TokenUsage())
```

Update 19 mock sites across 5 test files to use `_mock_llm_response()` or add `TokenUsage()` to side_effect lists.

### Step 18: New tests

**New test files:**
- `test_token_usage.py` — TokenUsage: cost calc, zero, unknown model fallback
- `test_api_usage_persistence.py` — ApiUsageModel: LLM rows, STT row, TTS row, 0 turns
- `test_usage_endpoints.py` — summary empty, summary with data, date filter, call usage detail, call not found

**Extended existing:**
- `test_openai_conversation.py` — add `test_returns_token_usage`, `test_usage_none_default`
- `test_pipeline_metrics.py` (or `test_fallback.py`) — add `test_metrics_include_token_and_cost_data`

---

## Files Touched (14 modified + 4 new)

**Modified:**
1. `backend/src/domain/ports/conversation_port.py`
2. `backend/src/infrastructure/adapters/openai_conversation.py`
3. `backend/src/application/graph/state.py`
4. `backend/src/application/graph/nodes/thinking.py`
5. `backend/src/infrastructure/audio/pipeline.py`
6. `backend/src/infrastructure/persistence/models.py`
7. `backend/src/api/webhooks/telnyx_webhook.py`
8. `backend/src/infrastructure/config/settings.py`
9. `backend/src/api/main.py`
10. `backend/src/api/routes/calls.py`
11. `backend/scripts/cli_chat.py`
12. `frontend/src/api/client.ts`
13. `frontend/src/pages/Dashboard.tsx`
14. `frontend/src/pages/CallHistory.tsx`

**New:**
1. `backend/src/domain/value_objects/token_usage.py`
2. `backend/src/api/routes/usage.py`
3. `frontend/src/components/CallUsageModal.tsx`
4. `backend/tests/conftest.py` (or extend if exists)

**Test files (modified + new):**
- 5 existing test files: ~19 mock updates using helper
- 3 new test files: ~16 new tests
