"use client"
import ReactMarkdown from "react-markdown"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { atomDark } from "react-syntax-highlighter/dist/cjs/styles/prism"

export default function MarkdownRenderer({ content }) {
  return (
    <ReactMarkdown
      components={{
        h1: ({ node, ...props }) => <h1 className="text-2xl font-bold my-4 text-primary" {...props} />,
        h2: ({ node, ...props }) => <h2 className="text-xl font-bold my-3 text-primary/90" {...props} />,
        h3: ({ node, ...props }) => <h3 className="text-lg font-bold my-2 text-primary/80" {...props} />,
        p: ({ node, ...props }) => <p className="my-2 leading-relaxed" {...props} />,
        ul: ({ node, ...props }) => <ul className="list-disc pl-6 my-3 space-y-1" {...props} />,
        ol: ({ node, ...props }) => <ol className="list-decimal pl-6 my-3 space-y-1" {...props} />,
        li: ({ node, ...props }) => <li className="my-1" {...props} />,
        a: ({ node, ...props }) => (
          <a className="text-primary underline hover:text-primary/80 transition-colors" {...props} />
        ),
        blockquote: ({ node, ...props }) => (
          <blockquote className="border-l-4 border-primary/50 pl-4 italic my-3 text-muted-foreground" {...props} />
        ),
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "")
          return !inline && match ? (
            <SyntaxHighlighter
              style={atomDark}
              language={match[1]}
              PreTag="div"
              className="rounded-md my-3 text-sm"
              {...props}
            >
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          ) : (
            <code
              className={`${
                inline ? "bg-primary/10 text-primary px-1.5 py-0.5 rounded text-sm font-mono" : ""
              } ${className}`}
              {...props}
            >
              {children}
            </code>
          )
        },
        table: ({ node, ...props }) => (
          <div className="overflow-x-auto my-4 rounded-md border border-border/50">
            <table className="w-full border-collapse" {...props} />
          </div>
        ),
        thead: ({ node, ...props }) => <thead className="bg-muted/50" {...props} />,
        tbody: ({ node, ...props }) => <tbody {...props} />,
        tr: ({ node, ...props }) => <tr className="border-b border-border/50" {...props} />,
        th: ({ node, ...props }) => <th className="px-4 py-2 text-left font-bold" {...props} />,
        td: ({ node, ...props }) => <td className="px-4 py-2" {...props} />,
        hr: ({ node, ...props }) => <hr className="my-4 border-muted/50" {...props} />,
        img: ({ node, ...props }) => <img className="max-w-full h-auto rounded-md my-3" {...props} />,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

