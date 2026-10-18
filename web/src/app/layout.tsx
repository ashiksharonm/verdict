import { ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { ToastProvider } from "@/components/Toast";
import Nav from "@/components/Nav";
import { HF_URL, REPO_URL } from "@/lib/config";
import "./globals.css";

const SITE = "https://verdict-sooty-zeta.vercel.app";
export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  openGraph: { type: "website", siteName: "Verdict", title: "Verdict: calibrated guardrails from one small model", description: "PII, toxicity, prompt-injection and groundedness checks with calibrated scores from one small, self-hostable model.", url: SITE },
  twitter: { card: "summary", title: "Verdict: calibrated guardrails from one small model", description: "PII, toxicity, prompt-injection and groundedness checks with calibrated scores from one small, self-hostable model." },
  title: { default: "Verdict: calibrated guardrails from one small model", template: "%s | Verdict" },
  description: "PII, toxicity, prompt-injection and groundedness checks with calibrated scores from one small, self-hostable model.",
};

const themeInit = `document.documentElement.classList.add("js");try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="min-h-screen antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-full focus:bg-surface focus:px-4 focus:py-2">
          Skip to content
        </a>
        <ToastProvider>
        <Nav />
        <main id="main" className="mx-auto max-w-6xl px-4 pb-24 pt-12 sm:px-6 sm:pt-16">
          {children}
        </main>
        <footer className="border-t border-border">
          <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-muted sm:px-6 md:flex-row md:items-start md:justify-between">
            <div className="max-w-sm">
              <p className="text-base font-medium tracking-tight text-ink">Verdict</p>
              <p className="mt-1">Calibrated guardrail checks from one small, self-hostable model. No tracking scripts.</p>
            </div>
            <ul className="flex flex-wrap gap-x-8 gap-y-2">
              <li><a className="link inline-flex items-center gap-0.5" href={REPO_URL}>GitHub repository <ArrowUpRight aria-hidden className="size-3.5" /></a></li>
              <li><a className="link inline-flex items-center gap-0.5" href="https://huggingface.co/ashiksharon005/verdict-laya">Verdict model on Hugging Face <ArrowUpRight aria-hidden className="size-3.5" /></a></li>
              <li><a className="link inline-flex items-center gap-0.5" href={HF_URL}>Laya base model <ArrowUpRight aria-hidden className="size-3.5" /></a></li>
              <li><a className="link" href={`${REPO_URL}/blob/main/LICENSE`}>MIT licence (code)</a></li>
            </ul>
          </div>
          <p className="mx-auto max-w-6xl px-4 pb-8 text-xs text-muted sm:px-6">Code is MIT-licensed; the fine-tuned model is Apache-2.0. Datasets and the base model keep their own licences.</p>
        </footer>
        </ToastProvider>
      </body>
    </html>
  );
}
