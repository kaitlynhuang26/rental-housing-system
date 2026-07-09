import React from "react";
import { Inbox, LoaderCircle } from "lucide-react";
import { formatCurrencyIDR, getPaymentStatusColor, normalizeStatus } from "../utils";

export function PageHeader({ title, subtitle, action }) {
  return <div className="page-header"><div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>;
}

export function LoadingState() {
  return <div className="state"><LoaderCircle className="spin" /><span>Loading rental data...</span></div>;
}

export function EmptyState({ message = "No records found." }) {
  return <div className="state"><Inbox /><span>{message}</span></div>;
}

export function StatusBadge({ status }) {
  return <span className={`status-badge ${getPaymentStatusColor(status)}`}>{normalizeStatus(status)}</span>;
}

export function AlertRows({ late, unpaid }) {
  const rows = [
    ...late.map((item) => ({ ...item, kind: "Late" })),
    ...unpaid.map((item) => ({ ...item, kind: "Unpaid" })),
  ];
  if (!rows.length) return <EmptyState message="No late or unpaid rooms need attention." />;
  return <div className="alert-list">{rows.map((item) => (
    <article className={`alert-item ${item.kind.toLowerCase()}`} key={`${item.kind}-${item.row_number}`}>
      <div className="alert-room">{item.room_id}</div>
      <div>
        <strong>{item.kind === "Late" ? `Room ${item.room_id} paid late` : `Room ${item.room_id} has not paid yet`}</strong>
        <p>{item.tenant_name || "No tenant name"} · {item.rent_start_date} to {item.rent_end_date}</p>
      </div>
      <div className="alert-amount"><strong>{formatCurrencyIDR(item.amount_due)}</strong><span>{item.kind === "Late" ? `Paid ${item.payment_date || "-"}` : "No payment yet"}</span></div>
    </article>
  ))}</div>;
}
