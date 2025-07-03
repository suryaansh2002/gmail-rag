import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ArrowRight, Mail, MessageSquare, Shield } from "lucide-react"

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-b from-background to-background/80">
      {/* Single Hero Section */}
      <div className="container px-4 md:px-6 py-10 md:py-14 flex flex-col items-center text-center max-w-5xl">
        <div className="flex items-center justify-center w-20 h-20 mb-8 rounded-full bg-primary/10">
          <Mail className="w-10 h-10 text-primary" />
        </div>

        <h1 className="text-4xl md:text-6xl font-bold tracking-tighter mb-6 bg-clip-text text-transparent bg-gradient-to-r from-primary to-primary/70">
          Chat with Your Gmail Inbox
        </h1>

        <p className="mx-auto max-w-[700px] text-xl text-muted-foreground mb-10">
          Unlock the power of AI to search, summarize, and interact with your emails in natural language.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-3xl mb-12">
          <div className="flex flex-col items-center p-6 rounded-xl bg-card/50 backdrop-blur-sm border border-border/50 hover:border-primary/30 transition-all">
            <Mail className="h-8 w-8 text-primary mb-3" />
            <h3 className="text-lg font-semibold mb-2">Connect Gmail</h3>
            <p className="text-sm text-muted-foreground">Securely link your Gmail account</p>
          </div>

          <div className="flex flex-col items-center p-6 rounded-xl bg-card/50 backdrop-blur-sm border border-border/50 hover:border-primary/30 transition-all">
            <Shield className="h-8 w-8 text-primary mb-3" />
            <h3 className="text-lg font-semibold mb-2">Privacy First</h3>
            <p className="text-sm text-muted-foreground">Your data stays private and secure</p>
          </div>

          <div className="flex flex-col items-center p-6 rounded-xl bg-card/50 backdrop-blur-sm border border-border/50 hover:border-primary/30 transition-all">
            <MessageSquare className="h-8 w-8 text-primary mb-3" />
            <h3 className="text-lg font-semibold mb-2">Natural Chat</h3>
            <p className="text-sm text-muted-foreground">Ask questions in plain English</p>
          </div>
        </div>

        <Link href="/authenticate">
          <Button size="lg" className="px-8 py-6 text-lg rounded-full group w-full">
            Get Started
            <ArrowRight className="inline ml-2 h-5 w-5 transition-transform group-hover:translate-x-1" />
          </Button>
        </Link>

        <div className="mt-16 text-sm text-muted-foreground">
          <p>Powered by advanced AI technology to make email management effortless</p>
        </div>
      </div>
    </div>
  )
}

