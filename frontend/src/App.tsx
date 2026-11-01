import { useCallback, useEffect, useRef, useState } from "react";
import { analyze, changeLanguage, editResult, finishReport, getHealth, getHistory, getPrices, listHistory, listSamples } from "./api";
import { useI18n } from "./i18n";
import { Marquee, Reveal, ScrollProgress, ScrollTrigger, scrollToTarget, SplitWords } from "./motion";
import { isRoom, type AnalysisResult, type Edits, type Language, type ReportDefect, type WriterStatus, type HistoryEntry, type PriceTable, type Result, type RolePhoto, type SpaceMode } from "./types";
import Navbar from "./components/Navbar";
import { Audience, Cta, Features, Footer, Hero, Stats, Story, Trace, useParallax } from "./components/Sections";
import AnalyzeWizard, { DEFAULT_SCOPE, type AnalyzeOptions } from "./components/AnalyzeWizard";
import StageProgress from "./components/StageProgress";
import OverlayViewer from "./components/OverlayViewer";
import ReportView from "./components/ReportView";
import HistoryPanel from "./components/HistoryPanel";
import PriceEditor from "./components/PriceEditor";
import PrintReport from "./components/PrintReport";

// Choices worth keeping between visits; sizes are per room, so they are not remembered.
const REMEMBERED = ["currency", "finish", "measure", "roomType", "scaleHeight"] as const;
const OPTIONS_KEY = "mimaar.options";

function loadRemembered(): Partial<AnalyzeOptions> {
  try {
    const saved = JSON.parse(localStorage.getItem(OPTIONS_KEY) || "{}");
    return Object.fromEntries(REMEMBERED.filter((k) => k in saved).map((k) => [k, saved[k]]));
  } catch {
    return {};
  }
}

function rememberOptions(options: AnalyzeOptions) {
  try {
    localStorage.setItem(OPTIONS_KEY, JSON.stringify(Object.fromEntries(REMEMBERED.map((k) => [k, options[k]]))));
  } catch {
    // Private windows can refuse storage; the app works without it.
  }
}

