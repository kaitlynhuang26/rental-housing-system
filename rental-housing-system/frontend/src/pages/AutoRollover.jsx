import React, { useState } from "react";
import { CalendarSync, CheckCircle2 } from "lucide-react";
import { api } from "../api";
import { EmptyState, PageHeader, StatusBadge } from "../components/Common";
import { formatCurrencyIDR } from "../utils";

export default function AutoRollover({ refresh, selectedLocation, selectedLocationInfo }) {
  const [preview, setPreview] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadPreview = async () => {
    setLoading(true); setError(""); setMessage("");
    try {
      const result = await api.rollover(true, [], selectedLocation);
      setPreview(result);
      setSelected(new Set(result.rows_to_create.map((row) => row.room_id)));
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  const toggle = (roomId) => setSelected((current) => {
    const next = new Set(current);
    next.has(roomId) ? next.delete(roomId) : next.add(roomId);
    return next;
  });
  const save = async () => {
    setLoading(true); setError("");
    const excluded = preview.rows_to_create.filter((row) => !selected.has(row.room_id)).map((row) => row.room_id);
    try {
      const result = await api.rollover(false, excluded, selectedLocation);
      setMessage(result.message);
      setPreview(null);
      await refresh();
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };

  return <>
    <PageHeader title="Auto rollover" subtitle={`Review next rental periods for ${selectedLocationInfo?.name || "the selected location"}.`} action={
      <button className="button primary" disabled={loading || selectedLocation === "all"} onClick={loadPreview}><CalendarSync size={18} />{loading ? "Checking..." : "Preview Auto Rollover"}</button>
    } />
    {selectedLocation === "all" && <div className="info-banner">Choose one rental location before running auto rollover. This prevents creating rows in the wrong workbook.</div>}
    <div className="info-banner">Tenants are assumed to continue. Uncheck any room where the tenant is not continuing.</div>
    {error && <div className="inline-error">{error}</div>}
    {message && <div className="success-banner"><CheckCircle2 />{message}</div>}
    {preview && <section className="section-block">
      <div className="section-heading"><div><h2>Proposed rental periods</h2><p>{selected.size} of {preview.rows_to_create.length} selected</p></div></div>
      {!preview.rows_to_create.length ? <EmptyState message="No rental periods need to be created." /> :
      <div className="rollover-list">{preview.rows_to_create.map((row) => <label className="rollover-row" key={row.room_id}>
        <input type="checkbox" checked={selected.has(row.room_id)} onChange={() => toggle(row.room_id)} />
        <div className="rollover-room"><strong>Room {row.room_id}</strong><span>{row.tenant_name || "No tenant name"}</span></div>
        <div><span>New period</span><strong>{row.rent_start_date} to {row.rent_end_date}</strong></div>
        <div><span>Amount due</span><strong>{formatCurrencyIDR(row.amount_due)}</strong></div>
        <StatusBadge status={row.payment_status} />
      </label>)}</div>}
      {!!preview.skipped.length && <details><summary>{preview.skipped.length} skipped rooms</summary>{preview.skipped.map((item) => <p key={item}>{item}</p>)}</details>}
      {!!preview.warnings.length && <div className="warning-list">{preview.warnings.map((item) => <p key={item}>{item}</p>)}</div>}
      {!!preview.rows_to_create.length && <div className="rollover-actions"><button className="button primary" disabled={loading || !selected.size} onClick={save}><CheckCircle2 size={18} />Confirm Selected Auto Rollover Rows</button></div>}
    </section>}
  </>;
}
