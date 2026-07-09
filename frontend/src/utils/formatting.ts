// Time / cost / percentage formatters used across the dashboard.

/** "HH:MM:SS" or "HH:MM" → seconds since midnight */
export function timeToSeconds(t: string): number {
  const [h, m, s] = t.split(":").map(Number);
  return h * 3600 + m * 60 + (s || 0);
}

/** seconds since midnight → "HH:MM:SS" */
export function secondsToTime(sec: number): string {
  const clamped = Math.max(0, Math.floor(sec)) % 86400;
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = clamped % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

/** seconds since midnight → "HH:MM" */
export function secondsToHHMM(sec: number): string {
  return secondsToTime(sec).slice(0, 5);
}

export function formatCost(v: number): string {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function formatPct(v: number, digits = 1): string {
  return `${v.toFixed(digits)}%`;
}

export function formatMinutes(v: number): string {
  const sign = v < 0 ? "−" : "";
  const abs = Math.abs(v);
  if (abs >= 90) return `${sign}${(abs / 60).toFixed(1)}h`;
  return `${sign}${Math.round(abs)} min`;
}

export function probabilityColor(p: number): string {
  if (p >= 0.7) return "text-aero-red";
  if (p >= 0.4) return "text-aero-amber";
  return "text-aero-green";
}
