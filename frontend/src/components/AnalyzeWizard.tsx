import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type Dispatch, type SetStateAction } from "react";
import { loadSample } from "../api";
import { scrollToTarget } from "../motion";
import { useI18n } from "../i18n";
import {
  ALL_WORK,
  ROOM_TYPES,
  WALL_WORK,
  type Finish,
  type Language,
  type PhotoRole,
  type RolePhoto,
  type RoomType,
  type SpaceMode,
  type WorkItem,
  withoutReplacements,
} from "../types";
import ScopePicker from "./ScopePicker";
import { ImagePlus, RoomIcon, Upload, WallIcon } from "./Icons";

export interface AnalyzeOptions {
  scaleElement: "" | "door" | "window";
  scaleHeight: number | null;
  roomLength: number | null;
  roomWidth: number | null;
  ceilingHeight: number | null;
  wallWidth: number | null;
  /** For a room that isn't a rectangle: used instead of length x width and the perimeter. */
  roomArea: number | null;
  roomPerimeter: number | null;
  /** "estimate" = no tape measure: a standard door and typical sizes fill the gaps. */
  measure: "exact" | "estimate";
  roomType: RoomType;
  language: Language;
  currency: string;
  finish: Finish;
  scope: WorkItem[];
}

export const DEFAULT_SCOPE: WorkItem[] = withoutReplacements(ALL_WORK);

const num = (value: string) => (value ? Number(value) : null);

/** A labelled number input in metres. */
function MetreField({ label, value, onChange, min = 0.5, max = 100 }: { label: string; value: number | null; onChange: (v: number | null) => void; min?: number; max?: number }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type="number" min={min} max={max} step="0.05" value={value ?? ""} onChange={(e) => onChange(num(e.target.value))} />
    </label>
  );
}

type SlotId = "floor" | "ceiling" | "wall1" | "wall2" | "wall3" | "wall4";
const SLOTS: { id: SlotId; role: PhotoRole; n?: number }[] = [
  { id: "floor", role: "floor" },
  { id: "ceiling", role: "ceiling" },
  { id: "wall1", role: "wall", n: 1 },
  { id: "wall2", role: "wall", n: 2 },
  { id: "wall3", role: "wall", n: 3 },
  { id: "wall4", role: "wall", n: 4 },
];
// Complete example rooms, each photographed from six angles: backend/samples/<id>-floor.jpg,
// -ceiling.jpg and -wall-1..4.jpg, plus a collage preview in frontend/public/samples/.
const ROOM_EXAMPLES = ["living-room", "bedroom", "sitting-room", "empty-room"] as const;
type RoomExample = (typeof ROOM_EXAMPLES)[number];
const exampleFiles = (id: RoomExample): Record<SlotId, string> => ({
  floor: `${id}-floor.jpg`,
  ceiling: `${id}-ceiling.jpg`,
  wall1: `${id}-wall-1.jpg`,
  wall2: `${id}-wall-2.jpg`,
  wall3: `${id}-wall-3.jpg`,
  wall4: `${id}-wall-4.jpg`,
});
// iPhone photos are HEIC; browsers often report them with an empty type, so check the name too.
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];
const IMAGE_EXT = /\.(jpe?g|png|webp|heic|heif)$/i;
const isImage = (f: File) => IMAGE_TYPES.includes(f.type) || IMAGE_EXT.test(f.name);
const isHeic = (f: File) => /heic|heif/i.test(f.type) || /\.(heic|heif)$/i.test(f.name);

interface Props {
  options: AnalyzeOptions;
  onOptions: Dispatch<SetStateAction<AnalyzeOptions>>;
  samples: string[];
  currencies: string[];
  defaultCurrency?: string;
  busy: boolean;
  onGenerate: (mode: SpaceMode, photos: RolePhoto[]) => void;
}

/** One upload tile: shows its label, takes a click or a drop, previews the photo. */
// Phones and tablets get a camera button next to each slot; desktops keep just the file picker.
const TOUCH = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;

