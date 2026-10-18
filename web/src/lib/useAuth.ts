"use client";
import type { Session, User } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { getSupabase } from "./supabase";

export type AuthState = { status: "loading" } | { status: "anon" } | { status: "user"; email: string; avatarUrl: string | null };

/** Dev-only: `?preview=1` fakes a signed-in session. NODE_ENV is inlined at build time, so this is dead code in production bundles. */
export function previewEnabled(): boolean {
  if (process.env.NODE_ENV === "production") return false;
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("preview") === "1";
}

const fromUser = (u: User | undefined | null): AuthState => {
  if (!u) return { status: "anon" };
  const avatar = u.user_metadata?.avatar_url;
  return { status: "user", email: u.email ?? "", avatarUrl: typeof avatar === "string" && /^https:\/\//.test(avatar) ? avatar : null };
};

/** Session-aware auth state. `loading` until the first session read so callers can render a same-size placeholder. */
export function useAuth(): { auth: AuthState; signOut: () => Promise<void> } {
  const [auth, setAuth] = useState<AuthState>({ status: "loading" });
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" && previewEnabled()) {
      setAuth({ status: "user", email: "ashik.sharon@example.com", avatarUrl: null });
      return;
    }
    const supabase = getSupabase();
    if (!supabase) {
      setAuth({ status: "anon" });
      return;
    }
    let live = true;
    supabase.auth.getSession().then(({ data }: { data: { session: Session | null } }) => live && setAuth(fromUser(data.session?.user)));
    const { data } = supabase.auth.onAuthStateChange((_e: string, session: Session | null) => setAuth(fromUser(session?.user)));
    return () => {
      live = false;
      data.subscription.unsubscribe();
    };
  }, []);
  const signOut = async () => {
    await getSupabase()?.auth.signOut();
    setAuth({ status: "anon" });
  };
  return { auth, signOut };
}
