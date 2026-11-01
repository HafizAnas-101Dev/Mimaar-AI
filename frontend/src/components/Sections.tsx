import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { CountUp, gsap, Magnetic, prefersReducedMotion, Reveal, ScrollTrigger, scrollToTarget, SplitWords, spotlight, useGsap } from "../motion";
import { ArrowDown, Coins, Doc, Globe, History, Layers, Ruler, Scan, Search, Shield, Sliders, Upload } from "./Icons";

/* Where things are in backend/samples/villa-room-defects.jpg, as % of the image. */
const GEOMETRY = {
  ceiling: { left: 0, top: 0, width: 100, height: 11 },
  wall: { left: 13.3, top: 11.3, width: 73.4, height: 58.7 },
  floor: { left: 0, top: 70, width: 100, height: 30 },
  door: { left: 20.8, top: 31.3, width: 12.5, height: 38.7 },
  window: { left: 54.2, top: 25, width: 23.3, height: 22.5 },
  fixture: { left: 46.7, top: 3, width: 6.7, height: 4.6 },
  crack: { left: 40.5, top: 15, width: 6, height: 31 },
  damp: { left: 80, top: 47.5, width: 10, height: 20 },
} as const;
const pos = (k: keyof typeof GEOMETRY) => {
  const g = GEOMETRY[k];
  return { left: `${g.left}%`, top: `${g.top}%`, width: `${g.width}%`, height: `${g.height}%` };
};

export function Hero({ sample }: { sample: string | null }) {
  const { t, el, lang } = useI18n();
  const ref = useRef<HTMLElement>(null);

  useGsap(
    ref,
    () => {
      // Hero sinks and fades as you scroll away; the scan card tips back.
      const scrub = { trigger: ref.current, start: "top top", end: "bottom top", scrub: true };
      gsap.to(".hero-copy", { yPercent: 18, opacity: 0, ease: "none", scrollTrigger: scrub });
      gsap.to(".hero-visual", { yPercent: 12, opacity: 0.15, ease: "none", scrollTrigger: scrub });
      gsap.from([".badge", ".lead", ".hero-ctas", ".hero-stats"], {
        y: 30, opacity: 0, duration: 1, ease: "power3.out", stagger: 0.1, delay: 0.35,
      });
      gsap.from(".hero-visual", { y: 60, opacity: 0, scale: 0.92, duration: 1.4, ease: "expo.out", delay: 0.3 });

      // Looping CSS animations only run while the hero is on screen.
      const visible = ScrollTrigger.create({
        trigger: ref.current,
        start: "top bottom",
        end: "bottom top",
        toggleClass: { targets: ref.current, className: "in-view" },
      });

      // 3D tilt toward the cursor.
      const tilt = ref.current!.querySelector(".tilt") as HTMLElement;
      const rx = gsap.quickTo(tilt, "rotationX", { duration: 0.8, ease: "power3" });
      const ry = gsap.quickTo(tilt, "rotationY", { duration: 0.8, ease: "power3" });
      const move = (e: MouseEvent) => {
        if (!visible.isActive || window.scrollY > window.innerHeight * 0.6) return;
        rx((0.5 - e.clientY / window.innerHeight) * 10);
        ry((e.clientX / window.innerWidth - 0.5) * 14);
      };
      window.addEventListener("mousemove", move);
      return () => window.removeEventListener("mousemove", move);
    },
    [lang],
  );

  return (
    <header className="hero" id="top" ref={ref}>
      <div className="hero-bg" aria-hidden="true">
        <span className="glow g1" />
        <span className="glow g2" />
        <span className="grid-lines" />
      </div>
      <div className="container hero-inner">
        <div className="hero-copy">
          <span className="badge"><span className="dot" /> {t("hero.badge")}</span>
          <h1 className="display" key={lang}>
            <SplitWords text={t("hero.title1")} onScroll={false} delay={0.05} />{" "}
            <SplitWords text={t("hero.title2")} className="gradient-text" onScroll={false} delay={0.25} />{" "}
            <SplitWords text={t("hero.title3")} onScroll={false} delay={0.45} />
          </h1>
          <p className="lead">{t("hero.sub")}</p>
          <div className="hero-ctas">
            <Magnetic><a href="#analyze" className="btn primary large">{t("hero.cta")}</a></Magnetic>
            <Magnetic><a href="#how" className="btn glass large">{t("hero.cta2")} <ArrowDown /></a></Magnetic>
          </div>
          <dl className="hero-stats">
            <div><dt dir="ltr">&lt; 1 min</dt><dd>{t("hero.stat1")}</dd></div>
            <div><dt>3</dt><dd>{t("hero.stat2")}</dd></div>
            <div><dt dir="ltr">SAR · PKR · USD</dt><dd>{t("hero.stat3")}</dd></div>
          </dl>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="tilt">
            <div className="scan-card">
              {sample ? <img src={sample} alt="" /> : <div className="scan-placeholder" />}
              {(["wall", "door", "window", "crack"] as const).map((k) => (
                <span key={k} className={`box b-${k}`} style={pos(k)}><i>{el(k)}</i></span>
              ))}
              <span className="scanline" />
              <div className="scan-status"><span className="dot" /> {t("hero.scanning")}</div>
            </div>
            <div className="float-chip c1" dir="ltr"><Ruler /> 18.3 m²</div>
            <div className="float-chip c2" dir="ltr"><Coins /> 3,008 – 7,646 SAR</div>
          </div>
        </div>
      </div>
      <a href="#how" className="scroll-cue" aria-label={t("hero.cta2")}><span /></a>
    </header>
  );
}

