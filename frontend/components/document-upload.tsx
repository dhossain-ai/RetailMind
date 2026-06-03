"use client"

import { useRef, useState } from "react"
import { Upload, CheckCircle2, AlertCircle, Loader2 } from "lucide-react"
import { uploadDocument, type UploadResponse } from "@/lib/api"

type UploadState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "done"; result: UploadResponse }
  | { status: "error"; message: string }

export function DocumentUpload() {
  const [state, setState] = useState<UploadState>({ status: "idle" })
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setState({ status: "error", message: "Only PDF files are accepted." })
      return
    }
    setState({ status: "uploading" })
    try {
      const result = await uploadDocument(file)
      setState({ status: "done", result })
    } catch (err) {
      setState({ status: "error", message: (err as Error).message })
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ""
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const isUploading = state.status === "uploading"

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Upload Document
      </p>

      <div
        role="button"
        tabIndex={0}
        aria-label="Upload PDF document"
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onClick={() => !isUploading && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && !isUploading && inputRef.current?.click()}
        className={[
          "flex cursor-pointer select-none flex-col items-center gap-2 rounded-lg border border-dashed p-4 text-center text-sm transition-colors outline-none",
          dragging
            ? "border-ring bg-muted/40"
            : "border-border text-muted-foreground hover:border-ring hover:bg-muted/20",
          isUploading ? "pointer-events-none opacity-60" : "",
        ].join(" ")}
      >
        {isUploading ? (
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        ) : (
          <Upload className="size-5" />
        )}
        <span>{isUploading ? "Uploading…" : "Drop PDF or click to browse"}</span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={handleChange}
      />

      {state.status === "done" && (
        <div className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2 text-xs">
          <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-green-600" />
          <span className="text-foreground">
            <span className="font-medium">{state.result.original_filename}</span>{" "}
            {state.result.status === "skipped"
              ? "already indexed"
              : `indexed (${state.result.chunk_count} chunks)`}
          </span>
        </div>
      )}

      {state.status === "error" && (
        <div className="flex items-start gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-destructive" />
          <span className="text-destructive">{state.message}</span>
        </div>
      )}
    </div>
  )
}
