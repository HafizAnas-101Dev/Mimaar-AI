import { Fragment, useEffect, useState, type CSSProperties } from "react";
import { useI18n } from "../i18n";
import { CountUp } from "../motion";
import { ALL_WORK, type ConfidenceLabel, type Evidence, type ReasoningState, type Report, type ReportDefect, type Vendor } from "../types";

const pct = (n: number) => `${Math.round(n * 100)}%`;
const money = (n: number) => Math.round(n).toLocaleString("en-US");

function ConfidenceBar({ value, label }: { value: number; label: ConfidenceLabel }) {
  return (
    <div className={`conf ${label}`} title={pct(value)}>
      <span className="conf-track"><span className="conf-fill" style={{ "--w": pct(value) } as CSSProperties} /></span>
      <span className="conf-value">{pct(value)}</span>
    </div>
  );
}

const SOURCE_KEYS: Record<string, "why.src.mock" | "why.src.muse" | "why.src.glimmer" | "why.src.sam" | "why.src.sam3" | "why.src.reasoning"> = {
  mock: "why.src.mock",
  "muse-grounding": "why.src.muse",
  "glimmer-grounding": "why.src.glimmer",
  "sam-3.1": "why.src.sam",
  "sam-3": "why.src.sam3",
  "muse-spark": "why.src.reasoning",
};

const fill = (text: string, values: Record<string, string>) => text.replace(/\{(\w+)\}/g, (_, k) => values[k] ?? "");

/** Plain-language explanation of one finding: where it came from and how its number was made. */
function WhyPanel({ evidence, kind, scale }: { evidence: Evidence; kind: "element" | "defect"; scale: Report["scale"] }) {
  const { t } = useI18n();
  const share = `${(evidence.image_share * 100).toFixed(1)}%`;
  const unmeasured = evidence.source === "muse-spark";
  let how: string;
  if (kind === "defect") {
    how = unmeasured ? t("why.defectUnmeasured") : fill(t("why.defect"), { share });
  } else if (evidence.area_basis === "dimensions") {
    const perimeter = evidence.rule.match(/perimeter (2 × \([\d.]+ \+ [\d.]+\) m) × height ([\d.]+) m/);
    const wallLength = evidence.rule.match(/wall length ([\d.]+) m × height ([\d.]+) m/);
    const floorArea = evidence.rule.match(/floor area entered, ([\d.]+) m²/);
    const wallHeight = evidence.rule.match(/wall width × height ([\d.]+) m/);
    const dims = evidence.rule.match(/room size ([\d.]+) m × ([\d.]+) m/);
    if (perimeter) how = fill(t("why.wallDims"), { dims: perimeter[1], h: perimeter[2] });
    else if (wallLength) how = fill(t("why.wallDims"), { dims: `${wallLength[1]} m`, h: wallLength[2] });
    else if (floorArea) how = fill(t("why.floorArea"), { area: floorArea[1] });
    else if (wallHeight) how = fill(t("why.wallWidth"), { h: wallHeight[1] });
    else how = fill(t("why.dims"), { dims: dims ? `${dims[1]} m × ${dims[2]} m` : "" });
  } else if (scale.method !== "none" && scale.metres_per_pixel) {
    const cm = (scale.metres_per_pixel * 100).toFixed(2);
    how = scale.method === "assumed_door" ? fill(t("why.areaAssumed"), { share, cm }) : fill(t("why.area"), { share, ref: scale.reference ?? "", cm });
  } else {
    how = fill(t("why.noScale"), { share });
  }
  if (evidence.estimated) how += ` ${t("why.estimated")}`;
  const sourceKey = SOURCE_KEYS[evidence.source];

  return (
    <div className="why-panel">
      <div className="why-stats">
        <div>
          <span className="label">{t("why.detectedBy")}</span>
          <strong>{sourceKey ? t(sourceKey) : evidence.source}</strong>
          {evidence.photo != null && <span className="muted small">{t("results.photo")} {evidence.photo + 1}</span>}
        </div>
        <div>
          <span className="label">{t("why.score")}</span>
          <strong dir="ltr">{unmeasured ? "—" : pct(evidence.detector_score)}</strong>
        </div>
        <div>
          <span className="label">{t("why.coverage")}</span>
          <strong dir="ltr">{unmeasured ? "—" : share}</strong>
        </div>
      </div>
      <p className="why-how"><span className="label">{t("why.how")}</span>{how}</p>
      <details className="why-tech">
        <summary>{t("why.technical")}</summary>
        <code dir="ltr">
          {evidence.rule}
          {evidence.boxes.length > 0 && <> · boxes {evidence.boxes.map((b) => `[${b.join(", ")}]`).join(" ")}</>}
        </code>
      </details>
    </div>
  );
}