function PhotoSlot({
  label,
  file,
  onFile,
  tip,
  large = false,
}: {
  label: string;
  file?: File;
  onFile: (f: File | undefined) => void;
  tip?: string;
  large?: boolean;
}) {
  const { t } = useI18n();
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    // Most browsers can't draw HEIC; the server converts it, so show the file name instead.
    if (!file || isHeic(file)) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const take = (list: FileList | null | undefined) => {
    const f = list && Array.from(list).find(isImage);
    if (f) onFile(f);
  };

  return (
    <div className={`slot ${large ? "large" : ""} ${file ? "filled" : ""} ${dragging ? "dragging" : ""}`}>
      <label
        className="slot-drop"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          take(e.dataTransfer.files);
        }}
      >
        {preview ? (
          <img src={preview} alt={label} />
        ) : file ? (
          <span className="slot-empty slot-file">
            <ImagePlus />
            <span>{t("wiz.heicReady")}</span>
            <span className="muted small" dir="ltr">{file.name}</span>
          </span>
        ) : (
          <span className="slot-empty">
            {large ? <Upload /> : <ImagePlus />}
            <span>{t("wiz.add")}</span>
          </span>
        )}
        <input type="file" accept={[...IMAGE_TYPES, ".heic", ".heif"].join(",")} hidden onChange={(e) => take(e.target.files)} />
      </label>
      <div className="slot-foot">
        <strong>{label}</strong>
        {TOUCH && !file && (
          <label className="link slot-camera">
            📷 {t("wiz.camera")}
            <input type="file" accept="image/*" capture="environment" hidden onChange={(e) => take(e.target.files)} />
          </label>
        )}
        {file && (
          <button type="button" className="link danger" onClick={() => onFile(undefined)}>
            {t("wiz.remove")}
          </button>
        )}
      </div>
      {tip && !file && <p className="slot-tip">{tip}</p>}
    </div>
  );
}

