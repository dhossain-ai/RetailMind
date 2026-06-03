"use client"

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react"
import { BarChart2, Bot, FileText, HelpCircle, Loader2, Send, User } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { AnalyticsResult } from "@/components/analytics-result"
import { DocumentSources } from "@/components/document-sources"
import { DocumentUpload } from "@/components/document-upload"
import { postChat, type ChatResponse, type ChatRoute } from "@/lib/api"

// ── Types ─────────────────────────────────────────────────────────────────────

type Message = {
  id: string
  role: "user" | "assistant"
  text: string
  response?: ChatResponse
  error?: string
}

// ── Route badge metadata ───────────────────────────────────────────────────────

type BadgeMeta = {
  label: string
  icon: React.ReactNode
  variant: "default" | "secondary" | "outline"
}

const ROUTE_META: Record<ChatRoute, BadgeMeta> = {
  analytics: {
    label: "Analytics",
    icon: <BarChart2 className="size-3" />,
    variant: "secondary",
  },
  document: {
    label: "Document",
    icon: <FileText className="size-3" />,
    variant: "outline",
  },
  unknown: {
    label: "Unknown",
    icon: <HelpCircle className="size-3" />,
    variant: "outline",
  },
}

// ── ChatPage ──────────────────────────────────────────────────────────────────

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function submit() {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", text }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setLoading(true)

    try {
      const response = await postChat(text)
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", text: response.answer, response },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "",
          error: (err as Error).message,
        },
      ])
    } finally {
      setLoading(false)
      // Return focus to the input after response arrives
      setTimeout(() => textareaRef.current?.focus(), 0)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    submit()
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-sidebar">
        {/* Logo */}
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
          <div className="flex size-7 items-center justify-center rounded-lg bg-primary">
            <Bot className="size-4 text-primary-foreground" />
          </div>
          <span className="text-sm font-semibold text-sidebar-foreground">RetailMind</span>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 px-2 py-3">
          <button
            type="button"
            className="flex items-center gap-2.5 rounded-md bg-sidebar-accent px-3 py-2 text-sm font-medium text-sidebar-accent-foreground"
          >
            <Bot className="size-4 shrink-0" />
            Chat
          </button>
        </nav>

        <Separator />

        {/* Document upload */}
        <div className="p-4">
          <DocumentUpload />
        </div>

        {/* Footer */}
        <div className="mt-auto border-t border-border px-4 py-3">
          <p className="text-xs text-muted-foreground">RetailMind v0.1</p>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Messages */}
        <ScrollArea className="flex-1">
          <div className="mx-auto max-w-2xl space-y-6 px-6 py-8">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-muted">
                  <Bot className="size-8 text-muted-foreground opacity-50" />
                </div>
                <p className="text-base font-medium text-foreground">How can I help?</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Ask about your retail data or uploaded documents.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
              >
                {/* Avatar */}
                <div
                  className={`flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {msg.role === "user" ? (
                    <User className="size-4" />
                  ) : (
                    <Bot className="size-4" />
                  )}
                </div>

                {/* Content */}
                <div
                  className={`flex max-w-[85%] flex-col gap-2 ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  {/* Bubble */}
                  {msg.error ? (
                    <div className="rounded-xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
                      Error: {msg.error}
                    </div>
                  ) : (
                    <div
                      className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
                        msg.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-foreground"
                      }`}
                    >
                      {msg.text}
                    </div>
                  )}

                  {/* Route badge */}
                  {msg.response && (
                    <div>
                      <Badge
                        variant={ROUTE_META[msg.response.route].variant}
                        className="gap-1"
                      >
                        {ROUTE_META[msg.response.route].icon}
                        {ROUTE_META[msg.response.route].label}
                      </Badge>
                    </div>
                  )}

                  {/* Analytics: SQL + table */}
                  {msg.response?.route === "analytics" &&
                    msg.response.sql &&
                    msg.response.columns &&
                    msg.response.rows && (
                      <AnalyticsResult
                        sql={msg.response.sql}
                        columns={msg.response.columns}
                        rows={msg.response.rows}
                      />
                    )}

                  {/* Document: sources */}
                  {msg.response?.route === "document" && msg.response.sources && (
                    <DocumentSources sources={msg.response.sources} />
                  )}
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {loading && (
              <div className="flex gap-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
                  <Bot className="size-4 text-muted-foreground" />
                </div>
                <div className="flex items-center gap-2 rounded-xl bg-muted px-4 py-3 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  Thinking…
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        {/* ── Input bar ───────────────────────────────────────────────────── */}
        <div className="border-t border-border bg-background px-4 py-4">
          <form
            onSubmit={handleSubmit}
            className="mx-auto flex max-w-2xl items-end gap-2"
          >
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your retail data or documents… (Enter to send, Shift+Enter for new line)"
              disabled={loading}
              className="resize-none"
            />
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim() || loading}
              className="mb-px shrink-0"
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
            </Button>
          </form>
        </div>
      </main>
    </div>
  )
}
