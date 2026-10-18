"use client";
import { useEffect, useState } from "react";
import { supabaseConfigured } from "@/lib/config";
import { getSupabase } from "@/lib/supabase";

export default function LoginForm() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  // Read ?error= after mount: reading it during render differs between server and client (hydration error).
  const [authError, setAuthError] = useState(false);
  useEffect(() => setAuthError(Boolean(new URLSearchParams(window.location.search).get("error"))), []);
  const supabase = getSupabase();

  if (!supabaseConfigured || !supabase) {
    return <p role="alert" className="rounded-xl border border-signal p-4">Sign-in is not configured: set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.</p>;
  }
  const redirectTo = () => `${window.location.origin}/auth/callback`;

  return (
    <div className="space-y-5">
      {authError && <p role="alert" className="text-bad">Sign-in failed. Please try again.</p>}
      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: redirectTo() } });
          setMsg(error ? { ok: false, text: error.message } : { ok: true, text: "Check your inbox for the sign-in link." });
          setBusy(false);
        }}
      >
        <label htmlFor="email" className="block text-sm font-medium">Email</label>
        <input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className="field" />
        <button type="submit" disabled={busy} className="btn btn-primary w-full">Send magic link</button>
      </form>
      <div className="text-center text-sm text-muted">or</div>
      <button
        type="button"
        className="btn btn-ghost w-full"
        onClick={async () => {
          const { error } = await supabase.auth.signInWithOAuth({ provider: "github", options: { redirectTo: redirectTo() } });
          if (error) setMsg({ ok: false, text: error.message });
        }}
      >
        Continue with GitHub
      </button>
      <p aria-live="polite" role="status" className={msg?.ok ? "text-ok" : "text-bad"}>{msg?.text}</p>
    </div>
  );
}
