import { useEffect, useState } from "react";
import { useI18n } from "../i18n";

const STAGES = ["stage.perceive", "stage.measure", "stage.price", "stage.report"] as const;

export default function StageProgress() {
  const { t } = useI18n();
  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setActive((a) => Math.min(a + 1, STAGES.length - 1)), 700);
    return () => clearInterval(id);
  }, []);

  return (
    <ol className="stages no-print" aria-live="polite">
      {STAGES.map((s, i) => (
        <li key={s} className={i < active ? "done" : i === active ? "active" : ""}>
          <span className="stage-dot">{i < active ? "✓" : i + 1}</span>
          {t(s)}
        </li>
      ))}
    </ol>
  );
}
