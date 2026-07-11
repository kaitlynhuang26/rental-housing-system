import React, { useState } from "react";
import { RotateCcw, ShieldCheck, X } from "lucide-react";
import { api } from "../api";
import { EmptyState, LoadingState, PageHeader } from "../components/Common";
import { formatDate } from "../utils";

export default function AuditLog({ audit, loading, refresh, selectedLocation, selectedLocationInfo }) {
  const [undoPreview, setUndoPreview] = useState(null);
  const [undoBusy, setUndoBusy] = useState(false);
  const [undoMessage, setUndoMessage] = useState("");
  const [undoError, setUndoError] = useState("");

  const previewUndo = async () => {
    setUndoBusy(true); setUndoError(""); setUndoMessage("");
    try { setUndoPreview(await api.undoLastChange(true, null, selectedLocation)); }
    catch (error) { setUndoError(error.message); }
    finally { setUndoBusy(false); }
  };

  const confirmUndo = async () => {
    setUndoBusy(true); setUndoError("");
    try {
      const result = await api.undoLastChange(
        false,
        undoPreview.rows_to_create?.[0]?.backup_file,
        selectedLocation,
      );
      setUndoMessage(result.message);
      setUndoPreview(null);
      await refresh();
    } catch (error) { setUndoError(error.message); }
    finally { setUndoBusy(false); }
  };

  if (loading && !audit.length) return <LoadingState />;
  const records = [...audit].reverse();
  return <>
    <PageHeader title="Audit log" subtitle={`Recent saved changes for ${selectedLocationInfo?.name || "the selected location"}.`} action={
      <button className="button secondary" disabled={undoBusy || selectedLocation === "all"} onClick={previewUndo}><RotateCcw size={18} />Preview Undo Last Change</button>
    } />
    {selectedLocation === "all" && <div className="info-banner">Audit logs from all locations are shown. Choose one location to preview undo for that workbook.</div>}
    {undoError && <div className="inline-error">{undoError}</div>}
    {undoMessage && <div className="success-banner"><ShieldCheck />{undoMessage}</div>}
    {undoPreview && <section className="undo-panel">
      <div><strong>Restore the previous workbook?</strong><p>{undoPreview.message}</p>
        <span>Backup: {undoPreview.rows_to_create?.[0]?.backup_file}</span>
        <span>Created: {undoPreview.rows_to_create?.[0]?.backup_created_at}</span>
      </div>
      <div className="confirm-buttons">
        <button className="button danger" disabled={undoBusy} onClick={confirmUndo}><RotateCcw size={17} />Confirm Undo</button>
        <button className="button secondary" disabled={undoBusy} onClick={() => setUndoPreview(null)}><X size={17} />Cancel</button>
      </div>
    </section>}
    {!records.length ? <EmptyState message="No saved changes are recorded yet." /> : <div className="table-wrap"><table><thead><tr>
      {selectedLocation === "all" && <th>Location</th>}<th>Timestamp</th><th>Action</th><th>Room</th><th>Sheet</th><th>Message</th><th>Status</th><th>Old value</th><th>New value</th>
    </tr></thead><tbody>{records.map((row, index) => <tr key={`${row.timestamp}-${index}`}>
      {selectedLocation === "all" && <td>{row.location_name || "-"}</td>}<td>{formatDate(row.timestamp?.slice(0, 10))} {row.timestamp?.slice(11, 19)}</td><td><strong>{row.action_type?.replaceAll("_", " ") || "-"}</strong></td>
      <td>{row.room_id || "-"}</td><td>{row.sheet_name || "-"}</td><td>{row.user_message || "-"}</td><td><span className={`audit-status ${row.status}`}>{row.status || "-"}</span></td>
      <td className="json-cell">{row.old_value || "-"}</td><td className="json-cell">{row.new_value || "-"}</td>
    </tr>)}</tbody></table></div>}
  </>;
}
