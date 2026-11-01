import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  Fragment,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type DependencyList,
  type ElementType,
  type ReactNode,
  type RefObject,
} from "react";

gsap.registerPlugin(ScrollTrigger);

export { gsap, ScrollTrigger };

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * Scrolling stays native: wheel and touch input reach the page with no smoothing delay.
 * Smooth scrolling is limited to in-page jumps (anchor links, "show results").
 */
export function scrollToTarget(target: HTMLElement | number, offset = -80) {
  const top = typeof target === "number" ? target : target.getBoundingClientRect().top + window.scrollY + offset;
  window.scrollTo({ top, behavior: prefersReducedMotion() ? "auto" : "smooth" });
}

/** Runs GSAP code scoped to a container and reverts it on cleanup or when deps change. */
export function useGsap(scope: RefObject<HTMLElement>, setup: (self: gsap.Context) => void, deps: DependencyList = []) {
  useLayoutEffect(() => {
    if (!scope.current || prefersReducedMotion()) return;
    const ctx = gsap.context(setup, scope);
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/** Headline whose words rise out of a mask one by one when it scrolls into view. */
export function SplitWords({
  text,
  as: Tag = "span",
  className = "",
  delay = 0,
  onScroll = true,
}: {
  text: string;
  as?: ElementType;
  className?: string;
  delay?: number;
  onScroll?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  useGsap(
    ref,
    () => {
      gsap.from(".word-inner", {
        yPercent: 115,
        rotate: 4,
        opacity: 0,
        duration: 1.05,
        ease: "power4.out",
        stagger: 0.06,
        delay,
        clearProps: "transform,opacity",
        scrollTrigger: onScroll ? { trigger: ref.current, start: "top 88%" } : undefined,
      });
    },
    [text],
  );
  return (
    <Tag ref={ref} className={`split ${className}`} aria-label={text}>
      {text.split(" ").map((word, i, words) => (
        <Fragment key={`${word}-${i}`}>
          <span className="word" aria-hidden="true">
            <span className="word-inner">{word}</span>
          </span>
          {i < words.length - 1 ? " " : null}
        </Fragment>
      ))}
    </Tag>
  );
}

/** Fades and slides children in when they scroll into view. */
export function Reveal({
  children,
  delay = 0,
  as: Tag = "div",
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  as?: ElementType;
  className?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (!("IntersectionObserver" in window) || prefersReducedMotion()) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag ref={ref} className={`reveal ${visible ? "visible" : ""} ${className}`} style={{ "--delay": `${delay}ms` } as CSSProperties}>
      {children}
    </Tag>
  );
}

/** Animates a number from 0 to `value` once it is on screen. */
export function CountUp({ value, duration = 1400, format }: { value: number; duration?: number; format: (n: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setShown(value);
      return;
    }
    let frame = 0;
    const run = () => {
      const start = performance.now();
      const tick = (now: number) => {
        // The first frame's timestamp can precede `start`; clamp so the count never dips below zero.
        const p = Math.max(0, Math.min(1, (now - start) / duration));
        setShown(value * (1 - Math.pow(1 - p, 4)));
        if (p < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };
    const node = ref.current;
    if (!node || !("IntersectionObserver" in window)) {
      run();
      return () => cancelAnimationFrame(frame);
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        observer.disconnect();
        run();
      }
    });
    observer.observe(node);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [value, duration]);

  return <span ref={ref}>{format(shown)}</span>;
}

/** Thin bar at the top of the page that tracks scroll position. */
export function ScrollProgress() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const update = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      if (ref.current) ref.current.style.transform = `scaleX(${max > 0 ? window.scrollY / max : 0})`;
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);
  return <div ref={ref} className="scroll-progress" aria-hidden="true" />;
}

/** Wrapper whose child leans toward the cursor. */
export function Magnetic({ children, strength = 0.3 }: { children: ReactNode; strength?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node || prefersReducedMotion() || window.matchMedia("(hover: none)").matches) return;
    const xTo = gsap.quickTo(node, "x", { duration: 0.6, ease: "elastic.out(1, 0.4)" });
    const yTo = gsap.quickTo(node, "y", { duration: 0.6, ease: "elastic.out(1, 0.4)" });
    const move = (e: MouseEvent) => {
      const r = node.getBoundingClientRect();
      xTo((e.clientX - (r.left + r.width / 2)) * strength);
      yTo((e.clientY - (r.top + r.height / 2)) * strength);
    };
    const leave = () => {
      xTo(0);
      yTo(0);
    };
    node.addEventListener("mousemove", move);
    node.addEventListener("mouseleave", leave);
    return () => {
      node.removeEventListener("mousemove", move);
      node.removeEventListener("mouseleave", leave);
    };
  }, [strength]);
  return <span ref={ref} className="magnetic">{children}</span>;
}

/** Sets --mx/--my on the card under the cursor so CSS can draw a spotlight. */
export function spotlight(e: React.MouseEvent<HTMLElement>) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  el.style.setProperty("--mx", `${e.clientX - r.left}px`);
  el.style.setProperty("--my", `${e.clientY - r.top}px`);
}

/** Infinite strip that scrolls at a steady pace. */
export function Marquee({ items, rtl }: { items: string[]; rtl: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useGsap(
    ref,
    () => {
      const track = ref.current!.querySelector(".marquee-track") as HTMLElement;
      const loop = gsap.fromTo(
        track,
        { xPercent: rtl ? -50 : 0 },
        { xPercent: rtl ? 0 : -50, duration: 38, ease: "none", repeat: -1 },
      );
      // Constant speed regardless of scrolling; it only pauses while off screen.
      ScrollTrigger.create({
        trigger: ref.current,
        start: "top bottom",
        end: "bottom top",
        onToggle: (self) => (self.isActive ? loop.resume() : loop.pause()),
      });
    },
    [items.join("|"), rtl],
  );
  // Each half of the track must be wider than the screen, or a gap shows as it loops.
  const row = [...items, ...items].map((item, i) => (
    <span key={i} className="marquee-item">
      {item}
      <span className="marquee-sep" aria-hidden="true">✦</span>
    </span>
  ));
  return (
    // Always laid out left-to-right; RTL only reverses the direction of travel.
    <div ref={ref} className="marquee" dir="ltr" aria-hidden="true">
      <div className="marquee-track">
        {row}
        {row}
      </div>
    </div>
  );
}
