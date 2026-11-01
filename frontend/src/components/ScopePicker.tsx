import { useI18n } from "../i18n";
import { ALL_WORK, FINISHING_WORK, REPAIR_WORK, type WorkItem } from "../types";

interface Props {
  value: WorkItem[];
  /** Items the customer can choose from; defaults to all of them. */
  available?: readonly WorkItem[];
  /** Receives an updater so each click applies to the latest selection. */
  onChange: (update: (current: WorkItem[]) => WorkItem[]) => void;
}

/** Lets the customer choose which work goes into the cost estimate, before analysing. */
export default function ScopePicker({ value, available = ALL_WORK, onChange }: Props) {
  const { t } = useI18n();
  const selected = new Set(value);

  function toggle(item: WorkItem) {
    onChange((current) => {
      const next = new Set(current);
      next.has(item) ? next.delete(item) : next.add(item);
      return available.filter((w) => next.has(w));
    });
  }

  const group = (title: string, all: readonly WorkItem[], kind: "finish" | "repair") => {
    const items = all.filter((w) => available.includes(w));
    if (!items.length) return null;
    return (
    <div className="scope-group">
      <span className="label">{title}</span>
      <div className="scope-chips">
        {items.map((item) => (
          <button
            key={item}
            type="button"
            role="checkbox"
            aria-checked={selected.has(item)}
            className={`scope-chip ${kind} ${selected.has(item) ? "on" : ""}`}
            onClick={() => toggle(item)}
          >
            <span className="scope-check" aria-hidden="true">{selected.has(item) ? "✓" : ""}</span>
            {kind === "finish" && <span className={`el-dot el-${item}`} />}
            {t(`work.${item}`)}
          </button>
        ))}
      </div>
    </div>
    );
  };

  return (
    <fieldset className="scope-picker">
      <div className="scope-head">
        <div>
          <legend>{t("scope.title")}</legend>
          <p className="muted small">{t("scope.sub")}</p>
        </div>
        <div className="scope-actions">
          <span className="muted small">
            {t("scope.count").replace("{n}", String(value.length)).replace("{total}", String(available.length))}
          </span>
          <button type="button" className="link" onClick={() => onChange(() => [...available])}>{t("scope.all")}</button>
          <button type="button" className="link" onClick={() => onChange(() => [])}>{t("scope.none")}</button>
        </div>
      </div>
      {group(t("scope.finishing"), FINISHING_WORK, "finish")}
      {group(t("scope.repairs"), REPAIR_WORK, "repair")}
      {value.length === 0 && <p className="scope-empty">{t("scope.empty")}</p>}
    </fieldset>
  );
}
