import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, AlertCircle, Bot, User, ThumbsUp, ShieldAlert, HeartCrack } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  conversationsService,
  type ConversationDetail as ConversationDetailData,
  type ConversationMessage,
} from "@/services/conversationsService";
import { StatusBadge } from "@/pages/Conversations";

// ============== CONVERSATION DETAIL PAGE ==============

export default function ConversationDetailPage() {
  const { id } = useParams();
  const conversationId = Number(id);
  const [detail, setDetail] = useState<ConversationDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(conversationId) || conversationId <= 0) {
      setError("Invalid conversation id.");
      setLoading(false);
      return;
    }
    fetchDetail(conversationId);
  }, [conversationId]);

  // S5: live refresh while the tab is visible — new messages appear without a manual reload.
  useAutoRefresh(() => {
    if (Number.isFinite(conversationId) && conversationId > 0) fetchDetail(conversationId, false);
  }, 4000, [conversationId]);

  async function fetchDetail(cid: number, showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await conversationsService.get(cid);
      setDetail(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load the conversation.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6" data-testid="conversation-detail">
      {/* ============== HEADER ============== */}
      <div>
        <Link
          to="/dashboard/conversations"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to conversations
        </Link>
        {loading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="conversation-detail-loading">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading conversation…
          </div>
        ) : error ? (
          <div
            className="mt-4 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
            data-testid="conversation-detail-error"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        ) : detail ? (
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <h1 className="text-2xl font-bold tracking-tight">
              Conversation with <span className="font-mono text-lg">{detail.conversation.customer_external_id}</span>
            </h1>
            <StatusBadge status={detail.conversation.status} />
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted-foreground">
              case: {detail.conversation.case_status}
            </span>
            <span className="text-xs text-muted-foreground">
              {detail.conversation.messages_count} messages · started {formatDate(detail.conversation.started_at)}
            </span>
          </div>
        ) : null}
      </div>

      {/* ============== MESSAGE THREAD ============== */}
      {detail && (
        <div className="space-y-4" data-testid="conversation-thread">
          {detail.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>
      )}
    </div>
  );
}

// ============== MESSAGE BUBBLE ==============

function MessageBubble({ message }: { message: ConversationMessage }) {
  const isUser = message.role === "user";
  const Icon = isUser ? User : Bot;
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`} data-testid="message-bubble">
      <div className={`max-w-[85%] sm:max-w-[70%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            isUser
              ? "border-primary/30 bg-primary/10 text-foreground"
              : "border-border bg-surface text-foreground"
          }`}
        >
          <div className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Icon className="h-3.5 w-3.5" />
            <span>{isUser ? "Customer" : "AI employee"}</span>
            <span>· {formatDate(message.sent_at)}</span>
          </div>
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
        {message.analysis && <AnalysisChips analysis={message.analysis} />}
      </div>
    </div>
  );
}

// ============== ANALYSIS CHIPS ==============

function AnalysisChips({ analysis }: { analysis: NonNullable<ConversationMessage["analysis"]> }) {
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="analysis-chip">
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${sentimentStyle(analysis.sentiment)}`}
      >
        {analysis.sentiment}
      </span>
      {analysis.is_complaint && (
        <span className="inline-flex items-center gap-1 rounded-full bg-orange-500/10 px-2 py-0.5 text-xs font-medium text-orange-500">
          <HeartCrack className="h-3 w-3" /> complaint
        </span>
      )}
      {analysis.is_violation && (
        <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
          <ShieldAlert className="h-3 w-3" /> violation{analysis.violation_type ? `: ${analysis.violation_type}` : ""}
          {analysis.severity ? ` (${analysis.severity})` : ""}
        </span>
      )}
      {!analysis.is_complaint && !analysis.is_violation && (
        <span className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted-foreground">
          <ThumbsUp className="h-3 w-3" /> clean
        </span>
      )}
    </div>
  );
}

function sentimentStyle(sentiment: string): string {
  if (sentiment === "positive") return "bg-success/10 text-success";
  if (sentiment === "negative") return "bg-destructive/10 text-destructive";
  return "bg-surface-2 text-muted-foreground";
}

// ============== FORMAT HELPERS ==============

function formatDate(iso: string): string {
  try {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}
