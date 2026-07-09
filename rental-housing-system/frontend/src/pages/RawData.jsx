import React, { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { EmptyState, LoadingState, PageHeader, StatusBadge } from "../components/Common";
import { formatCurrencyIDR } from "../utils";

const statuses = ["All", "Paid", "Late", "Unpaid", "Pending", "N/A"];
export default function RawData({ payments, loading }) {
  const [status, setStatus] = useState("All");
  const [room, setRoom] = useState("");
  const [tenant, setTenant] = useState("");
  const visible = useMemo(() => payments.filter((item) =>
    (status === "All" || item.calculated_payment_status === status) &&
    (!room || String(item.room_id || "").includes(room)) &&
    (!tenant || String(item.tenant_name || "").toLowerCase().includes(tenant.toLowerCase()))
  ), [payments, status, room, tenant]);
  if (loading && !payments.length) return <LoadingState />;
  return <>
    <PageHeader title="Raw payment data" subtitle="The detailed records returned by the backend." />
    <div className="toolbar raw-toolbar">
      <div className="segmented">{statuses.map((item) => <button key={item} className={status === item ? "active" : ""} onClick={() => setStatus(item)}>{item}</button>)}</div>
      <label className="search"><Search size={17} /><input value={room} onChange={(e) => setRoom(e.target.value)} placeholder="Room ID" /></label>
      <label className="search"><Search size={17} /><input value={tenant} onChange={(e) => setTenant(e.target.value)} placeholder="Tenant name" /></label>
    </div>
    {!visible.length ? <EmptyState /> : <div className="table-wrap raw-table"><table><thead><tr>
      {["Room","Start","End","Due","Paid","Payment date","Status","Room status","Method","Tenant","Phone","AC","Record","Source","Notes"].map((h) => <th key={h}>{h}</th>)}
    </tr></thead><tbody>{visible.map((p) => <tr key={p.row_number}>
      <td><strong>{p.room_id ?? "-"}</strong></td><td>{p.rent_start_date || "-"}</td><td>{p.rent_end_date || "-"}</td><td>{formatCurrencyIDR(p.amount_due)}</td><td>{formatCurrencyIDR(p.amount_paid)}</td>
      <td>{p.payment_date || "-"}</td><td><StatusBadge status={p.calculated_payment_status} /></td><td>{p.room_status || "-"}</td><td>{p.payment_method || "-"}</td>
      <td>{p.tenant_name || "-"}</td><td>{p.tenant_ph || "-"}</td><td>{p.ac || "-"}</td><td>{p.record_status || "-"}</td><td>{p.source || "-"}</td><td className="notes-cell">{p.notes || "-"}</td>
    </tr>)}</tbody></table></div>}
  </>;
}
