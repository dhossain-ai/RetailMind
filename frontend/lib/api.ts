const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type ChatRoute = "analytics" | "document" | "unknown"

export type ChatResponse = {
  route: ChatRoute
  answer: string
  sql?: string
  columns?: string[]
  rows?: unknown[][]
  sources?: string[]
}

export type UploadResponse = {
  document_id: number
  filename: string
  original_filename: string
  chunk_count: number
  status: "ingested" | "skipped"
}

export async function postChat(message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<ChatResponse>
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_URL}/documents/upload`, {
    method: "POST",
    body: form,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<UploadResponse>
}
