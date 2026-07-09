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

export const api = {
  summary: () => request("/summary"),
  rooms: () => request("/rooms"),
  payments: () => request("/payments"),
  latePayments: () => request("/payments/late"),
  unpaidPayments: () => request("/payments/unpaid"),
  auditLog: () => request("/audit-log?limit=100"),
  chat: (message) =>
    request("/chat", { method: "POST", body: JSON.stringify({ message }) }),
  confirmChat: (actionId, confirm) =>
    request("/chat/confirm", {
      method: "POST",
      body: JSON.stringify({ action_id: actionId, confirm }),
    }),
  rollover: (preview, excludedRoomIds = []) =>
    request("/rental-periods/auto-rollover", {
      method: "POST",
      body: JSON.stringify({
        preview,
        excluded_room_ids: excludedRoomIds,
      }),
    }),
  undoLastChange: (preview, backupFile = null) =>
    request("/undo/last-change", {
      method: "POST",
      body: JSON.stringify({ preview, backup_file: backupFile }),
    }),
};
