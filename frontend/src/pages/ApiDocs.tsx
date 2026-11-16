import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Copy, KeyRound, Send, Database, History, HeartPulse, ShieldAlert, Rocket } from "lucide-react";

// ============== API DOCUMENTATIONS PAGE (F13, FR-05 + FR-13) ==============
// Static content page (per the WORKFLOW page map: "(static content) | success") —
// it documents the REAL public API contract (§8.3): X-API-Key header auth,
// the {ok, data, error} envelope, and copy-pasteable curl + Python requests
// examples. No fetches here: everything below mirrors the backend routes as built.

interface DocSection {
  id: string;
  title: string;
  icon: typeof Rocket;
  description: string;
  blocks: CodeBlockData[];
  extra?: "errors-table";
}

interface CodeBlockData {
  language: string;
  label: string;
  code: string;
}

const BASE_URL_PLACEHOLDER = "http://127.0.0.1:8000";

const ENVELOPE_EXAMPLE = `{
  "ok": true,
  "data": { ... },
  "error": null
}

// on failure:
{
  "ok": false,
  "data": null,
  "error": { "code": "unauthorized", "message": "Invalid or revoked API key" }
}`;

const AUTH_CURL = `curl -X POST ${BASE_URL_PLACEHOLDER}/api/v1/chat \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ak_live_YOUR_KEY_HERE" \\
  -d '{"customer_external_id": "cust-1", "message": "Do you ship to Alexandria?"}'`;

const AUTH_PYTHON = `import requests

BASE_URL = "${BASE_URL_PLACEHOLDER}"
API_KEY = "ak_live_YOUR_KEY_HERE"  # created once in Dashboard -> API Keys

# Every public endpoint is authenticated with the X-API-Key header.
headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}`;

const UPLOAD_PYTHON = `import requests

BASE_URL = "${BASE_URL_PLACEHOLDER}"
headers = {"Content-Type": "application/json", "X-API-Key": "ak_live_YOUR_KEY_HERE"}

# Upload your store catalog so the AI employee can answer from real data (FR-05).
# items: up to 500 per request, id <= 200 chars, content <= 100,000 chars each.
payload = {
    "items": [
        {"id": "SKU-001", "content": "Cotton T-shirt, navy, size L. Price 450 EGP. In stock."},
        {"id": "SKU-002", "content": "Leather belt, brown. Price 300 EGP. Free shipping over 500 EGP."},
    ],
    "source": "api",
}

response = requests.post(f"{BASE_URL}/api/v1/data", json=payload, headers=headers, timeout=30)
result = response.json()

if result["ok"]:
    print(f"Uploaded: {result['data']['uploaded_count']} items, "
          f"{result['data']['total_bytes']} bytes total")
else:
    print(f"Error {response.status_code}: {result['error']}")`;

const UPLOAD_CURL = `curl -X POST ${BASE_URL_PLACEHOLDER}/api/v1/data \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ak_live_YOUR_KEY_HERE" \\
  -d '{
    "items": [{"id": "SKU-001", "content": "Cotton T-shirt, navy, size L. Price 450 EGP."}],
    "source": "api"
  }'`;

const CHAT_PYTHON = `import requests

BASE_URL = "${BASE_URL_PLACEHOLDER}"
headers = {"Content-Type": "application/json", "X-API-Key": "ak_live_YOUR_KEY_HERE"}

# Send one customer message and get the unified AI response (FR-11).
# conversation_id is optional: omit it to start a new conversation, then reuse
# the returned conversation_id to keep the same thread.
payload = {
    "customer_external_id": "cust-1",
    "message": "What colors does the cotton T-shirt come in?",
    # "conversation_id": 42,        # continue an existing conversation
    # "request_human": True,        # customer accepts the human-transfer offer
}

response = requests.post(f"{BASE_URL}/api/v1/chat", json=payload, headers=headers, timeout=60)
result = response.json()

if result["ok"]:
    data = result["data"]
    print(f"Reply: {data['reply']}")
    print(f"Case status: {data['case_status']}")          # analyzing | answered | ...
    if data.get("transfer_request"):
        print("The AI offered a human transfer — handle it in your widget")
else:
    print(f"Error {response.status_code}: {result['error']}")`;

const CHAT_CURL = `curl -X POST ${BASE_URL_PLACEHOLDER}/api/v1/chat \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ak_live_YOUR_KEY_HERE" \\
  -d '{"customer_external_id": "cust-1", "message": "Do you ship to Alexandria?"}'`;

