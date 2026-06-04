const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type ChatRoute = "analytics" | "document" | "unknown"

export type ChatResponse = {
  route: ChatRoute
  answer: string
  sql?: string
  columns?: string[]
  rows?: unknown[][]
  sources?: string[]
  mode?: string
}

export type UploadResponse = {
  document_id: number
  filename: string
  original_filename: string
  chunk_count: number
  status: "ingested" | "skipped"
}

export type DatasetUploadResponse = {
  dataset_id: number
  original_filename: string
  row_count: number
  skipped_count: number
  status: string
}

export type DatasetListItem = {
  dataset_id: number
  original_filename: string
  row_count: number | null
  skipped_count: number
  upload_date: string
}

export async function postChat(
  message: string,
  datasetId?: number | null,
): Promise<ChatResponse> {
  const payload: Record<string, unknown> = { message }
  if (datasetId != null) payload.dataset_id = datasetId
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
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
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<UploadResponse>
}

export async function uploadDataset(file: File): Promise<DatasetUploadResponse> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_URL}/datasets/upload`, {
    method: "POST",
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<DatasetUploadResponse>
}

export async function listDatasets(): Promise<DatasetListItem[]> {
  const res = await fetch(`${API_URL}/datasets`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<DatasetListItem[]>
}
