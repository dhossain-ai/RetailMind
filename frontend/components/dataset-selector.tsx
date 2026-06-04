"use client"

import { AlertCircle, BarChart2, Database } from "lucide-react"
import type { DatasetListItem } from "@/lib/api"

interface Props {
  datasets: DatasetListItem[]
  selectedId: number | null
  onChange: (id: number | null, dataset: DatasetListItem | null) => void
  error?: string
}

export function DatasetSelector({ datasets, selectedId, onChange, error }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Data Source
      </p>

      <div className="space-y-0.5">
        {/* Demo Data — always first, never removable */}
        <button
          type="button"
          onClick={() => onChange(null, null)}
          className={[
            "flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-left transition-colors",
            selectedId === null
              ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
              : "text-muted-foreground hover:bg-muted/40",
          ].join(" ")}
        >
          <BarChart2 className="size-3.5 shrink-0" />
          <span>Demo Data</span>
        </button>

        {/* Uploaded datasets, newest first */}
        {datasets.map((ds) => (
          <button
            key={ds.dataset_id}
            type="button"
            onClick={() => onChange(ds.dataset_id, ds)}
            className={[
              "flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-left transition-colors",
              selectedId === ds.dataset_id
                ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-muted/40",
            ].join(" ")}
          >
            <Database className="size-3.5 shrink-0" />
            <span className="min-w-0 flex-1 truncate" title={ds.original_filename}>
              {ds.original_filename}
            </span>
            {ds.row_count != null && (
              <span className="shrink-0 tabular-nums opacity-60">
                {ds.row_count.toLocaleString()}r
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="flex items-start gap-1.5 rounded-lg bg-destructive/10 px-3 py-2 text-xs">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-destructive" />
          <span className="text-destructive">{error}</span>
        </div>
      )}
    </div>
  )
}
