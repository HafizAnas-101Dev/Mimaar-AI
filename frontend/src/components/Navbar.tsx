import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import type { Language, WriterStatus } from "../types";

const LANGS: { code: Language; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "ar", label: "عربي" },
  { code: "ur", label: "اردو" },
];

export default function Navbar({ onPrices, writer, reasoner }: { onPrices: () => void; writer: WriterStatus; reasoner: string }) {
  const { t, lang, setLang } = useI18n();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav className={`navbar no-print ${scrolled ? "scrolled" : ""}`}>
      <div className="container nav-inner">
        <a href="#top" className="brand">
          <img className="brand-mark" src="/brand/mimaar-logo-512.png" alt="" width="44" height="44" />
          <span>Mimaar <b>AI</b></span>
        </a>
        <div className="nav-links">
          <a href="#how">{t("nav.how")}</a>
          <a href="#analyze">{t("nav.analyze")}</a>
          <a href="#features">{t("nav.features")}</a>
          <a href="#history">{t("nav.history")}</a>
        </div>
        <div className="nav-actions">
          {writer !== "off" && writer !== "api" && (
            <span className={`writer-status ${writer}`} title={`${reasoner}: ${t(`status.${writer}`)}`} role="status">
              <span className="writer-dot" aria-hidden="true" />
              <span className="writer-label">{t(`status.${writer}`)}</span>
            </span>
          )}
          <button type="button" className="btn ghost small" onClick={onPrices}>{t("nav.prices")}</button>
          <div className="lang-switch" role="group" aria-label="Language">
            {LANGS.map((l) => (
              <button
                key={l.code}
                type="button"
                className={lang === l.code ? "active" : ""}
                aria-pressed={lang === l.code}
                onClick={() => setLang(l.code)}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </nav>
  );
}
