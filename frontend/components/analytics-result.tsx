import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface Props {
  sql: string
  columns: string[]
  rows: unknown[][]
}

export function AnalyticsResult({ sql, columns, rows }: Props) {
  return (
    <div className="mt-2 space-y-3 w-full">
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Generated SQL
        </p>
        <pre className="overflow-x-auto rounded-lg bg-zinc-950 p-3 text-xs text-zinc-100 font-mono leading-relaxed">
          <code>{sql}</code>
        </pre>
      </div>

      {rows.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Results — {rows.length} {rows.length === 1 ? "row" : "rows"}
          </p>
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((col) => (
                    <TableHead key={col}>{col}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, i) => (
                  <TableRow key={i}>
                    {(row as unknown[]).map((cell, j) => (
                      <TableCell key={j}>{cell == null ? "—" : String(cell)}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {rows.length === 0 && (
        <p className="text-xs text-muted-foreground">Query returned no rows.</p>
      )}
    </div>
  )
}
