import { useEffect, useState } from "react";
import { Loader2, AlertCircle, Check, Sparkles, UserCircle } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  personaService,
  type PersonaOption,
  type PersonaPage,
} from "@/services/personaService";

// ============== PERSONA PAGE (F11, FR-16) ==============

export default function PersonaPage() {
  const [data, setData] = useState<PersonaPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Selection flow: one busy card + one shared note area (same pattern as Alerts dismiss).
  const [selectingId, setSelectingId] = useState<number | null>(null);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    fetchPersona();
  }, []);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchPersona(false), 5000);

  async function fetchPersona(showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await personaService.get();
      setData(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load personas.");
    } finally {
      if (showSpinner) setLoading(false);
    }
  }

  async function select(option: PersonaOption) {
    setSelectingId(option.id);
    setNote(null);
    try {
      const result = await personaService.update(option.id);
      // Refresh BEFORE the note: the success note must never show while the page
      // still highlights the previous persona (same rule as the Alerts dismiss flow).
      await fetchPersona(false);
      setNote({
        ok: true,
        text: `Persona updated — your AI employee now answers as ${result.persona.name}.`,
      });
    } catch (err) {
      setNote({
        ok: false,
        text: err instanceof ApiError ? err.message : "Could not update the persona.",
      });
    } finally {
      setSelectingId(null);
    }
  }

  // The card to highlight is the EFFECTIVE persona (the choice, or the platform
  // default before any choice is made) — not just the explicit current_persona.
  const currentId = data?.effective_persona?.id ?? null;

  return (
    <div className="space-y-6" data-testid="persona-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Persona</h1>
        <p className="text-sm text-muted-foreground">
          Pick how your AI employee talks to your customers — one ready-made theme, applied to every new chat instantly.
        </p>
      </div>

      {/* ============== ERROR ============== */}
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="persona-loading">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading personas…
        </div>
      ) : data ? (
        <>
          {/* ============== CURRENT PERSONA BANNER ============== */}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-border bg-surface p-4" data-testid="persona-current">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-sm text-muted-foreground">Currently active:</span>
            <span className="text-sm font-semibold" data-testid="persona-current-name">
              {data.current_persona ? data.current_persona.name : "Professional (platform default)"}
            </span>
            {data.using_default && (
              <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted-foreground">
                default — no choice made yet
              </span>
            )}
          </div>

          {/* ============== OPTIONS GRID ============== */}
          <div>
            <h2 className="mb-3 text-sm font-semibold">Ready-made themes ({data.options.length})</h2>
            <div
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
              data-testid="persona-options"
            >
              {data.options.map((option) => (
                <PersonaCard
                  key={option.id}
                  option={option}
                  current={option.id === currentId}
                  busy={selectingId === option.id}
                  onSelect={() => select(option)}
                />
              ))}
            </div>
          </div>

          {/* ============== NOTE ============== */}
          {note && (
            <p
              className={`text-xs ${note.ok ? "text-emerald-500" : "text-destructive"}`}
              data-testid={note.ok ? "persona-success" : "persona-error"}
            >
              {note.text}
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            Tip: the persona shapes the tone of the replies, never the facts — answers always come from your store data. The change applies to every new customer message right away.
          </p>
        </>
      ) : null}
    </div>
  );
}

// ============== OPTION CARD ==============

function PersonaCard({
  option,
  current,
  busy,
  onSelect,
}: {
  option: PersonaOption;
  current: boolean;
  busy: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={busy || current}
      aria-pressed={current}
      data-testid="persona-option"
      data-persona-code={option.code}
      className={`flex h-full flex-col gap-2 rounded-lg border p-4 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring ${
        current
          ? "border-primary bg-primary/10"
          : "border-border bg-surface hover:border-primary/50"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2" data-testid="persona-option-name">
          <UserCircle className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">{option.name}</span>
        </span>
        {current && (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground" data-testid="persona-active-badge">
            <Check className="h-3 w-3" /> Current
          </span>
        )}
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground" data-testid="persona-option-description">
        {option.description}
      </p>
      <span className="mt-auto pt-1 text-xs font-medium text-primary/80">
        {current ? "This is the active persona" : busy ? "Applying…" : "Click to use this persona"}
      </span>
    </button>
  );
}
