"use client"

import { useState, useRef, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Loader2, Home, Mail, ChevronRight } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"
import MarkdownRenderer from "@/components/MarkdownRenderer"

export default function Chat() {
  const router = useRouter()
  const { toast } = useToast()
  const [messages, setMessages] = useState([
    {
      role: "system",
      content: "Hello! I'm your email assistant. Ask me anything about your emails.",
    },
  ])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
    if (!loading && inputRef.current) {
      inputRef.current.focus()
    }
  }, [messages, loading])

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!input.trim()) return

    const userMessage = {
      role: "user",
      content: input,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setLoading(true)

    try {
      const response = await fetch("http://127.0.0.1:8000/ask_query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: userMessage.content,
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to get response")
      }

      const data = await response.json()

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
        },
      ])
    } catch (error) {
      console.error("Query error:", error)
      toast({
        variant: "destructive",
        title: "Query Failed",
        description: "There was a problem processing your query. Please try again.",
      })

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "I'm sorry, I encountered an error while processing your request. Please try again.",
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const goToHome = () => {
    router.push("/")
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-background to-background/95">
      {/* Header */}
      <header className="border-b border-border/40 bg-card/30 backdrop-blur-sm p-4 sticky top-0 z-10">
        <div className="container flex items-center justify-between max-w-5xl">
          <div className="flex items-center space-x-3">
            <div className="bg-primary/10 p-2 rounded-full">
              <Mail className="h-5 w-5 text-primary" />
            </div>
            <h1 className="text-xl font-bold">Email Assistant</h1>
          </div>
          <Button variant="outline" size="sm" onClick={goToHome} className="rounded-full py-2 px-6">
            <Home className="h-4 w-4 mr-2 inline" />
            Home
          </Button>
        </div>
      </header>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 container max-w-5xl">
        <div className="space-y-6 py-4">
          {messages.map((message, index) => (
            <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <Card
                className={`p-4 max-w-[85%] md:max-w-[70%] animate-in slide-in-from-${message.role === "user" ? "right" : "left"}-5 fade-in-50 duration-300 ${
                  message.role === "user"
                    ? "bg-primary text-primary-foreground rounded-2xl rounded-tr-none"
                    : "bg-card border border-border/50 rounded-2xl rounded-tl-none"
                }`}
              >
                {message.role === "user" ? (
                  <div className="whitespace-pre-wrap">{message.content}</div>
                ) : (
                  <MarkdownRenderer content={message.content} />
                )}
              </Card>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Form */}
      <div className="border-t border-border/40 bg-card/30 backdrop-blur-sm p-4 sticky bottom-0">
        <form onSubmit={handleSubmit} className="container max-w-3xl mx-auto">
          <div className="flex space-x-2 items-center">
            <div className="relative flex-1">
              <Input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your emails..."
                disabled={loading}
                className="pr-12 px-4 py-6 rounded-full bg-card border-border/50 focus-visible:ring-primary"
              />
              <Button
                type="submit"
                size="icon"
                disabled={loading || !input.trim()}
                className="absolute right-1 top-1/2 transform -translate-y-1/2 rounded-full h-10 w-10 text-center"
              >
                {loading ? <Loader2 className="h-5 w-5 animate-spin ml-3" /> : <ChevronRight className="h-5 w-5 ml-3" />}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