export default function App() {
  const { t, el, lang, dir } = useI18n();
  const [options, setOptions] = useState<AnalyzeOptions>(() => ({
    scaleElement: "door",
    scaleHeight: 2.1,
    roomLength: null,
    roomWidth: null,
    ceilingHeight: null,
    wallWidth: null,
    roomArea: null,
    roomPerimeter: null,
    measure: "exact",
    roomType: "bedroom",
    language: lang,
    currency: "",
    finish: "standard",
    scope: DEFAULT_SCOPE,
    ...loadRemembered(),
  }));
  useEffect(() => rememberOptions(options), [options]);
  const [result, setResult] = useState<Result | null>(null);
  const [photoIndex, setPhotoIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [prices, setPrices] = useState<PriceTable | null>(null);
  const [showPrices, setShowPrices] = useState(false);
  const [samples, setSamples] = useState<string[]>([]);
  const [reasoner, setReasoner] = useState("Muse");
  const finishing = useRef<string | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const refreshHistory = useCallback(() => listHistory().then(setHistory).catch(() => setHistory([])), []);

  useEffect(() => {
    refreshHistory();
    getPrices().then(setPrices).catch(() => setPrices(null));
    listSamples().then(setSamples).catch(() => setSamples([]));
  }, [refreshHistory]);

  // Whether the report writer is ready: shown in the navbar, checked every 15 seconds.
  const [writer, setWriter] = useState<WriterStatus>("off");
  useEffect(() => {
    const check = () =>
      getHealth()
        .then((h) => {
          setReasoner(h.reasoner);
          setWriter(h.writer);
        })
        .catch(() => setWriter("offline"));
    check();
    const timer = window.setInterval(check, 15000);
    return () => clearInterval(timer);
  }, []);

  // The report arrives at once, written by code; the Muse model's write-up replaces it when ready.
  const finish = useCallback(
    async (res: Result) => {
      if (res.reasoning !== "pending" || finishing.current === res.id) return;
      finishing.current = res.id;
      try {
        const done = await finishReport(res.id);
        setResult((cur) => (cur && cur.id === done.id ? done : cur));
        refreshHistory();
      } catch {
        setResult((cur) => (cur && cur.id === res.id ? { ...cur, reasoning: "failed" } : cur));
      } finally {
        if (finishing.current === res.id) finishing.current = null;
      }
    },
    [refreshHistory],
  );

  const run = useCallback(
    async (mode: SpaceMode, photos: RolePhoto[], runOptions: AnalyzeOptions, scroll = true) => {
      if (!photos.length) return;
      setBusy(true);
      setError(null);
      const currency = runOptions.currency || prices?.default_currency || "";
      // Without measurements, the backend fills the gaps with a standard door and typical sizes.
      const exact = runOptions.measure === "exact";
      const scaled = exact && runOptions.scaleElement && runOptions.scaleHeight;
      try {
        const roomSize = exact && mode === "room" && runOptions.roomLength && runOptions.roomWidth;
        const res = await analyze(mode, photos, {
          language: runOptions.language,
          currency,
          finish: runOptions.finish,
          scope: runOptions.scope.join(","),
          scale_element: scaled ? runOptions.scaleElement : "",
          scale_height_m: scaled ? String(runOptions.scaleHeight) : "",
          room_length_m: roomSize ? String(runOptions.roomLength) : "",
          room_width_m: roomSize ? String(runOptions.roomWidth) : "",
          ceiling_height_m: exact && runOptions.ceilingHeight ? String(runOptions.ceilingHeight) : "",
          wall_width_m: exact && mode === "wall" && runOptions.wallWidth ? String(runOptions.wallWidth) : "",
          room_floor_area_m2: exact && mode === "room" && runOptions.roomArea ? String(runOptions.roomArea) : "",
          room_perimeter_m: exact && mode === "room" && runOptions.roomPerimeter ? String(runOptions.roomPerimeter) : "",
          estimate: exact ? "" : "true",
          room_type: !exact && mode === "room" ? runOptions.roomType : "",
          defer_reasoning: "true",
        });
        setResult(res);
        setPhotoIndex(null);
        refreshHistory();
        finish(res);
        if (scroll) setTimeout(() => resultsRef.current && scrollToTarget(resultsRef.current), 120);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong.");
      } finally {
        setBusy(false);
      }
    },
    [prices, refreshHistory, finish],
  );

  // The language switch sets the language of the next report. An open report keeps its language
  // until the reader asks for it in the new one (no detection or measuring is redone).
  useEffect(() => {
    setOptions((prev) => ({ ...prev, language: lang }));
  }, [lang]);

  // ---- Corrections: every change is sent whole; the server recomputes from the original detections.
  const [highlight, setHighlight] = useState<{ photo: number | null; box: number[] } | null>(null);
  useEffect(() => setHighlight(null), [result?.id]);
  const edits: Edits = result?.edits ?? {};
  const plainEdits = (): Edits => ({ counts: edits.counts ?? {}, areas: edits.areas ?? {}, removed: edits.removed ?? {} });
  const hasEdits =
    Object.keys(edits.counts ?? {}).length > 0 ||
    Object.keys(edits.areas ?? {}).length > 0 ||
    Object.values(edits.removed ?? {}).some((kinds) => Object.values(kinds).some((boxes) => boxes.length > 0));

  async function applyEdits(next: Edits) {
    if (!result) return;
    try {
      setResult(await editResult(result.id, next));
      refreshHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply the correction.");
    }
  }

  function toggleBox(photoKey: string, type: string, box: number[]) {
    const next = plainEdits();
    const kinds = { ...(next.removed![photoKey] ?? {}) };
    const list = kinds[type] ?? [];
    const has = list.some((b) => b.every((v, i) => v === box[i]));
    kinds[type] = has ? list.filter((b) => !b.every((v, i) => v === box[i])) : [...list, box];
    next.removed = { ...next.removed, [photoKey]: kinds };
    // A count the customer typed in wins over taps, so a tap adjusts it by one as well.
    const typed = next.counts?.[type];
    if (typed != null) next.counts = { ...next.counts, [type]: Math.max(0, typed + (has ? 1 : -1)) };
    applyEdits(next);
  }

  function showDefect(d: ReportDefect) {
    const box = d.evidence?.boxes[0];
    if (!box) return;
    const photoIdx = room ? d.evidence?.photo ?? 0 : null;
    if (room) setPhotoIndex(photoIdx);
    setHighlight({ photo: photoIdx, box });
    setTimeout(() => resultsRef.current && scrollToTarget(resultsRef.current), 80);
  }

  async function retryWriting() {
    if (!result) return;
    setResult({ ...result, reasoning: "pending" });
    try {
      const done = await finishReport(result.id, true);
      setResult((cur) => (cur && cur.id === done.id ? done : cur));
    } catch {
      setResult((cur) => (cur && cur.id === result.id ? { ...cur, reasoning: "failed" } : cur));
    }
  }

  async function rewriteIn(language: Language) {
    if (!result) return;
    try {
      const res = await changeLanguage(result.id, language);
      setResult(res);
      refreshHistory();
      finish(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change the report language.");
    }
  }

  async function open(id: string) {
    try {
      const res = await getHistory(id);
      setResult(res);
      setPhotoIndex(null);
      finish(res);
      setError(null);
      setTimeout(() => resultsRef.current && scrollToTarget(resultsRef.current), 120);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open that analysis.");
    }
  }

  // Results, history and translations change the page height; pinned sections need fresh positions.
  useEffect(() => {
    let timer = 0;
    let lastHeight = document.body.scrollHeight;
    const observer = new ResizeObserver(() => {
      const height = document.body.scrollHeight;
      if (Math.abs(height - lastHeight) < 2) return;
      lastHeight = height;
      clearTimeout(timer);
      timer = window.setTimeout(() => ScrollTrigger.refresh(), 200);
    });
    observer.observe(document.body);
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, []);
  useParallax([lang]);

  const marquee = [
    ...["wall", "floor", "ceiling", "door", "window", "crack", "damp"].map(el),
    "SAR", "PKR", "USD", "English", "العربية", "اردو", "SAM 3", "Muse Glimmer",
  ];

  // "Floor", "Ceiling", "Wall 2"…; older results without roles fall back to "Photo n".
  const photoLabel = (photos: AnalysisResult[], i: number) => {
    const role = photos[i].role;
    if (!role) return `${t("results.photo")} ${i + 1}`;
    if (role !== "wall") return t(`slot.${role}`);
    const n = photos.slice(0, i + 1).filter((p) => p.role === "wall").length;
    const walls = photos.filter((p) => p.role === "wall").length;
    return walls > 1 ? `${t("slot.wall")} ${n}` : t("slot.wall");
  };

  const room = result && isRoom(result) ? result : null;
  const photo = result && !isRoom(result) ? result : room && photoIndex !== null ? room.photos[photoIndex] : null;
  const report = room && photoIndex === null ? room.report : photo?.report;
  const heroSample = samples.includes("villa-room-defects.jpg") ? "/api/samples/villa-room-defects.jpg" : null;

  return (
    <>
      <ScrollProgress />
      <Navbar onPrices={() => setShowPrices(true)} writer={writer} reasoner={reasoner} />
      <Hero sample={heroSample} />
      <Marquee items={marquee} rtl={dir === "rtl"} />
      <Audience />
      <Story />
      <Trace sample={heroSample} />
      <Stats />

      <section className="section analyze-section" id="analyze">
        <span className="glow g3" data-speed="0.4" aria-hidden="true" />
        <div className="container">
          <div className="section-head">
            <span className="kicker">{t("analyze.kicker")}</span>
            <SplitWords as="h2" text={t("analyze.title")} className="display" />
            <p className="section-sub">{t("analyze.sub")}</p>
          </div>

          <Reveal delay={100}>
            <AnalyzeWizard
              options={options}
              onOptions={setOptions}
              samples={samples}
              busy={busy}
              currencies={prices ? Object.keys(prices.tables) : []}
              defaultCurrency={prices?.default_currency}
              onGenerate={(mode, photos) => run(mode, photos, options)}
            />
          </Reveal>

          {busy && <StageProgress />}
          {error && <div className="alert error">{error}</div>}

          <div ref={resultsRef} className="results-anchor" />
          {result && !busy && (
            <div className="results-wrap" key={result.id}>
              {result.warnings.map((w) => (
                <div key={w} className="alert warning no-print">{w}</div>
              ))}
              {room && (
                <nav className="tabs no-print">
                  <button type="button" className={photoIndex === null ? "active" : ""} onClick={() => setPhotoIndex(null)}>
                    {t("results.combined")}
                  </button>
                  {room.photos.map((p, i) => (
                    <button key={p.id} type="button" className={photoIndex === i ? "active" : ""} onClick={() => setPhotoIndex(i)}>
                      {photoLabel(room.photos, i)}
                    </button>
                  ))}
                </nav>
              )}
              {room && photo?.role && photo.role !== "wall" && (
                <div className="alert info no-print">{t(`results.roleNote.${photo.role}`)}</div>
              )}
              <div className="results">
                {photo ? (
                  <OverlayViewer
                    key={photo.id}
                    result={photo}
                    removed={edits.removed?.[room ? String(photoIndex ?? 0) : "0"]}
                    onToggle={(type, box) => toggleBox(room ? String(photoIndex ?? 0) : "0", type, box)}
                    highlight={highlight && highlight.photo === (room ? photoIndex : null) ? highlight.box : null}
                  />
                ) : (
                  room && (
                    <div className="card thumbs">
                      {room.photos.map((p, i) => (
                        <button key={p.id} type="button" onClick={() => setPhotoIndex(i)}>
                          <img src={`data:image/png;base64,${p.image_png_base64}`} alt={photoLabel(room.photos, i)} />
                          <span>{photoLabel(room.photos, i)}</span>
                        </button>
                      ))}
                    </div>
                  )
                )}
                {report && (
                  <ReportView
                    report={report}
                    writing={report === result.report ? result.reasoning : undefined}
                    reasoner={reasoner}
                    onRewrite={report === result.report && report.language !== lang ? () => rewriteIn(lang) : undefined}
                    editing={
                      report === result.report
                        ? {
                            edited: hasEdits,
                            onCount: (type, count) => applyEdits({ ...plainEdits(), counts: { ...edits.counts, [type]: count } }),
                            onArea: (type, area) => applyEdits({ ...plainEdits(), areas: { ...edits.areas, [type]: area } }),
                            onReset: () => applyEdits({}),
                          }
                        : undefined
                    }
                    onShowDefect={showDefect}
                    onRetry={retryWriting}
                    // Measured on the sample photos: English is about twice as fast as Arabic/Urdu.
                    expectSeconds={(report.language === "en" ? 50 : 95) + (room ? 25 : 0)}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      <Features />

      <section className="section history-section" id="history">
        <div className="container">
          <HistoryPanel entries={history} activeId={result?.id} onOpen={open} onDeleted={refreshHistory} />
        </div>
      </section>

      <Cta />
      <Footer />

      {result && report && (
        <PrintReport
          id={photo && photoIndex !== null ? photo.id : result.id}
          mode={result.mode}
          report={report}
          photos={room && photoIndex === null ? room.photos : photo ? [photo] : []}
        />
      )}

      {showPrices && prices && (
        <PriceEditor table={prices} onSaved={setPrices} onClose={() => setShowPrices(false)} />
      )}
    </>
  );
}
