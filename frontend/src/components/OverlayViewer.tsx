import { useState, type CSSProperties } from "react";
import { useI18n } from "../i18n";
import type { AnalysisResult } from "../types";

// Things a customer can tap away when the model got them wrong. Walls, floor and ceiling are
// corrected by typing their area in the report instead.
const TAPPABLE = new Set(["door", "window", "fixture", "crack", "damp", "peeling"]);

const same = (a: number[], b: number[]) => a.length === b.length && a.every((v, i) => v === b[i]);

interface Props {
  result: AnalysisResult;
  /** Boxes the customer removed, per element type or defect kind. */
  removed?: Record<string, number[][]>;
  onToggle?: (type: string, box: number[]) => void;
  /** A defect picked in the report, outlined until another is picked. */
  highlight?: number[] | null;
}

export default function OverlayViewer({ result, removed = {}, onToggle, highlight }: Props) {
  const { t, el } = useI18n();
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [opacity, setOpacity] = useState(0.85);
  const [fixing, setFixing] = useState(false);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);

  function toggle(type: string) {
    const next = new Set(hidden);
    next.has(type) ? next.delete(type) : next.add(type);
    setHidden(next);
  }

  const boxes = [
    ...result.report.elements.filter((e) => TAPPABLE.has(e.type)).flatMap((e) => (e.evidence?.boxes ?? []).map((box) => ({ type: e.type, box }))),
    ...result.report.defects.filter((d) => d.evidence?.boxes.length).map((d) => ({ type: d.kind, box: d.evidence!.boxes[0] })),
  ];
  const isRemoved = (type: string, box: number[]) => (removed[type] ?? []).some((b) => same(b, box));

  return (
    <section className="viewer card">
      <div className={`stack ${fixing ? "fixing" : ""}`}>
        <img
          src={`data:image/png;base64,${result.image_png_base64}`}
          alt="Site photo"
          decoding="async"
          onLoad={(e) => setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
        />
        {result.layers.map((layer, i) => (
          <img
            key={layer.type}
            decoding="async"
            className={`layer ${hidden.has(layer.type) ? "off" : ""}`}
            style={{ opacity: hidden.has(layer.type) ? 0 : opacity, "--i": i } as CSSProperties}
            src={`data:image/png;base64,${layer.png_base64}`}
            alt=""
          />
        ))}
        {size && (fixing || highlight) && (
          <svg className="box-layer" viewBox={`0 0 ${size.w} ${size.h}`} preserveAspectRatio="none">
            {fixing &&
              boxes.map(({ type, box }) => {
                const gone = isRemoved(type, box);
                return (
                  <g key={`${type}-${box.join("-")}`} className={`tap-box ${gone ? "gone" : ""}`} onClick={() => onToggle?.(type, box)}>
                    <rect x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} />
                    <text x={box[0] + 6} y={box[1] + 18}>{gone ? `✕ ${el(type)}` : el(type)}</text>
                  </g>
                );
              })}
            {!fixing && highlight && (
              <rect className="highlight-box" x={highlight[0] - 6} y={highlight[1] - 6} width={highlight[2] - highlight[0] + 12} height={highlight[3] - highlight[1] + 12} />
            )}
          </svg>
        )}
        <span className="viewer-sweep" aria-hidden="true" />
      </div>
      <div className="viewer-controls no-print">
        <span className="label">{t("results.layers")}</span>
        <div className="legend">
          {result.layers.map((layer) => (
            <button
              key={layer.type}
              type="button"
              className={hidden.has(layer.type) ? "off" : ""}
              aria-pressed={!hidden.has(layer.type)}
              onClick={() => toggle(layer.type)}
            >
              <span className="swatch" style={{ background: layer.color }} />
              {el(layer.type)}
            </button>
          ))}
        </div>
        <label className="opacity">
          <span className="label">{t("results.opacity")}</span>
          <input type="range" min="0" max="1" step="0.05" value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
        </label>
        {onToggle && boxes.length > 0 && (
          <div className="fix-row">
            <button type="button" className={`btn small ${fixing ? "primary" : "ghost"}`} onClick={() => setFixing(!fixing)}>
              {fixing ? t("results.fixDone") : t("results.fix")}
            </button>
            {fixing && <span className="muted small">{t("results.fixHint")}</span>}
          </div>
        )}
      </div>
    </section>
  );
}
