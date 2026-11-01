import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { activatePriceList, deletePriceList, listPriceLists, savePrices } from "../api";
import { useI18n } from "../i18n";
import type { Finish, PriceItem, PriceListInfo, PriceTable } from "../types";

interface Props {
  table: PriceTable;
  onSaved: (table: PriceTable) => void;
  onClose: () => void;
}

const FINISHES: Finish[] = ["basic", "standard", "premium"];

export default function PriceEditor({ table, onSaved, onClose }: Props) {
  const { t, el } = useI18n();
  const [draft, setDraft] = useState<PriceTable>(structuredClone(table));
  const [currency, setCurrency] = useState(table.default_currency);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const importRef = useRef<HTMLInputElement>(null);
  // Saved price lists: the default rates plus every vendor file imported or saved.
  const [lists, setLists] = useState<PriceListInfo[]>([]);
  const refreshLists = () => listPriceLists().then(setLists).catch(() => setLists([]));
  useEffect(() => {
    refreshLists();
  }, []);
  const active = lists.find((l) => l.active);

  function load(table: PriceTable) {
    onSaved(table);
    setDraft(structuredClone(table));
    setCurrency(table.default_currency);
  }

  async function switchList(id: string) {
    try {
      load(await activatePriceList(id));
      refreshLists();
      setStatus({ ok: true, text: t("prices.switched").replace("{name}", lists.find((l) => l.id === id)?.name ?? id) });
    } catch (e) {
      setStatus({ ok: false, text: e instanceof Error ? e.message : "Could not switch." });
    }
  }

  async function removeList() {
    if (!active || active.id === "default" || !window.confirm(t("prices.deleteConfirm").replace("{name}", active.name))) return;
    await deletePriceList(active.id).catch(() => undefined);
    await switchList("default");
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.classList.add("modal-open");
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.classList.remove("modal-open");
    };
  }, [onClose]);

  function setItem(name: string, patch: Partial<PriceItem>) {
    setDraft({
      ...draft,
      tables: { ...draft.tables, [currency]: { ...draft.tables[currency], [name]: { ...draft.tables[currency][name], ...patch } } },
    });
    setStatus(null);
  }

  async function save() {
    try {
      load(await savePrices(draft));
      refreshLists();
      setStatus({ ok: true, text: t("prices.saved") });
    } catch (e) {
      setStatus({ ok: false, text: e instanceof Error ? e.message : "Could not save." });
    }
  }

  /** A vendor's price file replaces the table at once; the server checks it and says what's wrong. */
  async function importFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    let data: PriceTable;
    try {
      data = JSON.parse(await file.text());
      if (!data.tables || !data.default_currency) throw new Error();
    } catch {
      setStatus({ ok: false, text: t("prices.importBad") });
      return;
    }
    try {
      const saved = await savePrices(data);
      load(saved);
      refreshLists();
      setStatus({ ok: true, text: t("prices.imported").replace("{name}", saved.vendor?.name || file.name) });
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("prices.importBad") });
    }
  }

  return (
    <div className="modal-backdrop no-print" onClick={onClose}>
      <div className="drawer" role="dialog" aria-modal="true" aria-label={t("prices.title")} onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h3>{t("prices.title")}</h3>
          <div className="drawer-actions">
            <button type="button" className="btn ghost small" onClick={() => importRef.current?.click()}>{t("prices.import")}</button>
            <button type="button" className="btn ghost small" onClick={onClose}>{t("prices.close")}</button>
          </div>
          <input ref={importRef} type="file" accept="application/json,.json" hidden onChange={importFile} />
        </div>
        {lists.length > 1 && (
          <div className="price-list-row">
            <label className="field">
              <span>{t("prices.list")}</span>
              <select value={active?.id ?? ""} onChange={(e) => switchList(e.target.value)}>
                {lists.map((l) => (
                  <option key={l.id} value={l.id}>{l.name} · {l.currencies.join("/")}</option>
                ))}
              </select>
            </label>
            {active && active.id !== "default" && (
              <button type="button" className="link danger small" onClick={removeList}>{t("prices.deleteList")}</button>
            )}
          </div>
        )}
        <div className="segmented">
          {Object.keys(draft.tables).map((c) => (
            <button key={c} type="button" className={c === currency ? "active" : ""} onClick={() => setCurrency(c)}>{c}</button>
          ))}
        </div>
        <p className="muted small">{draft.note}</p>
        <div className="table-wrap">
          <table className="data-table edit">
            <thead>
              <tr>
                <th>{t("results.element")}</th>
                <th>{t("prices.label")}</th>
                <th>{t("prices.unit")}</th>
                <th className="num">{t("prices.low")}</th>
                <th className="num">{t("prices.high")}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(draft.tables[currency]).map(([name, item]) => (
                <tr key={name}>
                  <td><span className={`el-dot el-${name}`} />{el(name)}</td>
                  <td><input dir="ltr" value={item.label} onChange={(e) => setItem(name, { label: e.target.value })} /></td>
                  <td className="muted">{item.unit === "m2" ? t("prices.perM2") : t("results.each")}</td>
                  <td><input type="number" min="0" value={item.low} onChange={(e) => setItem(name, { low: Number(e.target.value) })} /></td>
                  <td><input type="number" min="0" value={item.high} onChange={(e) => setItem(name, { high: Number(e.target.value) })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="field-row three">
          {FINISHES.map((f) => (
            <label key={f} className="field">
              <span>{t(`upload.${f}`)} {t("prices.multiplier")}</span>
              <input
                type="number"
                min="0.1"
                step="0.05"
                value={draft.finish_multipliers[f]}
                onChange={(e) => setDraft({ ...draft, finish_multipliers: { ...draft.finish_multipliers, [f]: Number(e.target.value) } })}
              />
            </label>
          ))}
        </div>
        <div className="drawer-foot">
          <label className="field">
            <span>{t("prices.default")}</span>
            <select value={draft.default_currency} onChange={(e) => setDraft({ ...draft, default_currency: e.target.value })}>
              {Object.keys(draft.tables).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <button type="button" className="btn primary" onClick={save}>{t("prices.save")}</button>
        </div>
        {status && <div className={`alert ${status.ok ? "success" : "error"}`}>{status.text}</div>}
      </div>
    </div>
  );
}
