import { FileText } from "lucide-react"
import { Badge } from "@/components/ui/badge"

interface Props {
  sources: string[]
}

export function DocumentSources({ sources }: Props) {
  if (sources.length === 0) return null

  return (
    <div className="mt-2">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Sources
      </p>
      <div className="flex flex-wrap gap-2">
        {sources.map((src, i) => (
          <Badge key={i} variant="outline" className="gap-1.5 font-normal max-w-xs truncate">
            <FileText className="size-3 shrink-0" />
            <span className="truncate">{src}</span>
          </Badge>
        ))}
      </div>
    </div>
  )
}
