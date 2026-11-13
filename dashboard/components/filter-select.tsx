"use client"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export const ALL = "all"

interface FilterSelectProps {
  label: string
  allLabel: string
  value: string
  options: readonly string[]
  onChange: (value: string) => void
}

// Dropdown filter with an "All" option
export function FilterSelect({ label, allLabel, value, options, onChange }: FilterSelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" aria-label={label} className="w-40">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{allLabel}</SelectItem>
        {options.map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
