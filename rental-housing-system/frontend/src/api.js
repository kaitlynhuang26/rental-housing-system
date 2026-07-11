export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
  } catch {
    throw new Error(
      `Backend is not connected. Please start FastAPI at ${API_BASE_URL}.`,
    );
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail?.detail || body?.detail || body?.message;
    throw new Error(
      typeof detail === "string" ? detail : `Request failed (${response.status}).`,
    );
  }
  return body;
}

function withLocation(path, locationId) {
  if (!locationId) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}location_id=${encodeURIComponent(locationId)}`;
}

export const api = {
  locations: () => request("/locations"),
  summary: (locationId) => request(withLocation("/summary", locationId)),
  rooms: (locationId) => request(withLocation("/rooms", locationId)),
  payments: (locationId) => request(withLocation("/payments", locationId)),
  latePayments: (locationId) => request(withLocation("/payments/late", locationId)),
  unpaidPayments: (locationId) => request(withLocation("/payments/unpaid", locationId)),
  auditLog: (locationId) => request(withLocation("/audit-log?limit=100", locationId)),
  chat: (message, locationId) =>
    request("/chat", { method: "POST", body: JSON.stringify({ message, location_id: locationId }) }),
  confirmChat: (actionId, confirm, locationId) =>
    request("/chat/confirm", {
      method: "POST",
      body: JSON.stringify({ action_id: actionId, confirm, location_id: locationId }),
    }),
  rollover: (preview, excludedRoomIds = [], locationId) =>
    request(withLocation("/rental-periods/auto-rollover", locationId), {
      method: "POST",
      body: JSON.stringify({
        preview,
        excluded_room_ids: excludedRoomIds,
      }),
    }),
  undoLastChange: (preview, backupFile = null, locationId) =>
    request(withLocation("/undo/last-change", locationId), {
      method: "POST",
      body: JSON.stringify({ preview, backup_file: backupFile }),
    }),
};
