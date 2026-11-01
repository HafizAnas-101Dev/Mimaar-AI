import { useState } from "react";
import { clearHistory, deleteHistory, renameHistory } from "../api";
import { useI18n } from "../i18n";
import { Reveal, SplitWords } from "../motion";
import type { HistoryEntry } from "../types";

interface Props {
  entries: HistoryEntry[];
  activeId?: string;
  onOpen: (id: string) => void;
  onDeleted: () => void;
}

const PREVIEW_COUNT = 6;
type Kind = "all" | "room" | "photo";

export default function HistoryPanel({ entries, activeId, onOpen, onDeleted }: Props) {
  const { t, lang } = useI18n();
  const [showAll, setShowAll] = useState(false);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<Kind>("all");
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);

  const q = query.trim().toLowerCase();
  const matching = entries.filter(
    (e) => (kind === "all" || e.kind === kind) && (!q || e.title.toLowerCase().includes(q) || e.summary.toLowerCase().includes(q)),
  );
  const shown = showAll || q ? matching : matching.slice(0, PREVIEW_COUNT);

  async function remove(id: string) {
    await deleteHistory(id).catch(() => undefined);
    onDeleted();
  }

  async function saveName() {
    if (!renaming) return;
    const title = renaming.title.trim();
    setRenaming(null);
    if (title) await renameHistory(renaming.id, title).catch(() => undefined);
    onDeleted();
  }

  async function clearAll() {
    if (!window.confirm(t("history.clearConfirm").replace("{n}", String(entries.length)))) return;
    await clearHistory().catch(() => undefined);
    onDeleted();
  }

  return (
    <div className="history no-print">
      <div className="section-head">
        <span className="kicker">{t("nav.history")}</span>
        <SplitWords as="h2" text={t("history.title")} className="display" />
      </div>
      {entries.length === 0 && <p className="muted center">{t("history.empty")}</p>}
      {entries.length > 0 && (
        <div className="history-tools">
          <input type="search" value={query} placeholder={t("history.search")} onChange={(e) => setQuery(e.target.value)} />
          <div className="segmented">
            {(["all", "room", "photo"] as const).map((k) => (
              <button key={k} type="button" className={kind === k ? "active" : ""} onClick={() => setKind(k)}>
                {t(`history.filter.${k}`)}
              </button>
            ))}
          </div>
          <button type="button" className="link danger small" onClick={clearAll}>{t("history.clear")}</button>
        </div>
      )}
      {entries.length > 0 && matching.length === 0 && <p className="muted center">{t("history.noMatch")}</p>}
      <div className="history-grid">
        {shown.map((e, i) => (
          <Reveal key={e.id} delay={(i % 3) * 80} className={`history-card card glass-card ${e.id === activeId ? "active" : ""}`}>
            {renaming?.id === e.id ? (
              <div className="open renaming">
                <span className={`tag ${e.kind}`}>{t(`history.${e.kind}`)}</span>
                <input
                  autoFocus
                  value={renaming.title}
                  maxLength={120}
                  onChange={(ev) => setRenaming({ id: e.id, title: ev.target.value })}
                  onBlur={saveName}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter") saveName();
                    if (ev.key === "Escape") setRenaming(null);
                  }}
                />
              </div>
            ) : (
              <button type="button" className="open" onClick={() => onOpen(e.id)}>
                <span className={`tag ${e.kind}`}>{t(`history.${e.kind}`)}</span>
                <strong dir="auto" className="history-title" title={e.title}>{e.title}</strong>
                <span className="muted small">{new Date(e.created_at).toLocaleString(lang === "en" ? "en-GB" : lang)}</span>
                {e.low != null && e.high != null && (
                  <span className="history-cost" dir="ltr">
                    ≈ {Math.round(e.low).toLocaleString("en-US")} – {Math.round(e.high).toLocaleString("en-US")} {e.currency}
                  </span>
                )}
              </button>
            )}
            <div className="history-actions">
              <button type="button" className="link small" onClick={() => setRenaming({ id: e.id, title: e.title })}>{t("history.rename")}</button>
              <button type="button" className="link danger small" onClick={() => remove(e.id)}>{t("history.delete")}</button>
            </div>
          </Reveal>
        ))}
      </div>
      {!q && matching.length > PREVIEW_COUNT && (
        <div className="center history-more">
          <button type="button" className="btn ghost small" onClick={() => setShowAll(!showAll)}>
            {showAll ? t("history.less") : `${t("history.all")} (${matching.length})`}
          </button>
        </div>
      )}
    </div>
  );
}
