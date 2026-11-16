"""Backend-wide constants. Per CODE_RULES 6.5: no magic numbers or strings in code."""

import os

# ============== APP IDENTITY ==============

APP_NAME = "AI Employee"
APP_VERSION = "0.1.0"
APP_SLUG = "shop-assistant"

# ============== API PATH PREFIX ==============

API_V1_PREFIX = "/api/v1"

# ============== ROLES ==============

ROLE_VISITOR = "visitor"
ROLE_USER = "user"
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"

# ============== AI PROVIDERS ==============

AI_PROVIDER_MOCK = "mock"
AI_PROVIDER_GEMINI = "gemini"
AI_PROVIDER_OPENAI = "openai"
AI_PROVIDER_ANTHROPIC = "anthropic"

AI_DEFAULT_PROVIDER = AI_PROVIDER_GEMINI  # When real keys are present, prefer Gemini.

AI_GEMINI_MODEL = "gemini-3.6-flash"      # Stable Flash model per Google AI Studio (gemini-1.5-flash retired → 404).
AI_OPENAI_MODEL = "gpt-4o-mini"
AI_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"

# Read timeout per provider HTTP attempt. 30s produced spurious "The read operation
# timed out" fallbacks to mock on latency spikes (S4 user log 2026-11-16: two Gemini
# calls exceeded 30s while every chat in the same session succeeded) — 60s absorbs
# them; worst case (3 attempts + backoff) stays bounded under ~3.5 minutes.
AI_TIMEOUT_SECONDS = 60
AI_MAX_RETRIES = 2
# Output token budget per AI call. Thinking-style Flash models spend part of it on
# internal reasoning before the strict-JSON answer starts, so 1024 truncated the JSON
# mid-string (CR-01 run 2026-11-13): the budget now covers thinking + the JSON reply.
AI_MAX_OUTPUT_TOKENS = 4096
# Pause between provider attempts: exponential backoff (2s -> 4s -> 8s ...), and on 429
# the provider's requested wait (Retry-After header, or the retryDelay Google embeds in
# the JSON error body) is honored — all capped so a chat request cannot hang forever.
AI_RETRY_SLEEP_SECONDS = 2.0
AI_RETRY_BACKOFF_FACTOR = 2.0
AI_RETRY_MAX_SLEEP_SECONDS = 30.0
# Client-side spacing between real-provider HTTP requests, in seconds (0 = off).
# Free-tier Gemini keys allow ~10 requests/minute: set AI_MIN_CALL_INTERVAL_SECONDS in
# .env (e.g. 6.5) to stay under the per-minute quota.
AI_MIN_CALL_INTERVAL_SECONDS = float(os.getenv("AI_MIN_CALL_INTERVAL_SECONDS", "0") or 0)

# ============== CHAT ==============

CHAT_ROLE_USER = "user"
CHAT_ROLE_ASSISTANT = "assistant"

CHAT_HISTORY_LIMIT = 20        # Past turns passed to the AI (FR-09 memory window).
CHAT_MESSAGE_MAX_CHARS = 4000  # Per-message input cap (schema-level too).

CONVERSATION_STATUS_ACTIVE = "active"
CONVERSATION_STATUS_TRANSFERRED = "transferred"
CONVERSATION_STATUSES = (CONVERSATION_STATUS_ACTIVE, CONVERSATION_STATUS_TRANSFERRED)
TRANSFER_STATUS_PENDING = "pending"

# ============== RAG ==============

RAG_TOP_K = 5  # Always take top 5 paragraphs (per details.txt / FR-07)

# ============== LIMITS & ALERTS ==============

RATE_LIMIT_WINDOW_SECONDS = 60  # Sliding window for the per-key rate limit.
TOKEN_NEAR_LIMIT_PERCENT = 90   # Raise token_near_limit alert at 90% of the plan limit.

# ============== CUSTOMER CASE STATUS ==============

CASE_ACTIVE = "active"
CASE_ANALYZING = "analyzing"
CASE_WARNED = "warned"
CASE_BANNED = "banned"
CASE_TRANSFERRED = "transferred"

