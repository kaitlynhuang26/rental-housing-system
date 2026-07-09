export function formatCurrencyIDR(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  })
    .format(Number(value) || 0)
    .replace("IDR", "Rp");
}

export function formatDate(value) {
  if (!value) return "-";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : String(value);
}

export function normalizeStatus(value) {
  const status = String(value || "N/A").trim().toLowerCase();
  if (status === "paid") return "Paid";
  if (status === "late") return "Late";
  if (status === "unpaid") return "Unpaid";
  if (status === "pending") return "Pending";
  return "N/A";
}

export function getPaymentStatusColor(value) {
  return `status-${normalizeStatus(value).toLowerCase().replace("/", "")}`;
}

export const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
