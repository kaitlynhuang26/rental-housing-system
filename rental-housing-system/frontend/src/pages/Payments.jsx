import React, { useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { EmptyState, LoadingState, PageHeader, StatusBadge } from "../components/Common";
import { formatCurrencyIDR, monthNames } from "../utils";

export default function Payments({ payments, loading }) {
  const years = useMemo(() => [...new Set(payments.map((p) => p.rent_start_date?.slice(0, 4)).filter(Boolean))].sort().reverse(), [payments]);
  const [selectedYear, setSelectedYear] = useState("");
  const year = selectedYear || years[0] || String(new Date().getFullYear());
  const grouped = useMemo(() => {
    const rooms = new Map();
    payments.filter((p) => p.rent_start_date?.startsWith(year) && p.record_status !== "Cancelled").forEach((payment) => {
      const month = Number(payment.rent_start_date.slice(5, 7)) - 1;
      if (!rooms.has(payment.room_id)) rooms.set(payment.room_id, { names: new Set(), months: Array.from({ length: 12 }, () => []) });
      const room = rooms.get(payment.room_id);
      if (payment.tenant_name) room.names.add(payment.tenant_name);
      room.months[month].push(payment);
    });
    return [...rooms.entries()].sort((a, b) => a[0] - b[0]);
  }, [payments, year]);
  if (loading && !payments.length) return <LoadingState />;

  return <>
    <PageHeader title="Monthly payments" subtitle="Rental periods arranged by their start month." action={
      <label className="field-label">Year<select value={year} onChange={(e) => setSelectedYear(e.target.value)}>{years.map((item) => <option key={item}>{item}</option>)}</select></label>
    } />
    {!grouped.length ? <EmptyState message={`No payment records found for ${year}.`} /> :
      <div className="calendar-wrap"><table className="payment-calendar"><thead><tr><th className="sticky-col">Room & tenant</th>{monthNames.map((month) => <th key={month}>{month.slice(0, 3)}</th>)}</tr></thead>
      <tbody>{grouped.map(([roomId, room]) => <tr key={roomId}><td className="sticky-col room-identity"><strong>Room {roomId}</strong><span>{[...room.names].join(", ") || "No tenant"}</span></td>
        {room.months.map((records, month) => <td key={month}>{records.map((record) => <article className="month-payment" key={record.row_number}>
          <div className="month-payment-head"><strong>{formatCurrencyIDR(record.amount_due)}</strong><StatusBadge status={record.calculated_payment_status} /></div>
          <span>{record.rent_start_date} to {record.rent_end_date}</span>
          <span>{record.payment_date ? `Paid ${record.payment_date}` : "No payment yet"}</span>
          <span>{record.payment_method || "-"}</span>
        </article>)}{records.length > 1 && <div className="multiple-warning"><AlertTriangle size={13} />Multiple records</div>}</td>)}
      </tr>)}</tbody></table></div>}
  </>;
}
