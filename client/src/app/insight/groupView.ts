export const fmtPp = (value: number | null, digits = 2) => value == null
  ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(digits)}%p`;

export const plainPct = (value: number | null) => value == null ? "—" : `${value.toFixed(1)}%`;

export function updateGroupView(values: Record<string, string | null>, replace = false) {
  const url = new URL(window.location.href);
  Object.entries(values).forEach(([key, value]) => {
    if (value === null) url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  });
  window.history[replace ? "replaceState" : "pushState"](null, "", url);
}
