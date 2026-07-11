import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, BedDouble, Bot, Building2, CalendarSync, Database,
  History, LayoutDashboard, Menu, ReceiptText, RefreshCw, X,
} from "lucide-react";
import { api } from "./api";
import Dashboard from "./pages/Dashboard";
import Rooms from "./pages/Rooms";
import Payments from "./pages/Payments";
import RawData from "./pages/RawData";
import Chatbot from "./pages/Chatbot";
import AutoRollover from "./pages/AutoRollover";
import AuditLog from "./pages/AuditLog";

const navigation = [
  ["dashboard", "Dashboard", LayoutDashboard],
  ["rooms", "Rooms", BedDouble],
  ["payments", "Payments", ReceiptText],
  ["raw", "Raw Data", Database],
  ["chat", "Chatbot", Bot],
  ["rollover", "Auto Rollover", CalendarSync],
  ["audit", "Audit Log", History],
];
const ALL_LOCATION = { location_id: "all", name: "All Locations" };

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [mobileNav, setMobileNav] = useState(false);
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(() => localStorage.getItem("selected-location") || "gedung_panjang");
  const [data, setData] = useState({
    summary: null, rooms: [], payments: [], late: [], unpaid: [], audit: [], locationSummaries: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const locationList = await api.locations();
      setLocations(locationList);
      const locationId = selectedLocation;
      const [summary, rooms, payments, late, unpaid, audit] = await Promise.all([
        api.summary(locationId), api.rooms(locationId), api.payments(locationId), api.latePayments(locationId),
        api.unpaidPayments(locationId), api.auditLog(locationId),
      ]);
      const locationSummaries = locationId === "all"
        ? await Promise.all(locationList.map((location) => api.summary(location.location_id)))
        : [];
      setData({ summary, rooms, payments, late, unpaid, audit, locationSummaries });
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedLocation]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    localStorage.setItem("selected-location", selectedLocation);
  }, [selectedLocation]);
  useEffect(() => {
    const refreshOnFocus = () => refresh();
    window.addEventListener("focus", refreshOnFocus);
    return () => window.removeEventListener("focus", refreshOnFocus);
  }, [refresh]);

  const CurrentPage = useMemo(() => ({
    dashboard: Dashboard, rooms: Rooms, payments: Payments, raw: RawData,
    chat: Chatbot, rollover: AutoRollover, audit: AuditLog,
  })[page], [page]);

  const openPage = (nextPage) => {
    setPage(nextPage);
    setMobileNav(false);
    if (nextPage === "dashboard") refresh();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const locationOptions = [ALL_LOCATION, ...locations];
  const selectedLocationInfo = locationOptions.find((item) => item.location_id === selectedLocation) || ALL_LOCATION;

  const changeLocation = (event) => {
    setSelectedLocation(event.target.value);
    setMobileNav(false);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="icon-button nav-toggle" onClick={() => setMobileNav(true)} aria-label="Open navigation">
          <Menu size={22} />
        </button>
        <div className="brand">
          <span className="brand-mark"><Building2 size={22} /></span>
          <div><strong>{selectedLocationInfo.name}</strong><span>Rental manager</span></div>
        </div>
        <label className="location-picker">
          <span>Location</span>
          <select value={selectedLocation} onChange={changeLocation}>
            {locationOptions.map((location) => (
              <option key={location.location_id} value={location.location_id}>{location.name}</option>
            ))}
          </select>
        </label>
        <nav className="desktop-nav" aria-label="Main navigation">
          {navigation.map(([id, label, Icon]) => (
            <button key={id} className={page === id ? "active" : ""} onClick={() => openPage(id)}>
              <Icon size={17} />{label}
            </button>
          ))}
        </nav>
        <button className="icon-button refresh-button" onClick={refresh} title="Refresh data" aria-label="Refresh data">
          <RefreshCw size={19} className={loading ? "spin" : ""} />
        </button>
      </header>

      {mobileNav && (
        <div className="mobile-nav-overlay" onClick={() => setMobileNav(false)}>
          <aside onClick={(event) => event.stopPropagation()}>
            <div className="mobile-nav-head"><strong>Menu</strong><button className="icon-button" onClick={() => setMobileNav(false)}><X /></button></div>
            {navigation.map(([id, label, Icon]) => (
              <button key={id} className={page === id ? "active" : ""} onClick={() => openPage(id)}>
                <Icon size={19} />{label}
              </button>
            ))}
          </aside>
        </div>
      )}

      <main className="page-container">
        {error && (
          <div className="connection-error"><AlertTriangle size={20} /><div><strong>Cannot load rental data</strong><span>{error}</span></div></div>
        )}
        {!error && <CurrentPage {...data} loading={loading} refresh={refresh} selectedLocation={selectedLocation} selectedLocationInfo={selectedLocationInfo} />}
      </main>
      <footer>{lastUpdated ? `Last refreshed ${lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Rental records"}</footer>
    </div>
  );
}