const HISTORY_PYTHON = `import requests

BASE_URL = "${BASE_URL_PLACEHOLDER}"
headers = {"X-API-Key": "ak_live_YOUR_KEY_HERE"}

# Conversation memory: fetch the messages of one conversation (oldest first).
conversation_id = 42
response = requests.get(
    f"{BASE_URL}/api/v1/conversations/{conversation_id}/history",
    headers=headers,
    timeout=30,
)
result = response.json()

if result["ok"]:
    for message in result["data"]["messages"]:
        role = "customer" if message["role"] == "customer" else "ai"
        print(f"{role}: {message['content']}")
else:
    print(f"Error {response.status_code}: {result['error']}")`;

const HEALTH_CURL = `curl ${BASE_URL_PLACEHOLDER}/api/health`;

const HEALTH_PYTHON = `import requests

# Liveness probe — no authentication required.
response = requests.get("${BASE_URL_PLACEHOLDER}/api/health", timeout=10)
print(response.json())  # {"ok": true, "data": {"status": "healthy", ...}}`;

const ERRORS_ROWS: { code: number; meaning: string; detail: string }[] = [
  { code: 401, meaning: "unauthorized", detail: "Missing, invalid, or revoked X-API-Key header (or expired session token on the dashboard API)." },
  { code: 402, meaning: "plan limit", detail: "The store's plan data/tokens allowance is exhausted — upgrade the plan in Plans & Usage." },
  { code: 403, meaning: "forbidden", detail: "The customer is banned, or the owner session has no store yet." },
  { code: 413, meaning: "payload too large", detail: "An upload exceeded the size cap (per-item content <= 100,000 chars)." },
  { code: 422, meaning: "validation error", detail: "The request body failed validation (missing field, bad type, item id > 200 chars, > 500 items...)." },
  { code: 429, meaning: "rate limited", detail: "More than 60 requests per minute with the same API key — slow down and retry." },
];

const SECTIONS: DocSection[] = [
  {
    id: "getting-started",
    title: "Getting started",
    icon: Rocket,
    description:
      "The AI Employee public API is a REST API served by your platform backend. Every response uses the same JSON envelope: ok (bool), data (payload), and error (code + message on failure). Replace the base URL below with your deployment origin (the examples use the local dev server).",
    blocks: [{ language: "json", label: "Response envelope", code: ENVELOPE_EXAMPLE }],
  },
  {
    id: "authentication",
    title: "Authentication",
    icon: KeyRound,
    description:
      "Create an API key once in Dashboard → API Keys (it is shown in plain text only at creation — store it safely). Every public endpoint is authenticated with the X-API-Key HTTP header; the key identifies your store, applies your plan limits, and powers the per-key rate limit (60 requests/minute).",
    blocks: [
      { language: "python", label: "Setup — requests", code: AUTH_PYTHON },
      { language: "bash", label: "curl", code: AUTH_CURL },
    ],
  },
  {
    id: "upload-data",
    title: "Upload data — POST /api/v1/data",
    icon: Database,
    description:
      "Upload your store catalog (products, policies, FAQs) so the AI employee answers from real data (FR-05). Each item carries your own id (e.g. a SKU) and free-text content; the retrieval layer searches this corpus on every chat (top 5 matches). Up to 500 items per request, each content up to 100,000 characters.",
    blocks: [
      { language: "python", label: "Python — requests", code: UPLOAD_PYTHON },
      { language: "bash", label: "curl", code: UPLOAD_CURL },
    ],
  },
  {
    id: "chat",
    title: "Chat — POST /api/v1/chat",
    icon: Send,
    description:
      "The core endpoint your store widget calls: one customer message in, one unified AI response out. The engine records the conversation, analyzes sentiment/complaint/violation signals, searches your uploaded data, enforces the persona and the plan limits, and raises owner alerts when needed. Keep customer_external_id stable per customer to preserve memory; reuse conversation_id to continue a thread.",
    blocks: [
      { language: "python", label: "Python — requests", code: CHAT_PYTHON },
      { language: "bash", label: "curl", code: CHAT_CURL },
    ],
  },
  {
    id: "conversation-history",
    title: "Conversation history — GET /api/v1/conversations/{id}/history",
    icon: History,
    description:
      "Fetch the messages of one conversation in chronological order (oldest first) — useful for rendering the thread in your own widget or syncing it to your helpdesk. The conversation must belong to the store identified by the X-API-Key header.",
    blocks: [{ language: "python", label: "Python — requests", code: HISTORY_PYTHON }],
  },
  {
    id: "health",
    title: "Health — GET /api/health",
    icon: HeartPulse,
    description:
      "Unauthenticated liveness probe for uptime monitors and deploy checks. The owner-facing service report lives separately in Dashboard → System Status.",
    blocks: [
      { language: "bash", label: "curl", code: HEALTH_CURL },
      { language: "python", label: "Python — requests", code: HEALTH_PYTHON },
    ],
  },
  {
    id: "errors",
    title: "Rate limits & error codes",
    icon: ShieldAlert,
    description:
      "Every failure follows the same envelope with an error.code + error.message. The per-key rate limit is 60 requests/minute; when you exceed it the API answers 429 — back off briefly and retry. The table below lists the codes a store integration can meet on the public endpoints.",
    blocks: [],
    extra: "errors-table",
  },
];