export default function AnalyzeWizard({ options, onOptions, samples, currencies, defaultCurrency, busy, onGenerate }: Props) {
  const { t } = useI18n();
  const [step, setStep] = useState(0);
  const [mode, setMode] = useState<SpaceMode | null>(null);
  const [slots, setSlots] = useState<Partial<Record<SlotId, File>>>({});
  const [wallFile, setWallFile] = useState<File | undefined>();
  const [hint, setHint] = useState<string | null>(null);
  const slideRefs = useRef<(HTMLDivElement | null)[]>([]);
  const rootRef = useRef<HTMLDivElement>(null);
  const firstStep = useRef(true);
  const [height, setHeight] = useState<number | undefined>();

  const set = (patch: Partial<AnalyzeOptions>) => onOptions((prev) => ({ ...prev, ...patch }));
  const currency = options.currency || defaultCurrency || "";
  const available = mode === "wall" ? WALL_WORK : ALL_WORK;

  const photos: RolePhoto[] =
    mode === "wall"
      ? wallFile
        ? [{ file: wallFile, role: "wall" }]
        : []
      : SLOTS.flatMap((s) => (slots[s.id] ? [{ file: slots[s.id]!, role: s.role }] : []));

  // The viewport follows the visible slide's height, so short and tall slides both fit snugly.
  useLayoutEffect(() => {
    const node = slideRefs.current[step];
    if (!node) return;
    const update = () => setHeight(node.offsetHeight);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, [step, mode]);

  // Slides differ in height. When a tall slide (the photo slots) gives way to a shorter one, the
  // page below moves up under the reader; bring the wizard's top back into view on every step.
  useEffect(() => {
    if (firstStep.current) {
      firstStep.current = false;
      return;
    }
    const node = rootRef.current;
    if (!node) return;
    const navbar = 80;
    const top = node.getBoundingClientRect().top;
    if (top < navbar || top > window.innerHeight * 0.6) scrollToTarget(node, -(navbar + 16));
  }, [step]);

  function choose(next: SpaceMode) {
    setMode(next);
    setHint(null);
    // Pre-tick everything that applies to this kind of space.
    set({ scope: withoutReplacements(next === "wall" ? WALL_WORK : ALL_WORK) });
    window.setTimeout(() => setStep(1), 280);
  }

  function goNext() {
    if (step === 0 && !mode) return setHint(t("wiz.needType"));
    if (step === 1 && !photos.length) return setHint(t("wiz.needPhoto"));
    setHint(null);
    setStep((s) => Math.min(2, s + 1));
  }

  // A single wall needs a wall photo: offer three at random, never the floor or ceiling shots.
  const [sampleRound, setSampleRound] = useState(0);
  const wallSamples = useMemo(() => {
    const pool = samples.filter((s) => !/-(floor|ceiling)\.jpg$/.test(s));
    return [...pool].sort(() => Math.random() - 0.5).slice(0, 3);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [samples, sampleRound]);

  // Only examples whose six photos are actually on the server are offered.
  const examples = ROOM_EXAMPLES.filter((id) => Object.values(exampleFiles(id)).every((f) => samples.includes(f)));

  async function fillExample(id: RoomExample) {
    const entries = await Promise.all(
      Object.entries(exampleFiles(id)).map(async ([slot, name]) => [slot, await loadSample(name)] as const),
    );
    setSlots(Object.fromEntries(entries));
    setHint(null);
  }

  // "Start a new analysis" clears everything; keep the old photos for a few seconds in case it was a mis-click.
  const [cleared, setCleared] = useState<{ step: number; mode: SpaceMode | null; slots: typeof slots; wallFile?: File } | null>(null);
  useEffect(() => {
    if (!cleared) return;
    const timer = window.setTimeout(() => setCleared(null), 8000);
    return () => clearTimeout(timer);
  }, [cleared]);

  function reset() {
    setCleared({ step, mode, slots, wallFile });
    setStep(0);
    setMode(null);
    setSlots({});
    setWallFile(undefined);
    setHint(null);
  }

  function undoReset() {
    if (!cleared) return;
    setMode(cleared.mode);
    setSlots(cleared.slots);
    setWallFile(cleared.wallFile);
    setStep(cleared.step);
    setCleared(null);
  }

  const steps = [t("wiz.step.space"), t("wiz.step.photos"), t("wiz.step.work")];
  const slideProps = (i: number) => ({
    ref: (el: HTMLDivElement | null) => (slideRefs.current[i] = el),
    className: `wizard-slide ${i === step ? "current" : i < step ? "is-before" : "is-after"}`,
    "aria-hidden": i !== step,
    ...(i !== step ? { inert: "" } : {}),
  });

  return (
    <div className="wizard no-print" ref={rootRef}>
      <ol className="wizard-steps">
        {steps.map((label, i) => (
          <li key={label} className={`${i < step ? "done" : ""} ${i === step ? "active" : ""}`}>
            <button type="button" disabled={i > step} onClick={() => setStep(i)}>
              <span className="wizard-dot">{i < step ? "✓" : i + 1}</span>
              <span>{label}</span>
            </button>
          </li>
        ))}
        <span className="wizard-progress" aria-hidden="true">
          <span style={{ "--p": step / (steps.length - 1) } as CSSProperties} />
        </span>
      </ol>

      <div className="wizard-viewport" style={{ height }}>
        <div className="wizard-track" style={{ "--step": step } as CSSProperties}>
          {/* 1. Room or wall */}
          <div {...slideProps(0)}>
            <div className="float-panel">
              <h3 className="wizard-title">{t("wiz.q")}</h3>
              <p className="muted wizard-sub">{t("wiz.qSub")}</p>
              <div className="mode-cards">
                {(
                  [
                    ["room", <RoomIcon key="r" />, t("wiz.room"), t("wiz.roomDesc")],
                    ["wall", <WallIcon key="w" />, t("wiz.wall"), t("wiz.wallDesc")],
                  ] as const
                ).map(([id, icon, title, desc]) => (
                  <button
                    key={id}
                    type="button"
                    className={`mode-card ${mode === id ? "selected" : ""}`}
                    aria-pressed={mode === id}
                    onClick={() => choose(id)}
                  >
                    <span className="mode-icon">{icon}</span>
                    <strong>{title}</strong>
                    <span className="muted">{desc}</span>
                    <span className="mode-check" aria-hidden="true">✓</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* 2. Photos and details */}
          <div {...slideProps(1)}>
            <div className="float-panel">
              <h3 className="wizard-title">{mode === "wall" ? t("wiz.photosWall") : t("wiz.photosRoom")}</h3>
              <p className="muted wizard-sub">{mode === "wall" ? t("wiz.photosWallSub") : t("wiz.photosRoomSub")}</p>

              {mode === "wall" ? (
                <div className="wall-upload">
                  <PhotoSlot large label={t("slot.wall")} file={wallFile} onFile={setWallFile} tip={t("slot.tip.single")} />
                  {wallSamples.length > 0 && (
                    <div className="samples">
                      <span className="muted">{t("upload.samples")}:</span>
                      {wallSamples.map((s) => (
                        <button key={s} type="button" className="pill" onClick={async () => setWallFile(await loadSample(s))}>
                          {s.replace(/\.jpg$/, "").replace(/-/g, " ")}
                        </button>
                      ))}
                      <button type="button" className="link small" onClick={() => setSampleRound((n) => n + 1)}>↻ {t("wiz.otherSamples")}</button>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div className="slot-grid">
                    {SLOTS.map((s) => (
                      <PhotoSlot
                        key={s.id}
                        label={s.n ? `${t("slot.wall")} ${s.n}` : t(`slot.${s.role}`)}
                        tip={t(`slot.tip.${s.role}`)}
                        file={slots[s.id]}
                        onFile={(f) => setSlots((prev) => ({ ...prev, [s.id]: f }))}
                      />
                    ))}
                  </div>
                  {examples.length > 0 && (
                    <div className="room-examples">
                      <span className="label">{t("wiz.examples")}</span>
                      <div className="room-example-list">
                        {examples.map((id) => (
                          <button key={id} type="button" className="room-example" onClick={() => fillExample(id)}>
                            <img src={`/samples/${id}-collage.jpg`} alt="" loading="lazy" />
                            <span>
                              <strong>{t(`wiz.example.${id}` as "wiz.example.bedroom")}</strong>
                              <span className="muted small">{t("wiz.examplePhotos")}</span>
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
              <p className="muted small furniture-tip">{t("wiz.furnitureTip")}</p>

              <div className="wizard-fields">
                <div className="measure-toggle" role="radiogroup" aria-label={t("wiz.measureQ")}>
                  {(
                    [
                      ["exact", t("wiz.haveMeasure"), t("wiz.haveMeasureDesc")],
                      ["estimate", t("wiz.noMeasure"), t("wiz.noMeasureDesc")],
                    ] as const
                  ).map(([id, title, desc]) => (
                    <button
                      key={id}
                      type="button"
                      role="radio"
                      aria-checked={options.measure === id}
                      className={options.measure === id ? "selected" : ""}
                      onClick={() => set({ measure: id })}
                    >
                      <strong>{title}</strong>
                      <span className="muted small">{desc}</span>
                    </button>
                  ))}
                </div>

                {options.measure === "exact" ? (
                  <>
                    <fieldset className="room-size">
                      <legend>
                        {mode === "room" ? t("wiz.roomSize") : t("wiz.wallSize")} <span className="muted">({t("wiz.optional")})</span>
                      </legend>
                      <div className="field-row">
                        {mode === "room" ? (
                          <>
                            <MetreField label={t("wiz.length")} value={options.roomLength} onChange={(v) => set({ roomLength: v })} />
                            <span className="times" aria-hidden="true">×</span>
                            <MetreField label={t("wiz.width")} value={options.roomWidth} onChange={(v) => set({ roomWidth: v })} />
                          </>
                        ) : (
                          <MetreField label={t("wiz.wallWidth")} value={options.wallWidth} max={50} onChange={(v) => set({ wallWidth: v })} />
                        )}
                        <span className="times" aria-hidden="true">×</span>
                        <MetreField label={t("wiz.ceiling")} value={options.ceilingHeight} min={1.5} max={10} onChange={(v) => set({ ceilingHeight: v })} />
                      </div>
                      <p className="muted small">{mode === "room" ? `${t("wiz.roomSizeHint")} ${t("wiz.ceilingHint")}` : t("wiz.wallSizeHint")}</p>
                      {mode === "room" && (
                        <details className="irregular" open={Boolean(options.roomArea || options.roomPerimeter)}>
                          <summary>{t("wiz.irregular")}</summary>
                          <div className="field-row">
                            <MetreField label={t("wiz.floorArea")} value={options.roomArea} min={1} max={2000} onChange={(v) => set({ roomArea: v })} />
                            <MetreField label={t("wiz.wallLength")} value={options.roomPerimeter} min={2} max={400} onChange={(v) => set({ roomPerimeter: v })} />
                          </div>
                          <p className="muted small">{t("wiz.irregularHint")}</p>
                        </details>
                      )}
                    </fieldset>
                    <div className="field-row">
                      <label className="field">
                        <span>{mode === "room" ? t("wiz.doorWall") : t("upload.scale")}</span>
                        {mode === "room" ? (
                          <input type="number" min="0.5" max="5" step="0.05" value={options.scaleHeight ?? ""}
                            onChange={(e) => set({ scaleElement: "door", scaleHeight: num(e.target.value) })} />
                        ) : (
                          <select value={options.scaleElement} onChange={(e) => set({ scaleElement: e.target.value as AnalyzeOptions["scaleElement"] })}>
                            <option value="">{t("upload.none")}</option>
                            <option value="door">{t("upload.door")}</option>
                            <option value="window">{t("upload.window")}</option>
                          </select>
                        )}
                      </label>
                      {mode === "wall" && options.scaleElement && (
                        <MetreField label={t("upload.height")} value={options.scaleHeight} min={0.1} max={20} onChange={(v) => set({ scaleHeight: v })} />
                      )}
                    </div>
                  </>
                ) : (
                  <div className="estimate-box">
                    {mode === "room" && (
                      <label className="field">
                        <span>{t("wiz.roomType")}</span>
                        <select value={options.roomType} onChange={(e) => set({ roomType: e.target.value as RoomType })}>
                          {(Object.keys(ROOM_TYPES) as RoomType[]).map((r) => (
                            <option key={r} value={r}>
                              {/* Isolate the size so it stays "5 × 6 m" inside Arabic and Urdu text. */}
                              {`${t(`room.${r}`)} · ⁦${ROOM_TYPES[r][0]} × ${ROOM_TYPES[r][1]} m⁩`}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <p className="muted small">{mode === "room" ? t("wiz.estimateRoom") : t("wiz.estimateWall")}</p>
                    <p className="small phone-tip">{t("wiz.phoneTip")}</p>
                  </div>
                )}
                <div className="field-row">
                  <label className="field">
                    <span>{t("upload.finish")}</span>
                    <select value={options.finish} onChange={(e) => set({ finish: e.target.value as Finish })}>
                      <option value="basic">{t("upload.basic")}</option>
                      <option value="standard">{t("upload.standard")}</option>
                      <option value="premium">{t("upload.premium")}</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>{t("upload.currency")}</span>
                    <select value={currency} onChange={(e) => set({ currency: e.target.value })}>
                      {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </label>
                  <label className="field">
                    <span>{t("upload.reportLang")}</span>
                    <select value={options.language} onChange={(e) => set({ language: e.target.value as Language })}>
                      <option value="en">English</option>
                      <option value="ar">العربية</option>
                      <option value="ur">اردو</option>
                    </select>
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* 3. Work to price */}
          <div {...slideProps(2)}>
            <div className="float-panel">
              <ScopePicker value={options.scope} available={available} onChange={(update) => onOptions((prev) => ({ ...prev, scope: update(prev.scope) }))} />
              <div className="wizard-summary">
                <span className="label">{t("wiz.summary")}</span>
                <span className="summary-chip">{mode === "wall" ? t("wiz.wall") : t("wiz.room")}</span>
                <span className="summary-chip">{t("wiz.photosCount").replace("{n}", String(photos.length))}</span>
                <span className="summary-chip" dir="ltr">{currency} · {t(`upload.${options.finish}`)}</span>
                {options.measure === "estimate" ? (
                  <span className="summary-chip estimate">
                    {t("wiz.estimatedChip")}{mode === "room" && ` · ${t(`room.${options.roomType}`)}`}
                  </span>
                ) : mode === "room" && options.roomLength && options.roomWidth ? (
                  <span className="summary-chip" dir="ltr">
                    {options.roomLength} × {options.roomWidth}{options.ceilingHeight ? ` × ${options.ceilingHeight}` : ""} m
                  </span>
                ) : mode === "wall" && options.wallWidth && options.ceilingHeight ? (
                  <span className="summary-chip" dir="ltr">{options.wallWidth} × {options.ceilingHeight} m</span>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      {hint && <p className="wizard-hint" role="alert">{hint}</p>}
      {cleared && (
        <p className="wizard-undo" role="status">
          {t("wiz.cleared")} <button type="button" className="link" onClick={undoReset}>{t("wiz.undo")}</button>
        </p>
      )}

      <div className="wizard-nav">
        {step > 0 ? (
          <button type="button" className="btn ghost" onClick={() => { setHint(null); setStep((s) => s - 1); }}>
            <span className="arrow back" aria-hidden="true">→</span> {t("wiz.back")}
          </button>
        ) : <span />}
        {step < 2 ? (
          <button type="button" className="btn primary" onClick={goNext}>
            {t("wiz.next")} <span className="arrow" aria-hidden="true">→</span>
          </button>
        ) : (
          <div className="wizard-final">
            <button type="button" className="link" onClick={reset}>{t("wiz.new")}</button>
            <button
              type="button"
              className="btn primary"
              disabled={busy || !photos.length || !options.scope.length}
              onClick={() => mode && onGenerate(mode, photos)}
            >
              {busy ? t("upload.analysing") : t("wiz.generate")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
