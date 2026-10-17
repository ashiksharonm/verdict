import type { Metadata } from "next";
import Nav from "@/components/Nav";
import { REPO_URL } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Verdict: calibrated guardrails from one small model", template: "%s | Verdict" },
  description: "PII, toxicity, prompt-injection and groundedness checks with calibrated scores from one small, self-hostable model.",
};

const themeInit = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="min-h-screen antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-card focus:px-3 focus:py-2">
          Skip to content
        </a>
        <Nav />
        <main id="main" className="mx-auto max-w-5xl px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-border">
          <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-muted">
            MIT-licensed code, <a className="underline" href={REPO_URL}>source on GitHub</a>. Datasets and base models keep their own licences. No tracking scripts.
          </div>
        </footer>
      </body>
    </html>
  );
}