// ============== CODE BLOCK (language badge + copy) ==============

function CodeBlock({ block }: { block: CodeBlockData }) {
  const [copied, setCopied] = useState(false);

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(block.code);
    } catch {
      // clipboard API unavailable (permissions/insecure context) — textarea fallback
      const textarea = document.createElement("textarea");
      textarea.value = block.code;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border" data-testid="docs-code-block" data-language={block.language}>
      <div className="flex items-center justify-between gap-2 border-b border-border bg-surface-2 px-3 py-1.5">
        <span className="text-xs font-medium text-muted-foreground">{block.label}</span>
        <span className="flex items-center gap-2">
          <span className="rounded bg-background/60 px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">
            {block.language}
          </span>
          <button
            type="button"
            onClick={copyToClipboard}
            data-testid="docs-copy-btn"
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-background/60 hover:text-foreground"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied!" : "Copy"}
          </button>
        </span>
      </div>
      <pre className="max-h-96 overflow-auto bg-background/50 p-3 font-mono text-xs leading-relaxed text-foreground">
        <code>{block.code}</code>
      </pre>
    </div>
  );
}

// ============== ERRORS TABLE ==============

function ErrorsTable() {
  return (
    <div className="overflow-x-auto rounded-lg border border-border" data-testid="docs-errors-table">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2 text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">HTTP</th>
            <th className="px-3 py-2 font-medium">error.code</th>
            <th className="px-3 py-2 font-medium">When</th>
          </tr>
        </thead>
        <tbody>
          {ERRORS_ROWS.map((row) => (
            <tr key={row.code} className="border-b border-border/60 last:border-0" data-testid="docs-error-row">
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs font-semibold text-warning">{row.code}</td>
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{row.meaning}</td>
              <td className="px-3 py-2 text-xs text-muted-foreground">{row.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============== PAGE ==============

export default function ApiDocsPage() {
  return (
    <div className="space-y-6" data-testid="docs-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">API Documentations</h1>
        <p className="text-sm text-muted-foreground">
          Integrate your AI employee into your store: authenticate with an API key, upload your catalog, send customer messages, and read conversations back — with copy-pasteable examples for curl and the Python requests library.
        </p>
      </div>

      {SECTIONS.map((section) => {
        const Icon = section.icon;
        return (
          <section
            key={section.id}
            className="space-y-3 rounded-lg border border-border bg-surface p-4 sm:p-5"
            data-testid="docs-section"
            data-section-id={section.id}
          >
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-surface-2">
                <Icon className="h-4 w-4 text-primary" />
              </span>
              <div className="min-w-0">
                <h2 className="text-base font-semibold">{section.title}</h2>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{section.description}</p>
              </div>
            </div>

            {section.blocks.map((block) => (
              <CodeBlock key={block.label} block={block} />
            ))}

            {section.extra === "errors-table" && <ErrorsTable />}
          </section>
        );
      })}

      <p className="text-xs text-muted-foreground">
        Tip: the interactive OpenAPI schema (try-it-out for every endpoint) is served by the backend at /docs while the server is running.
      </p>
    </div>
  );
}

// ============== PUBLIC STANDALONE WRAPPER (support round S1, 2026-11-16) ==============
// The landing page's "API Docs" button used to open the raw FastAPI Swagger (/docs);
// the user expected the project's OWN API Documentations page. The page now has a
// public route (/api-docs) reachable without login, with a minimal chrome wrapper.
export function PublicApiDocsPage() {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <header className="border-b border-border/60">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <span className="text-sm font-semibold tracking-tight">AI Employee</span>
          <Link
            to="/"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            ← Back to home
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        <ApiDocsPage />
      </main>
    </div>
  );
}