function WhyToggle({ open, onClick }: { open: boolean; onClick: () => void }) {
  const { t } = useI18n();
  return (
    <button type="button" className={`why-toggle ${open ? "open" : ""}`} aria-expanded={open} onClick={onClick}>
      <span aria-hidden="true">{open ? "−" : "+"}</span> {t("results.why")}
    </button>
  );
}

/** Whose rates priced this report: a vendor's own price file, imported in the price table. */
function VendorStrip({ vendor }: { vendor: Vendor }) {
  const { t } = useI18n();
  const contact = [vendor.city, vendor.phone, vendor.email, vendor.website].filter(Boolean);
  return (
    <div className="vendor-strip">
      {vendor.logo && <img src={vendor.logo} alt="" />}
      <div>
        <span className="label">{t("results.quoteBy")}</span>
        <strong>{vendor.name}</strong>
        {vendor.tagline && <span className="muted small">{vendor.tagline}</span>}
        {contact.length > 0 && (
          <span className="vendor-contact muted small" dir="ltr">
            {contact.map((c) => <span key={c}>{c}</span>)}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Stands in for the summary while the Muse model writes it. Progress is time-based, not measured:
 * the bar eases towards the usual duration and the steps follow it, so it never claims to be done.
 */
function WritingPanel({ reasoner, expectSeconds }: { reasoner: string; expectSeconds: number }) {
  const { t } = useI18n();
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const timer = window.setInterval(() => setElapsed((Date.now() - start) / 1000), 500);
    return () => clearInterval(timer);
  }, []);
  const progress = Math.min(0.95, 1 - Math.exp((-1.8 * elapsed) / expectSeconds));
  const step = progress < 0.2 ? 0 : progress < 0.5 ? 1 : 2;
  const clock = `${Math.floor(elapsed / 60)}:${String(Math.floor(elapsed % 60)).padStart(2, "0")}`;
  const usual = expectSeconds <= 60 ? t("results.writingAboutMin") : t("results.writingAboutMins");
  const steps = [t("results.writingStep1"), t("results.writingStep2"), t("results.writingStep3")];

  return (
    <div className="writing-panel no-print" role="status" aria-live="polite">
      <div className="writing-head">
        <span className="writing-orb" aria-hidden="true" />
        <strong>{fill(t("results.writingTitle"), { model: reasoner })}</strong>
        <span className="writing-clock" dir="ltr">{clock}</span>
      </div>
      <div className="writing-lines" aria-hidden="true"><i /><i /><i /></div>
      <ol className="writing-steps">
        {steps.map((label, i) => (
          <li key={label} className={i < step ? "done" : i === step ? "active" : ""}>
            <span className="writing-step-dot" aria-hidden="true">{i < step ? "✓" : ""}</span>
            {label}
          </li>
        ))}
      </ol>
      <div className="writing-bar" aria-hidden="true"><span style={{ "--p": progress } as CSSProperties} /></div>
      <p className="writing-foot">{fill(t("results.writingFoot"), { usual })}</p>
    </div>
  );
}

/** Counted elements the customer can correct with − and +; areas can be typed in. */
const COUNTABLE = new Set(["door", "window", "fixture"]);
const AREA_TYPES = new Set(["wall", "floor", "ceiling"]);
// Missed items a customer can add from the table even when none were detected.
const ADDABLE = ["door", "window", "fixture"];

export interface ReportEditing {
  edited: boolean;
  onCount: (type: string, count: number) => void;
  onArea: (type: string, area: number) => void;
  onReset: () => void;
}

/** An area the customer can correct: click it, type the right m², press Enter. */
function AreaCell({ value, onSave }: { value: number | null; onSave?: (v: number) => void }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  if (editing && onSave) {
    return (
      <input
        className="area-input"
        type="number"
        min="0"
        step="0.1"
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => setEditing(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && Number(draft) > 0) {
            onSave(Number(draft));
            setEditing(false);
          }
          if (e.key === "Escape") setEditing(false);
        }}
      />
    );
  }
  if (!onSave) {
    return value != null ? (
      <>{value} m²</>
    ) : (
      <span className="muted needs-scale" title={t("results.needsScaleHint")}>{t("results.needsScale")} ⓘ</span>
    );
  }
  // Editable: the value itself is the button, outlined like the − / + count buttons.
  return (
    <button
      type="button"
      className={`area-chip ${value == null ? "empty" : ""}`}
      title={value == null ? t("results.needsScaleHint") : t("results.editArea")}
      onClick={() => {
        setDraft(value != null ? String(value) : "");
        setEditing(true);
      }}
    >
      <span>{value != null ? `${value} m²` : t("results.addSize")}</span>
      <span className="area-chip-icon" aria-hidden="true">✎</span>
    </button>
  );
}

