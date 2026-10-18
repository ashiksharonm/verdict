"use client";

// Replaces the root layout when it fails, so it carries its own minimal styles (no CSS variables available).
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: "100vh", display: "grid", placeItems: "center", background: "#F7F6F2", color: "#14161C", fontFamily: "system-ui, sans-serif", textAlign: "center", padding: 24 }}>
        <div role="alert" style={{ maxWidth: 440 }}>
          <h1 style={{ fontWeight: 300, fontSize: 36, letterSpacing: "-0.02em", margin: "0 0 12px" }}>Something went wrong</h1>
          <p style={{ color: "#555B69", margin: "0 0 24px" }}>The page failed to load. Try again.</p>
          <button type="button" onClick={reset} style={{ background: "#2F3FBF", color: "#fff", border: 0, borderRadius: 9999, padding: "10px 20px", fontSize: 14, cursor: "pointer" }}>Try again</button>
        </div>
      </body>
    </html>
  );
}
