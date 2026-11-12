export const kg = (value: string | number) =>
  `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} kg`;

export const km = (metres: number) =>
  `${(metres / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })} km`;

export const minutes = (seconds: number) =>
  `${Math.round(seconds / 60).toLocaleString()} min`;

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

export const shortId = (id: string | null | undefined, length = 8) =>
  id ? `${id.slice(0, length)}…` : "—";

export const titleCase = (value: string) =>
  value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const STATUS_TONES: Record<string, string> = {
  PENDING_ALLOCATION: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  ALLOCATED: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  PICKING: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  READY_FOR_DISPATCH: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  OUT_FOR_DELIVERY: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  DELIVERED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  PARTIALLY_SHIPPED: "bg-teal-500/15 text-teal-300 border-teal-500/30",
  CANCELLED: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  FAILED: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  OPEN: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  UNRESOLVED: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  RESOLVED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  PLANNED: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  IN_PROGRESS: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  COMPLETED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
};

export const statusTone = (status: string) =>
  STATUS_TONES[status] ?? "bg-slate-500/15 text-slate-300 border-slate-500/30";
