"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Mail, Loader2, CheckCircle, Lock, ArrowRight } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

export default function Authenticate() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    const successParam = searchParams.get("success")

    if (successParam === "true") {
      const state = searchParams.get("state")
      const code = searchParams.get("code")

      if (state && code) {
        handleOAuthCallback(state, code)
      }
    }
  }, [searchParams])

  const handleAuthenticate = async () => {
    setLoading(true)

    try {
      const response = await fetch("http://127.0.0.1:8000/authenticate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          redirect_uri: "http://localhost:3000/authenticate?success=true",
        }),
      })

      if (!response.ok) {
        throw new Error("Authentication request failed")
      }

      const data = await response.json()

      // Redirect to Google OAuth URL
      window.location.href = data.auth_url
    } catch (error) {
      console.error("Authentication error:", error)
      toast({
        variant: "destructive",
        title: "Authentication Failed",
        description: "There was a problem connecting to Gmail. Please try again.",
      })
      setLoading(false)
    }
  }

  const handleOAuthCallback = async (state, code) => {
    setLoading(true)

    try {
      const response = await fetch(`http://127.0.0.1:8000/oauth/callback?state=${state}&code=${code}`, {
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("OAuth callback failed")
      }

      const data = await response.json()

      if (data.success === "true") {
        setSuccess(true)
        toast({
          title: "Successfully Connected",
          description: "Your Gmail account has been connected successfully.",
        })

        // Redirect to email fetching page after a short delay
        setTimeout(() => {
          router.push("/fetch-emails")
        }, 2000)
      } else {
        throw new Error("OAuth verification failed")
      }
    } catch (error) {
      console.error("OAuth callback error:", error)
      toast({
        variant: "destructive",
        title: "Connection Failed",
        description: "There was a problem verifying your Gmail connection. Please try again.",
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4 bg-gradient-to-b from-background to-background/80">
      <Card className="w-full max-w-md border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="text-center space-y-1">
          <CardTitle className="text-2xl font-bold">Connect Your Gmail</CardTitle>
          <CardDescription className="text-muted-foreground">
            Securely connect your Gmail account to start chatting with your emails
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center space-y-8 pt-6">
          <div className="relative">
            <div className="absolute inset-0 bg-primary/20 rounded-full blur-xl"></div>
            <div className="relative bg-primary/10 p-6 rounded-full border border-primary/30">
              <Mail className="h-12 w-12 text-primary" />
            </div>
          </div>

          {success ? (
            <div className="flex flex-col items-center space-y-4 animate-in fade-in-50 duration-500">
              <div className="bg-green-500/10 p-6 rounded-full border border-green-500/30">
                <CheckCircle className="h-12 w-12 text-green-500" />
              </div>
              <p className="text-center text-green-500 font-medium text-lg">Gmail connected successfully!</p>
              <p className="text-center text-muted-foreground">Redirecting to the next step...</p>
            </div>
          ) : (
            <div className="space-y-4 text-center max-w-sm">
              <div className="flex items-center justify-center space-x-2 text-primary">
                <Lock className="h-4 w-4" />
                <span className="text-sm font-medium">Secure Connection</span>
              </div>
              <p className="text-muted-foreground">
                We need your permission to access your Gmail account. We only read the emails you specify and never
                store your credentials.
              </p>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex justify-center pb-8">
          {!success && (
            <Button
              size="lg"
              className="w-full py-6 rounded-full group transition-all"
              onClick={handleAuthenticate}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  Connect Gmail
                  <ArrowRight className="inline ml-2 h-5 w-5 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  )
}

