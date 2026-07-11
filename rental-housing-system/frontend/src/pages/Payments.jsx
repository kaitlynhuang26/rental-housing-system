import React, { useMemo, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { EmptyState, LoadingState, PageHeader, StatusBadge } from "../components/Common";
import { formatCurrencyIDR, monthNames } from "../utils";

export default function Payments({ payments, loading, selectedLocation }) {
  const years = useMemo(() => [...new Set(payments.map((p) => p.rent_start_date?.slice(0, 4)).filter(Boolean))].sort().reverse(), [payments]);
  const [selectedYear, setSelectedYear] = useState("");
  const [selectedPayment, setSelectedPayment] = useState(null);
  const year = selectedYear || years[0] || String(new Date().getFullYear());
  const currentTenantByRoom = useMemo(() => {
    const latest = new Map();
    payments.filter((p) => p.record_status !== "Cancelled").forEach((payment) => {
      const key = `${payment.location_id || "one"}-${payment.room_id}`;
      const sortValue = `${payment.rent_start_date || ""}-${payment.rent_end_date || ""}-${String(payment.row_number || 0).padStart(6, "0")}`;
      const existing = latest.get(key);
      if (!existing || sortValue > existing.sortValue) {
        latest.set(key, {
          sortValue,
          tenantName: payment.tenant_name || "No tenant",
        });
      }
    });
    return latest;
  }, [payments]);
  const grouped = useMemo(() => {
    const rooms = new Map();
    payments.filter((p) => p.rent_start_date?.startsWith(year) && p.record_status !== "Cancelled").forEach((payment) => {
      const month = Number(payment.rent_start_date.slice(5, 7)) - 1;
      const key = `${payment.location_id || "one"}-${payment.room_id}`;
      if (!rooms.has(key)) rooms.set(key, { roomId: payment.room_id, locationName: payment.location_name, currentTenant: currentTenantByRoom.get(key)?.tenantName || "No tenant", months: Array.from({ length: 12 }, () => []) });
      const room = rooms.get(key);
      room.months[month].push(payment);
    });
    return [...rooms.entries()].sort((a, b) => Number(a[1].roomId || 0) - Number(b[1].roomId || 0));
  }, [payments, year, currentTenantByRoom]);
  if (loading && !payments.length) return <LoadingState />;

  return <>
    <PageHeader title="Monthly payments" subtitle="Rental periods arranged by their start month." action={
      <label className="field-label">Year<select value={year} onChange={(e) => setSelectedYear(e.target.value)}>{years.map((item) => <option key={item}>{item}</option>)}</select></label>
    } />
    {!grouped.length ? <EmptyState message={`No payment records found for ${year}.`} /> :
      <div className="calendar-wrap"><table className="payment-calendar"><thead><tr><th className="sticky-col">Room & tenant</th>{monthNames.map((month) => <th key={month}>{month.slice(0, 3)}</th>)}</tr></thead>
      <tbody>{grouped.map(([key, room]) => <tr key={key}><td className="sticky-col room-identity"><strong>Room {room.roomId}</strong><span>{selectedLocation === "all" && room.locationName ? `${room.locationName} • ` : ""}{room.currentTenant}</span></td>
        {room.months.map((records, month) => <td key={month}>{records.map((record) => <button className="month-payment" key={record.row_number} onClick={() => setSelectedPayment(record)} type="button">
          <div className="month-payment-head"><strong>{formatCurrencyIDR(record.amount_due)}</strong><StatusBadge status={record.calculated_payment_status} /></div>
          <span>{record.rent_start_date} to {record.rent_end_date}</span>
          <span>{record.payment_date ? `Paid ${record.payment_date}` : "No payment yet"}</span>
          <span>{record.payment_method || "-"}</span>
        </button>)}{records.length > 1 && <div className="multiple-warning"><AlertTriangle size={13} />Multiple records</div>}</td>)}
      </tr>)}</tbody></table></div>}
    {selectedPayment && <PaymentModal payment={selectedPayment} onClose={() => setSelectedPayment(null)} />}
  </>;
}

function PaymentModal({ payment, onClose }) {
  const details = [
    ["Location", payment.location_name],
    ["Room", payment.room_id],
    ["Tenant", payment.tenant_name],
    ["Phone", payment.tenant_ph],
    ["Rent period", `${payment.rent_start_date || "-"} to ${payment.rent_end_date || "-"}`],
    ["Amount due", formatCurrencyIDR(payment.amount_due)],
    ["Amount paid", formatCurrencyIDR(payment.amount_paid)],
    ["Payment date", payment.payment_date],
    ["Payment method", payment.payment_method],
    ["Room status", payment.room_status],
    ["AC", payment.ac],
    ["Record status", payment.record_status],
    ["Source", payment.source],
    ["Notes", payment.notes],
  ];

  return <div className="modal-backdrop" onClick={onClose} role="presentation">
    <section className="payment-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label={`Payment details for room ${payment.room_id}`}>
      <header className="payment-modal-head">
        <div>
          <span>Payment details</span>
          <h2>Room {payment.room_id}</h2>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close payment details"><X size={22} /></button>
      </header>
      <div className="payment-modal-summary">
        <strong>{formatCurrencyIDR(payment.amount_due)}</strong>
        <StatusBadge status={payment.calculated_payment_status} />
      </div>
      <dl className="payment-detail-grid">
        {details.map(([label, value]) => <React.Fragment key={label}>
          <dt>{label}</dt>
          <dd>{value || "-"}</dd>
        </React.Fragment>)}
      </dl>
      {!!payment.warnings?.length && <div className="warning-list">{payment.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
    </section>
  </div>;
}
