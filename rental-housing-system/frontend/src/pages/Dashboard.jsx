import React from "react";
import { Banknote, BedDouble, CircleDollarSign, CreditCard, DoorOpen, HandCoins, TriangleAlert, Users } from "lucide-react";
import { AlertRows, LoadingState, PageHeader } from "../components/Common";
import { formatCurrencyIDR } from "../utils";

export default function Dashboard({ summary, rooms, late, unpaid, loading, locationSummaries = [], selectedLocation }) {
  if (loading && !summary) return <LoadingState />;
  const cards = [
    ["Total rooms", summary?.total_rooms, BedDouble, "neutral"],
    ["Occupied", summary?.occupied_rooms, Users, "green"],
    ["Empty", summary?.empty_rooms, DoorOpen, "red"],
    ["Late payments", summary?.late_payment_rows, TriangleAlert, "orange"],
    ["Unpaid payments", summary?.unpaid_payment_rows, CircleDollarSign, "red"],
    ["Total amount due", formatCurrencyIDR(summary?.total_amount_due), Banknote, "neutral"],
    ["Total amount paid", formatCurrencyIDR(summary?.total_amount_paid), HandCoins, "green"],
    ["Cash collected", formatCurrencyIDR(summary?.total_cash_collected), Banknote, "neutral"],
    ["Transfer collected", formatCurrencyIDR(summary?.total_transfer_collected), CreditCard, "neutral"],
    ["Total collected", formatCurrencyIDR((summary?.total_cash_collected || 0) + (summary?.total_transfer_collected || 0)), HandCoins, "green"],
  ];
  const occupied = rooms.filter((room) => room.current_status === "Occupied");
  const empty = rooms.filter((room) => room.current_status === "Empty");

  return <>
    <PageHeader title="Dashboard" subtitle="A clear view of rooms, payments, and what needs attention." />
    <section className="summary-grid">{cards.map(([label, value, Icon, tone]) => (
      <article className={`summary-card ${tone}`} key={label}><div><span>{label}</span><strong>{value ?? "-"}</strong></div><Icon size={21} /></article>
    ))}</section>
    {selectedLocation === "all" && !!locationSummaries.length && <section className="section-block">
      <div className="section-heading"><div><h2>Locations overview</h2><p>Compare each rental location at a glance.</p></div></div>
      <div className="location-overview">
        {locationSummaries.map((item) => <article className="location-card" key={item.location_id}>
          <strong>{item.location_name}</strong>
          <dl>
            <dt>Total rooms</dt><dd>{item.total_rooms}</dd>
            <dt>Occupied</dt><dd>{item.occupied_rooms}</dd>
            <dt>Empty</dt><dd>{item.empty_rooms}</dd>
            <dt>Total paid</dt><dd>{formatCurrencyIDR(item.total_amount_paid)}</dd>
          </dl>
        </article>)}
      </div>
    </section>}
    <section className="section-block">
      <div className="section-heading"><div><h2>Room availability</h2><p>Current room status from the latest rental records.</p></div></div>
      <div className="availability">
        <div><h3><span className="dot occupied" />Occupied rooms <small>{occupied.length}</small></h3><div className="room-chips">{occupied.map((room) => <span className="room-chip occupied" key={`${room.location_id || "one"}-${room.room_id}`}>{room.location_id && selectedLocation === "all" ? `${room.location_name}: ` : ""}{room.room_id}</span>)}</div></div>
        <div><h3><span className="dot empty" />Empty rooms <small>{empty.length}</small></h3><div className="room-chips">{empty.map((room) => <span className="room-chip empty" key={`${room.location_id || "one"}-${room.room_id}`}>{room.location_id && selectedLocation === "all" ? `${room.location_name}: ` : ""}{room.room_id}</span>)}</div></div>
      </div>
    </section>
    <section className="section-block">
      <div className="section-heading"><div><h2>Needs attention</h2><p>Late and unpaid rental periods.</p></div><span className="count-label">{late.length + unpaid.length} alerts</span></div>
      <AlertRows late={late} unpaid={unpaid} />
    </section>
    {!!summary?.warnings?.length && <section className="warning-list">{summary.warnings.map((warning) => <p key={warning}>{warning}</p>)}</section>}
  </>;
}
