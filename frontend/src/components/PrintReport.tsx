import { createPortal } from "react-dom";
import { useI18n } from "../i18n";
import type { AnalysisResult, Report } from "../types";

const pct = (n: number) => `${Math.round(n * 100)}%`;
const money = (n: number) => Math.round(n).toLocaleString("en-US");

interface Props {
  id: string;
  mode: "live" | "mock";
  report: Report;
  photos: AnalysisResult[];
}

/**
 * The PDF export. Hidden on screen; when printing, it replaces the whole page with a clean,
 * light A4 document. Labels follow the interface language, report text keeps its own language.
 */
export default function PrintReport({ id, mode, report, photos }: Props) {
  const { t, el, lang } = useI18n();
  const cost = report.cost_estimate;
  const reportDir = report.language === "en" ? "ltr" : "rtl";
  const generated = new Date().toLocaleString(lang === "en" ? "en-GB" : lang, { dateStyle: "long", timeStyle: "short" });
  const scaled = report.scale.method !== "none";
  const layerTypes = [...new Map(photos.flatMap((p) => p.layers).map((l) => [l.type, l])).values()];
  // A quotation needs a reference and a validity: the vendor's own date, or 30 days by default.
  const today = new Date();
  const quoteNo = `Q-${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, "0")}${String(today.getDate()).padStart(2, "0")}-${id.slice(0, 4).toUpperCase()}`;
  const validUntil =
    cost.vendor?.valid_until ||
    new Date(today.getTime() + 30 * 86400000).toLocaleDateString(lang === "en" ? "en-GB" : lang, { dateStyle: "long" });

  return createPortal(
    <article className="print-report" dir={lang === "en" ? "ltr" : "rtl"} lang={lang} aria-hidden="true">
      <header className="pr-header">
        <div className="pr-brand">
          <img className="pr-mark" src="/brand/mimaar-logo.png" alt="Mimaar AI" />
          <div>
            <strong>Mimaar AI</strong>
            <span>{t("print.title")}</span>
          </div>
        </div>
        {cost.vendor && (
          <div className="pr-vendor">
            {cost.vendor.logo && <img src={cost.vendor.logo} alt="" />}
            <div>
              <span>{t("results.quoteBy")}</span>
              <strong>{cost.vendor.name}</strong>
              <small dir="ltr">{[cost.vendor.city, cost.vendor.phone, cost.vendor.email, cost.vendor.website].filter(Boolean).join(" · ")}</small>
            </div>
          </div>
        )}
        <dl className="pr-id">
          <div><dt>{t("print.generated")}</dt><dd>{generated}</dd></div>
          <div><dt>{t("print.quoteNo")}</dt><dd dir="ltr">{quoteNo}</dd></div>
          <div><dt>{t("print.validUntil")}</dt><dd>{validUntil}</dd></div>
        </dl>
      </header>

      {mode === "mock" && <p className="pr-banner">{t("print.mock")}</p>}
      {cost.estimated && <p className="pr-banner">{t("results.estimated")}: {t("results.estimatedNote")}</p>}

      <section className="pr-meta">
        <div><dt>{t("print.photos")}</dt><dd dir="ltr">{photos.map((p) => p.filename || "—").join(", ")}</dd></div>
        <div><dt>{t("results.scale")}</dt><dd dir="ltr">{scaled ? report.scale.reference : t("print.noScale")}</dd></div>
        <div><dt>{t("print.pricing")}</dt><dd>{cost.currency} · {t(`upload.${cost.finish}`)}</dd></div>
        <div className="pr-meta-wide"><dt>{t("scope.priced")}</dt><dd>{cost.scope.map((w) => t(`work.${w}` as "work.wall")).join(" · ")}</dd></div>
        <div><dt>{t("upload.reportLang")}</dt><dd>{{ en: "English", ar: "العربية", ur: "اردو" }[report.language]}</dd></div>
      </section>

      <section className="pr-summary">
        <div className="pr-cost">
          <span>{t("results.cost")}</span>
          <strong dir="ltr">
            {cost.low != null && cost.high != null ? <>≈ {money(cost.low)} – {money(cost.high)} <small>{cost.currency}</small></> : t("results.notAvailable")}
          </strong>
          {cost.labour_low != null && cost.materials_low != null && (
            <small className="pr-split" dir="ltr">
              {t("results.labour")} ≈ {money(cost.labour_low)} – {money(cost.labour_high ?? 0)} · {t("results.materials")} ≈ {money(cost.materials_low)} – {money(cost.materials_high ?? 0)}
            </small>
          )}
        </div>
        <p dir={reportDir} lang={report.language}>{report.summary}</p>
      </section>

      <section className="pr-block pr-photos">
        <h2>{t("print.overlay")}</h2>
        <div className={`pr-photo-grid n${Math.min(photos.length, 3)}`}>
          {photos.map((p, i) => (
            <figure key={p.id}>
              <div className="pr-stack">
                <img src={`data:image/png;base64,${p.image_png_base64}`} alt="" />
                {p.layers.map((l) => (
                  <img key={l.type} className="pr-layer" src={`data:image/png;base64,${l.png_base64}`} alt="" />
                ))}
              </div>
              {photos.length > 1 && <figcaption>{p.role ? t(`slot.${p.role}`) : `${t("results.photo")} ${i + 1}`}</figcaption>}
            </figure>
          ))}
        </div>
        <ul className="pr-legend">
          {layerTypes.map((l) => (
            <li key={l.type}><span style={{ background: l.color }} />{el(l.type)}</li>
          ))}
        </ul>
      </section>

      <section className="pr-block">
        <h2>{t("results.quantities")}</h2>
        <table>
          <thead>
            <tr>
              <th>{t("results.element")}</th>
              <th className="num">{t("results.count")}</th>
              <th className="num">{t("results.area")}</th>
              <th>{t("results.confidence")}</th>
              <th>{t("print.basis")}</th>
            </tr>
          </thead>
          <tbody>
            {report.elements.map((e) => (
              <tr key={e.type}>
                <td><span className={`pr-dot el-${e.type}`} />{el(e.type)}</td>
                <td className="num">{e.count}</td>
                <td className="num" dir="ltr">{e.area_m2 != null ? `${e.area_m2} m²` : "—"}</td>
                <td>{t(`sev.${e.confidence_label}`)} · <span dir="ltr">{pct(e.confidence)}</span></td>
                <td className="pr-muted">
                  {e.evidence ? `${pct(e.evidence.image_share)} ${t("print.ofPhoto")}` : ""}
                  {e.area_m2 == null ? ` · ${t("results.needsScale")}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="pr-block">
        <h2>{t("results.defects")}</h2>
        {report.defects.length === 0 ? (
          <p className="pr-muted">{t("results.noDefects")}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t("print.severity")}</th>
                <th>{t("print.defect")}</th>
                <th>{t("print.location")}</th>
                <th>{t("results.confidence")}</th>
                <th>{t("print.reason")}</th>
              </tr>
            </thead>
            <tbody>
              {report.defects.map((d, i) => (
                <tr key={i}>
                  <td><span className={`pr-sev ${d.severity}`}>{t(`sev.${d.severity}`)}</span></td>
                  <td>{el(d.kind)}</td>
                  <td dir={reportDir}>{d.location}</td>
                  <td dir="ltr">{pct(d.confidence)}</td>
                  <td dir={reportDir} className="pr-muted">{d.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {cost.lines.length > 0 && (
        <section className="pr-block">
          <h2>{t("print.breakdown")}</h2>
          <table>
            <thead>
              <tr>
                <th>{t("results.item")}</th>
                <th className="num">{t("results.quantity")}</th>
                <th className="num">{t("results.range")} ({cost.currency})</th>
              </tr>
            </thead>
            <tbody>
              {cost.lines.map((l) => (
                <tr key={l.item}>
                  <td dir="ltr">{l.item}{l.estimated ? ` (${t("results.estimated")})` : ""}</td>
                  <td className="num" dir="ltr">{l.estimated ? "≈ " : ""}{l.quantity} {l.unit === "m2" ? "m²" : t("results.each")}</td>
                  <td className="num" dir="ltr">{money(l.low)} – {money(l.high)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={2}>{t("print.total")}</td>
                <td className="num" dir="ltr">{cost.low != null ? `≈ ${money(cost.low)} – ${money(cost.high ?? 0)}` : "—"}</td>
              </tr>
            </tfoot>
          </table>
        </section>
      )}

      <section className="pr-block">
        <h2>{t("results.assumptions")}</h2>
        <ul className="pr-assumptions" dir="ltr">
          {/* Quantity lines already appear in the cost breakdown table; list only the real assumptions. */}
          {cost.assumptions
            .filter((a) => !cost.lines.some((l) => a.startsWith(`${l.item}:`)))
            .map((a) => <li key={a}>{a}</li>)}
        </ul>
      </section>

      {cost.vendor && (cost.vendor.terms || cost.vendor.valid_until || cost.vendor.address) && (
        <section className="pr-block pr-terms">
          <h2>{t("print.vendorTerms")}</h2>
          {cost.vendor.terms && <p>{cost.vendor.terms}</p>}
          {cost.vendor.valid_until && <p>{t("prices.v.valid_until")}: {cost.vendor.valid_until}</p>}
          {cost.vendor.address && <p className="pr-muted">{cost.vendor.address}</p>}
        </section>
      )}

      <p className="pr-disclaimer" dir={reportDir}>{report.disclaimer}</p>
      <footer className="pr-footer">{t("print.footer")}</footer>
    </article>,
    document.body,
  );
}
