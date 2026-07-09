import React, { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { EmptyState, LoadingState, PageHeader } from "../components/Common";
import { formatCurrencyIDR } from "../utils";

const filters = ["All", "Occupied", "Empty", "AC", "Non-AC", "Rent required", "No rent required"];

export default function Rooms({ rooms, loading }) {
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const visible = useMemo(() => rooms.filter((room) => {
    const matches = !query || String(room.room_id).includes(query) || String(room.note || "").toLowerCase().includes(query.toLowerCase());
    if (!matches) return false;
    if (filter === "Occupied" || filter === "Empty") return room.current_status === filter;
    if (filter === "AC") return room.ac === "Y";
    if (filter === "Non-AC") return room.ac !== "Y";
    if (filter === "Rent required") return room.rent_required === "Y";
    if (filter === "No rent required") return room.rent_required === "N";
    return true;
  }), [rooms, filter, query]);
  if (loading && !rooms.length) return <LoadingState />;

  return <>
    <PageHeader title="Rooms" subtitle="Current room setup and availability." />
    <div className="toolbar">
      <div className="segmented">{filters.map((item) => <button className={filter === item ? "active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div>
      <label className="search"><Search size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search room or note" /></label>
    </div>
    {!visible.length ? <EmptyState /> : <div className="table-wrap"><table><thead><tr>
      <th>Room</th><th>Status</th><th>Floor</th><th>AC</th><th>Occupants</th><th>Usual rent</th><th>Rent required</th><th>Note</th>
    </tr></thead><tbody>{visible.map((room) => <tr key={room.room_id}>
      <td><strong>{room.room_id}</strong></td><td><span className={`room-status ${room.current_status?.toLowerCase()}`}>{room.current_status || "-"}</span></td>
      <td>{room.floor ?? "-"}</td><td>{room.ac === "Y" ? "Yes" : "No"}</td><td>{room.current_occupants}</td>
      <td>{formatCurrencyIDR(room.usual_price)}</td><td>{room.rent_required === "Y" ? "Yes" : "No"}</td><td className="notes-cell">{room.note || "-"}</td>
    </tr>)}</tbody></table></div>}
  </>;
}