const STAGE_ICONS = [<Upload key="u" />, <Scan key="s" />, <Ruler key="r" />, <Coins key="c" />, <Doc key="d" />];

export function Trace({ sample }: { sample: string | null }) {
  const { t, el, lang } = useI18n();
  const ref = useRef<HTMLElement>(null);
  const trigger = useRef<ScrollTrigger | null>(null);
  const [stage, setStage] = useState(0);
  const count = STAGE_ICONS.length;

  useGsap(
    ref,
    () => {
      const fill = ref.current!.querySelector(".trace-line-fill");
      trigger.current = ScrollTrigger.create({
        trigger: ".trace-pin",
        start: "top top",
        end: () => `+=${window.innerHeight * count * 0.45}`,
        pin: true,
        anticipatePin: 1,
        onUpdate: (self) => {
          gsap.set(fill, { scaleX: self.progress });
          const next = Math.min(count - 1, Math.floor(self.progress * count));
          setStage((s) => (s === next ? s : next));
        },
      });
      return () => {
        trigger.current = null;
      };
    },
    [lang],
  );

  function jump(i: number) {
    const st = trigger.current;
    if (!st) return setStage(i);
    scrollToTarget(st.start + ((i + 0.5) / count) * (st.end - st.start), 0);
  }

  const titles = [t("trace.0.title"), t("how.1.title"), t("how.2.title"), t("how.3.title"), t("how.4.title")];
  const bodies = [t("trace.0.body"), t("how.1.body"), t("how.2.body"), t("how.3.body"), t("how.4.body")];
  const reached = Array.from({ length: stage + 1 }, (_, i) => `r${i}`).join(" ");

  return (
    <section className="trace-section" id="how" ref={ref}>
      <div className="trace-pin">
        <div className="container">
          <div className="section-head compact">
            <span className="kicker">{t("trace.kicker")}</span>
            <SplitWords as="h2" text={t("trace.title")} className="display" />
            <p className="section-sub">{t("trace.sub")}</p>
          </div>

          <div className="trace-steps">
            <div className="trace-line"><span className="trace-line-fill" /></div>
            {STAGE_ICONS.map((icon, i) => (
              <button
                key={i}
                type="button"
                className={`trace-node ${i < stage ? "done" : ""} ${i === stage ? "active" : ""}`}
                onClick={() => jump(i)}
              >
                <span className="trace-icon">{icon}</span>
                <span className="trace-label">{titles[i]}</span>
              </button>
            ))}
          </div>

          <div className="trace-body">
            <div className="trace-card" key={`${stage}-${lang}`}>
              <span className="trace-index">{t("trace.step")} 0{stage + 1} / 0{count}</span>
              <h3>{titles[stage]}</h3>
              <p>{bodies[stage]}</p>
            </div>

            <div className={`trace-visual s${stage} ${reached}`} aria-hidden="true">
              {sample ? <img src={sample} alt="" /> : <div className="scan-placeholder" />}
              <span className="dim" style={{ left: `calc(${GEOMETRY.door.left}% - 18px)`, top: pos("door").top, height: pos("door").height }}>
                <b>2.1 m</b>
              </span>
              {(Object.keys(GEOMETRY) as (keyof typeof GEOMETRY)[]).map((k, i) => (
                <span key={k} className={`mask m-${k}`} style={{ ...pos(k), transitionDelay: `${i * 70}ms` }}>
                  <i>{el(k)}</i>
                </span>
              ))}
              <span className="trace-scan" />
              {(
                [
                  ["measure", "wall", "18.2 m²", "60%", "56%"],
                  ["measure", "floor", "13.3 m²", "38%", "84%"],
                  ["measure", "window", "2.6 m²", "57%", "18%"],
                  ["price", "wall", "638 – 1,276 SAR", "4%", "15%"],
                  ["price", "floor", "1,065 – 2,396 SAR", "56%", "74%"],
                  ["price", "door", "600 – 1,800 SAR", "23%", "73%"],
                ] as const
              ).map(([kind, k, value, left, top]) => (
                <span key={`${kind}-${k}`} className={kind} style={{ left, top }}>
                  <bdi>{el(k)}</bdi> · <bdi dir="ltr">{value}</bdi>
                </span>
              ))}
              <div className="mini-report">
                <span className="label">{t("results.cost")}</span>
                <strong dir="ltr">3,008 – 7,646 <small>SAR</small></strong>
                <ul>
                  <li><span className="el-dot el-wall" />{el("wall")} <em dir="ltr">18.2 m²</em></li>
                  <li><span className="el-dot el-floor" />{el("floor")} <em dir="ltr">13.3 m²</em></li>
                  <li><span className="sev medium">{t("sev.medium")}</span> {el("damp")}</li>
                  <li><span className="sev low">{t("sev.low")}</span> {el("crack")}</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

const AUDIENCE = [
  { icon: <Ruler key="r" />, key: "1" },
  { icon: <Doc key="d" />, key: "2" },
  { icon: <Search key="s" />, key: "3" },
] as const;

export function Audience() {
  const { t } = useI18n();
  return (
    <section className="section audience-section" id="audience">
      <div className="container">
        <div className="section-head">
          <span className="kicker">{t("aud.kicker")}</span>
          <SplitWords as="h2" text={t("aud.title")} className="display" />
        </div>
        <div className="audience-grid">
          {AUDIENCE.map((a, i) => (
            <Reveal key={a.key} delay={i * 110} className="persona card glass-card">
              <span className="icon-tile">{a.icon}</span>
              <h3>{t(`aud.${a.key}.role` as "aud.1.role")}</h3>
              <div className="persona-row pain">
                <span className="label">{t("aud.pain")}</span>
                <p>{t(`aud.${a.key}.pain` as "aud.1.pain")}</p>
              </div>
              <div className="persona-row gain">
                <span className="label">{t("aud.gain")}</span>
                <p>{t(`aud.${a.key}.gain` as "aud.1.gain")}</p>
              </div>
            </Reveal>
          ))}
        </div>
        <Reveal className="market-note"><span className="dot" /> {t("aud.market")}</Reveal>
      </div>
    </section>
  );
}

export function Story() {
  const { t, lang } = useI18n();
  const ref = useRef<HTMLElement>(null);
  useGsap(
    ref,
    () => {
      gsap.fromTo(
        ".story-line-fill",
        { scaleX: 0 },
        { scaleX: 1, ease: "none", scrollTrigger: { trigger: ".story-steps", start: "top 80%", end: "bottom 55%", scrub: true } },
      );
    },
    [lang],
  );
  const steps = ["1", "2", "3", "4"] as const;
  return (
    <section className="section story-section" ref={ref}>
      <div className="container">
        <div className="section-head">
          <span className="kicker">{t("story.kicker")}</span>
          <SplitWords as="h2" text={t("story.title")} className="display" />
        </div>
        <ol className="story-steps">
          <li className="story-line" aria-hidden="true"><span className="story-line-fill" /></li>
          {steps.map((k, i) => (
            <Reveal as="li" key={k} delay={i * 140} className={`story-step ${k === "2" ? "before" : k === "3" ? "with" : ""}`}>
              <span className="story-num">0{i + 1}</span>
              <span className="label">{t(`story.${k}.label` as "story.1.label")}</span>
              <p>{t(`story.${k}.body` as "story.1.body")}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Stats() {
  const { t } = useI18n();
  const items = [
    { value: 6, label: t("stats.1") },
    { value: 3, label: t("stats.2") },
    { value: 3, label: t("stats.3") },
    { value: 6, label: t("stats.4") },
  ];
  return (
    <section className="section stats-section">
      <div className="container">
        <div className="section-head">
          <span className="kicker">{t("stats.kicker")}</span>
          <SplitWords as="h2" text={t("stats.title")} className="display" />
        </div>
        <div className="stats-grid">
          {items.map((item, i) => (
            <Reveal key={i} delay={i * 90} className="stat card glass-card">
              <span className="stat-value"><CountUp value={item.value} format={(n) => Math.round(n).toString()} /></span>
              <span className="stat-label">{item.label}</span>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

const FEATURES = [
  { icon: <Shield />, key: "1" },
  { icon: <Search />, key: "2" },
  { icon: <Globe />, key: "3" },
  { icon: <Layers />, key: "4" },
  { icon: <Sliders />, key: "5" },
  { icon: <History />, key: "6" },
] as const;

export function Features() {
  const { t, lang } = useI18n();
  const ref = useRef<HTMLElement>(null);

  useGsap(
    ref,
    () => {
      // Explicit end values: never derive the target from the card's current (possibly mid-animation) transform.
      gsap.fromTo(
        ".feature",
        { y: 90, rotateX: -28, opacity: 0, transformPerspective: 900, transformOrigin: "50% 100%" },
        {
          y: 0,
          rotateX: 0,
          opacity: 1,
          duration: 1.1,
          ease: "power3.out",
          stagger: { each: 0.1, grid: "auto", from: "start" },
          clearProps: "transform,opacity",
          scrollTrigger: { trigger: ".feature-grid", start: "top 82%" },
        },
      );
    },
    [lang],
  );

  return (
    <section className="section" id="features" ref={ref}>
      <div className="container">
        <div className="section-head">
          <span className="kicker">{t("features.kicker")}</span>
          <SplitWords as="h2" text={t("features.title")} className="display" />
        </div>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <article key={f.key} className="feature card glass-card spot" onMouseMove={spotlight}>
              <span className="icon-tile">{f.icon}</span>
              <h3>{t(`features.${f.key}.title` as "features.1.title")}</h3>
              <p>{t(`features.${f.key}.body` as "features.1.body")}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Cta() {
  const { t, lang } = useI18n();
  const ref = useRef<HTMLElement>(null);
  useGsap(
    ref,
    () => {
      gsap.fromTo(
        ".cta-card",
        { scale: 0.86, y: 80, borderRadius: 60 },
        { scale: 1, y: 0, borderRadius: 28, ease: "none", scrollTrigger: { trigger: ref.current, start: "top bottom", end: "center center", scrub: 1 } },
      );
    },
    [lang],
  );
  return (
    <section className="section cta-section no-print" ref={ref}>
      <div className="container">
        <div className="cta-card spot" onMouseMove={spotlight}>
          <SplitWords as="h2" text={t("cta.title")} className="display" />
          <p>{t("cta.sub")}</p>
          <Magnetic><a href="#analyze" className="btn primary large">{t("cta.button")}</a></Magnetic>
        </div>
      </div>
    </section>
  );
}

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="footer no-print">
      <div className="container">
        <span className="footer-brand"><img src="/brand/mimaar-logo-512.png" alt="" width="40" height="40" /><span className="brand-small display">Mimaar AI</span></span>
        <p>{t("footer.text")}</p>
      </div>
    </footer>
  );
}

/** Background glows that drift at different speeds while scrolling. */
export function useParallax(deps: unknown[]) {
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>("[data-speed]").forEach((node) => {
        const speed = Number(node.dataset.speed);
        gsap.to(node, {
          yPercent: speed * -100,
          ease: "none",
          scrollTrigger: { trigger: node.parentElement, start: "top bottom", end: "bottom top", scrub: true },
        });
      });
    });
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
