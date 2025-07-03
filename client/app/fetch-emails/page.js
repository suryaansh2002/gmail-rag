"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Loader2, FileText, CheckCircle, ArrowRight } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

export default function FetchEmails() {
  const router = useRouter()
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [emailCount, setEmailCount] = useState(50)
  const [includeAttachments, setIncludeAttachments] = useState(false)
  const [fetchedCount, setFetchedCount] = useState(0)

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (emailCount < 10 || emailCount > 500) {
      toast({
        variant: "destructive",
        title: "Invalid Input",
        description: "Please enter a number between 10 and 500.",
      })
      return
    }

    setLoading(true)

    try {
      const response = await fetch("http://127.0.0.1:8000/fetch_emails", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          number_of_emails: emailCount,
          include_attachments: includeAttachments ? 1 : 0,
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to fetch emails")
      }

      const data = await response.json()

      if (data.status === "success") {
        setFetchedCount(data.num_emails_fetched)
        setSuccess(true)
        toast({
          title: "Emails Fetched Successfully",
          description: `Successfully fetched ${data.num_emails_fetched} emails.`,
        })

        // Redirect to chat page after a short delay
        setTimeout(() => {
          router.push("/chat")
        }, 2000)
      } else {
        throw new Error("Email fetching failed")
      }
    } catch (error) {
      console.error("Email fetching error:", error)
      toast({
        variant: "destructive",
        title: "Fetching Failed",
        description: "There was a problem fetching your emails. Please try again.",
      })
    } finally {
      setLoading(false)
    }
  }

  // Custom slider component
  const CustomSlider = ({ min, max, value, onChange }) => {
    const percentage = ((value - min) / (max - min)) * 100

    const handleSliderChange = (e) => {
      const newValue = Number.parseInt(e.target.value)
      onChange(newValue)
    }

    return (
      <div className="relative py-4">
        <input
          type="range"
          min={min}
          max={max}
          value={value}
          onChange={handleSliderChange}
          className="w-full h-2 bg-secondary rounded-full appearance-none cursor-pointer"
          style={{
            background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${percentage}%, hsl(var(--secondary)) ${percentage}%, hsl(var(--secondary)) 100%)`,
          }}
        />
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4 bg-gradient-to-b from-background to-background/80">
      <Card className="w-full max-w-md border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="text-center space-y-1">
          <CardTitle className="text-2xl font-bold">Fetch Your Emails</CardTitle>
          <CardDescription className="text-muted-foreground">
            Specify how many emails you want to analyze
          </CardDescription>
        </CardHeader>
        <CardContent>
          {success ? (
            <div className="flex flex-col items-center space-y-6 py-8 animate-in fade-in-50 duration-500">
              <div className="bg-green-500/10 p-6 rounded-full border border-green-500/30">
                <CheckCircle className="h-12 w-12 text-green-500" />
              </div>
              <div className="text-center space-y-2">
                <p className="font-medium text-green-500 text-lg">Successfully fetched {fetchedCount} emails!</p>
                <p className="text-muted-foreground">Preparing your chat interface...</p>
              </div>
              <div className="w-full max-w-[80%] h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary animate-pulse rounded-full" style={{ width: "100%" }}></div>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-8 py-4">
              <div className="space-y-6">
                <div className="flex justify-center mb-6">
                  <div className="relative">
                    <div className="absolute inset-0 bg-primary/20 rounded-full blur-xl"></div>
                    <div className="relative bg-primary/10 p-5 rounded-full border border-primary/30">
                      <FileText className="h-10 w-10 text-primary" />
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <Label htmlFor="emailCount">Number of Emails</Label>
                      <span className="text-2xl font-bold text-primary">{emailCount}</span>
                    </div>

                    <CustomSlider min={10} max={500} value={emailCount} onChange={setEmailCount} />

                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>10</span>
                      <span>250</span>
                      <span>500</span>
                    </div>

                    <p className="text-sm text-muted-foreground mt-2">
                      More emails provide better context but may take longer to process.
                    </p>
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border border-border/50">
                    <Label htmlFor="includeAttachments" className="cursor-pointer flex items-center">
                      <span className="mr-2">Include Attachments</span>
                      <span className="text-xs text-muted-foreground">(may increase processing time)</span>
                    </Label>

                    {/* Custom Switch Component */}
                    <div className="relative inline-block">
                      <input
                        type="checkbox"
                        id="includeAttachments"
                        checked={includeAttachments}
                        onChange={() => setIncludeAttachments(!includeAttachments)}
                        className="sr-only"
                      />
                      <div
                        onClick={() => setIncludeAttachments(!includeAttachments)}
                        className={`block w-12 h-6 rounded-full cursor-pointer transition-colors duration-300 ${
                          includeAttachments ? "bg-primary" : "bg-muted"
                        }`}
                      >
                        <div
                          className={`absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 ${
                            includeAttachments ? "transform translate-x-6" : ""
                          }`}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </form>
          )}
        </CardContent>
        <CardFooter className="flex justify-center pb-8">
          {!success && (
            <Button
              type="submit"
              size="lg"
              className="w-full text-lg py-6 rounded-full group transition-all"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin inline" />
                  Fetching Emails...
                </>
              ) : (
                <>
                  Fetch Emails
                  <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-1 inline" />
                </>
              )}
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  )
}