CASE_STATUSES = (CASE_ACTIVE, CASE_ANALYZING, CASE_WARNED, CASE_BANNED, CASE_TRANSFERRED)

# ============== VIOLATION ACTIONS ==============

VIOLATION_WARNING = "warning"
VIOLATION_TEMP_BAN = "temp_ban"
VIOLATION_PERMA_BAN = "perma_ban"

VIOLATION_ACTIONS = (VIOLATION_WARNING, VIOLATION_TEMP_BAN, VIOLATION_PERMA_BAN)

# Default violation handling when the store has NO auto-apply policies (pre-F08 behavior).
VIOLATION_SEVERITY_HIGH = "high"
DEFAULT_VIOLATION_ACTION = VIOLATION_WARNING
HIGH_SEVERITY_VIOLATION_ACTION = VIOLATION_PERMA_BAN
POLICY_BASELINE_ACTION = VIOLATION_WARNING

# ============== ALERT TYPES ==============

ALERT_COMPLAINT_SPIKE = "complaint_spike"
ALERT_NEW_VIOLATION = "new_violation"
ALERT_TOKEN_NEAR_LIMIT = "token_near_limit"
ALERT_TRANSFER_PENDING = "transfer_pending"

ALERT_TYPES = (ALERT_COMPLAINT_SPIKE, ALERT_NEW_VIOLATION, ALERT_TOKEN_NEAR_LIMIT, ALERT_TRANSFER_PENDING)

# ============== ALERT SEVERITIES & LIST STATUS FILTER (F10) ==============

ALERT_SEVERITY_INFO = "info"
ALERT_SEVERITY_WARNING = "warning"
ALERT_SEVERITY_CRITICAL = "critical"

ALERT_STATUS_ACTIVE = "active"       # dismissed_at IS NULL
ALERT_STATUS_DISMISSED = "dismissed" # dismissed_at NOT NULL
ALERT_STATUS_ALL = "all"

# ============== COMPLAINT SPIKE (F10, dashboard-computed per PRD 4.5) ==============

# PRD 4.5: complaint_spike = the complaint ratio rose above a threshold in a period.
# The DASHBOARD computes it (the alerts.py docstring design): on GET /dashboard/alerts
# the service counts the assistant-turn analyses of the last window; enough of them and
# a complaint ratio over the threshold raises ONE complaint_spike alert (the
# has_active_alert_of_type guard prevents spamming on every list call).
COMPLAINT_SPIKE_WINDOW_HOURS = 24   # the evaluation period ("a given period" per PRD 4.5)
COMPLAINT_SPIKE_MIN_ANALYSES = 3    # below this the sample is too small to judge
COMPLAINT_SPIKE_RATIO_PERCENT = 60  # complaints/analyses must reach this ratio

# ============== SYSTEM STATUS (F12) ==============

# The two states a service row can report. `degraded` = working in a safe fallback
# mode (mock AI provider, mock email delivery); the UI shows it amber, not red —
# the platform still answers, but the feature is not fully live.
SERVICE_STATUS_OPERATIONAL = "operational"
SERVICE_STATUS_DEGRADED = "degraded"
SERVICE_STATUSES = (SERVICE_STATUS_OPERATIONAL, SERVICE_STATUS_DEGRADED)

# ============== SUBSCRIPTION STATUS ==============

SUB_TRIAL = "trial"
SUB_ACTIVE = "active"
SUB_CANCELED = "canceled"
SUB_EXPIRED = "expired"

# ============== PLAN CODES ==============

PLAN_FREE_TRIAL = "free_trial"
PLAN_STARTER = "starter"
PLAN_PRO = "pro"
PLAN_BUSINESS = "business"

# ============== PERSONA CODES ==============

PERSONA_FRIENDLY = "friendly"
PERSONA_PROFESSIONAL = "professional"
PERSONA_CONCISE = "concise"
PERSONA_DETAILED = "detailed"

PERSONAS = (PERSONA_FRIENDLY, PERSONA_PROFESSIONAL, PERSONA_CONCISE, PERSONA_DETAILED)
