import type { ChartConfig } from "@/components/ui/chart"

// Neutral greys; series are told apart by shade and, for lines, dash pattern
const STYLES = [
  { light: "oklch(0.25 0 0)", dark: "oklch(0.95 0 0)", dash: undefined },
  { light: "oklch(0.45 0 0)", dark: "oklch(0.78 0 0)", dash: "6 3" },
  { light: "oklch(0.6 0 0)", dark: "oklch(0.62 0 0)", dash: "2 3" },
  { light: "oklch(0.78 0 0)", dark: "oklch(0.42 0 0)", dash: "8 3 2 3" },
]

export interface Series {
  key: string
  label: string
  style: number
}

export function chartConfigFor(series: Series[]): ChartConfig {
  return Object.fromEntries(
    series.map((s) => [s.key, { label: s.label, theme: { light: STYLES[s.style].light, dark: STYLES[s.style].dark } }])
  )
}

export function dashFor(series: Series) {
  return STYLES[series.style].dash
}

// Legend with a sample of each line or bar, so dash patterns stay visible (colour squares can't show them)
export function SeriesLegend({ series, shape = "line" }: { series: Series[]; shape?: "line" | "box" }) {
  return (
    <ul className="flex flex-wrap justify-center gap-x-5 gap-y-1 pt-3 text-xs text-muted-foreground">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <svg width={shape === "line" ? 20 : 10} height={shape === "line" ? 6 : 10} aria-hidden>
            {shape === "line" ? (
              <line x1="0" y1="3" x2="20" y2="3" stroke={`var(--color-${s.key})`} strokeWidth="2" strokeDasharray={dashFor(s)} />
            ) : (
              <rect width="10" height="10" rx="2" fill={`var(--color-${s.key})`} />
            )}
          </svg>
          {s.label}
        </li>
      ))}
    </ul>
  )
}