export default function ReportView({
  report,
  writing,
  reasoner = "Muse",
  expectSeconds = 60,
  onRewrite,
  editing,
  onShowDefect,
  onRetry,
}: {
  report: Report;
  writing?: ReasoningState;
  reasoner?: string;
  expectSeconds?: number;
  /** Shown when the interface language differs from the report's. */
  onRewrite?: () => void;
  /** Present when the customer may correct quantities (the combined or single-photo report). */
  editing?: ReportEditing;
  onShowDefect?: (defect: ReportDefect) => void;
  onRetry?: () => void;
}) {
  const { t, el } = useI18n();
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  const cost = report.cost_estimate;
  const reportDir = report.language === "en" ? "ltr" : "rtl";

  async function copy() {
    await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <section className="report card">
      {onRewrite && writing !== "pending" && (
        <div className="rewrite-bar no-print">
          <span>{t("results.otherLanguage")}</span>
          <button type="button" className="btn primary small" onClick={onRewrite}>{t("results.rewrite")}</button>
        </div>
      )}
      <div className="report-head">
        <h3>{t("results.report")}</h3>
        <div className="no-print actions">
          <button type="button" className="btn ghost small" onClick={copy}>{copied ? t("results.copied") : t("results.copy")}</button>
          <button type="button" className="btn dark small" onClick={() => window.print()}>{t("results.pdf")}</button>
        </div>
      </div>

      {cost.vendor && <VendorStrip vendor={cost.vendor} />}
      <div className="cost-hero">
        <span className="label">{t("results.cost")} · {t(`upload.${cost.finish}`)} {t("results.finish")}</span>
        <p className="cost-value" dir="ltr">
          {cost.low != null && cost.high != null ? (
            <>
              <span className="approx">≈</span> <CountUp value={cost.low} format={money} /> – <CountUp value={cost.high} format={money} /> <small>{cost.currency}</small>
            </>
          ) : (
            t("results.notAvailable")
          )}
        </p>
        {cost.labour_low != null && cost.materials_low != null && (
          <p className="cost-split" dir="ltr">
            <span><span className="label">{t("results.labour")}</span> ≈ {money(cost.labour_low)} – {money(cost.labour_high ?? 0)}</span>
            <span><span className="label">{t("results.materials")}</span> ≈ {money(cost.materials_low)} – {money(cost.materials_high ?? 0)}</span>
          </p>
        )}
        {editing?.edited && (
          <p className="estimate-note">
            <span className="edited-badge">{t("results.edited")}</span>
            <span className="muted small">{t("results.editedNote")}</span>
            <button type="button" className="link small no-print" onClick={editing.onReset}>{t("results.resetEdits")}</button>
          </p>
        )}
        {cost.sample_rates && (
          <p className="estimate-note">
            <span className="sample-badge">{t("results.sampleRates")}</span>
            <span className="muted small">{t("results.sampleRatesNote")}</span>
          </p>
        )}
        {cost.estimated && (
          <p className="estimate-note">
            <span className="estimate-badge">{t("results.estimated")}</span>
            <span className="muted small">{t("results.estimatedNote")}</span>
          </p>
        )}
        {cost.scope.length > 0 && cost.scope.length < ALL_WORK.length && (
          <div className="priced-work">
            <span className="label">{t("scope.priced")}</span>
            {cost.scope.map((w) => <span key={w} className="priced-chip">{t(`work.${w}` as "work.wall")}</span>)}
          </div>
        )}
      </div>

      {writing === "pending" ? (
        <WritingPanel reasoner={reasoner} expectSeconds={expectSeconds} />
      ) : (
        <p className={`summary ${writing === "done" ? "written" : ""}`} dir={reportDir} lang={report.language}>{report.summary}</p>
      )}
      {writing === "failed" && (
        <p className="writing-note failed no-print">
          {t("results.writingFailed")}
          {onRetry && <button type="button" className="link small" onClick={onRetry}>{t("results.retry")}</button>}
        </p>
      )}

      <h4>{t("results.quantities")}</h4>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("results.element")}</th>
              <th className="num">{t("results.count")}</th>
              <th className="num">{t("results.area")}</th>
              <th>{t("results.confidence")}</th>
            </tr>
          </thead>
          <tbody>
            {report.elements.map((e, i) => (
              <Fragment key={e.type}>
                <tr className={open.has(e.type) ? "expanded" : ""} style={{ "--i": i } as CSSProperties}>
                  <td>
                    <span className={`el-dot el-${e.type}`} />
                    <strong>{el(e.type)}</strong>
                    {e.edited && <span className="edited-badge tiny">{t("results.edited")}</span>}
                    {e.evidence && <WhyToggle open={open.has(e.type)} onClick={() => toggle(e.type)} />}
                  </td>
                  <td className="num">
                    {editing && COUNTABLE.has(e.type) ? (
                      <span className="stepper no-print-controls">
                        <button type="button" aria-label="−" disabled={e.count <= 0} onClick={() => editing.onCount(e.type, e.count - 1)}>−</button>
                        <span>{e.count}</span>
                        <button type="button" aria-label="+" onClick={() => editing.onCount(e.type, e.count + 1)}>+</button>
                      </span>
                    ) : (
                      e.count
                    )}
                  </td>
                  <td className="num" dir="ltr">
                    <AreaCell value={e.area_m2} onSave={editing && AREA_TYPES.has(e.type) ? (v) => editing.onArea(e.type, v) : undefined} />
                  </td>
                  <td><ConfidenceBar value={e.confidence} label={e.confidence_label} /></td>
                </tr>
                {e.evidence && open.has(e.type) && (
                  <tr className="why-row">
                    <td colSpan={4}><WhyPanel evidence={e.evidence} kind="element" scale={report.scale} /></td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {editing && ADDABLE.some((type) => !report.elements.some((e) => e.type === type)) && (
        <p className="add-missed no-print">
          <span className="muted small">{t("results.addMissed")}</span>
          {ADDABLE.filter((type) => !report.elements.some((e) => e.type === type)).map((type) => (
            <button key={type} type="button" className="pill" onClick={() => editing.onCount(type, 1)}>+ {el(type)}</button>
          ))}
        </p>
      )}
      <p className="muted small">
        {t("results.scale")}: <span dir="ltr">{report.scale.method !== "none" ? report.scale.reference : t("results.scaleNone")}</span>
      </p>

      <h4>{t("results.defects")}</h4>
      {report.defects.length === 0 ? (
        <p className="muted">{t("results.noDefects")}</p>
      ) : (
        <ul className="defects">
          {report.defects.map((d, i) => (
            <li key={i} className={`defect sev-${d.severity}`} style={{ "--i": i } as CSSProperties}>
              <div className="defect-head">
                <span className={`sev ${d.severity}`}>{t(`sev.${d.severity}`)}</span>
                <strong>{el(d.kind)}</strong>
                <ConfidenceBar value={d.confidence} label={d.confidence_label} />
              </div>
              <div dir={reportDir}>{d.location}</div>
              <div className="muted" dir={reportDir}>{d.why}</div>
              {onShowDefect && d.evidence?.boxes.length ? (
                <button type="button" className="link small show-on-photo no-print" onClick={() => onShowDefect(d)}>{t("results.showOnPhoto")} →</button>
              ) : null}
              {d.evidence && <WhyToggle open={open.has(`d${i}`)} onClick={() => toggle(`d${i}`)} />}
              {d.evidence && open.has(`d${i}`) && <WhyPanel evidence={d.evidence} kind="defect" scale={report.scale} />}
            </li>
          ))}
        </ul>
      )}

      {cost.lines.length > 0 && (
        <>
          <h4>{t("results.cost")}</h4>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("results.item")}</th>
                  <th className="num">{t("results.quantity")}</th>
                  <th className="num">{t("results.range")} ({cost.currency})</th>
                </tr>
              </thead>
              <tbody>
                {cost.lines.map((l, i) => (
                  <tr key={l.item} style={{ "--i": i } as CSSProperties}>
                    <td dir="ltr">
                      {l.item}
                      {l.estimated && <span className="estimate-badge tiny">{t("results.estimated")}</span>}
                      {l.edited && <span className="edited-badge tiny">{t("results.edited")}</span>}
                    </td>
                    <td className="num" dir="ltr">{l.estimated ? "≈ " : ""}{l.quantity} {l.unit === "m2" ? "m²" : t("results.each")}</td>
                    <td className="num" dir="ltr">{money(l.low)} – {money(l.high)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={2}>{t("results.cost")}</td>
                  <td className="num" dir="ltr">{cost.low != null ? `≈ ${money(cost.low)} – ${money(cost.high ?? 0)}` : "—"}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}

      <details className="assumptions">
        <summary>{t("results.assumptions")} ({cost.assumptions.length})</summary>
        <ul dir="ltr">
          {cost.assumptions.map((a) => <li key={a}>{a}</li>)}
        </ul>
      </details>

      <p className="disclaimer" dir={reportDir}>{report.disclaimer}</p>
    </section>
  );
}
