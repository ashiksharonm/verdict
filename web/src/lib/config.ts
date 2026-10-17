export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "https://ashiksharon005-verdict-api.hf.space").replace(/\/$/, "");
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
export const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
export const REPO_URL = "https://github.com/ashiksharonm/verdict";
export const supabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

export const CHECKS = ["pii", "toxicity", "prompt_injection", "grounded"] as const;
export type CheckName = (typeof CHECKS)[number];
export const CHECK_INFO: Record<CheckName, { label: string; question: string }> = {
  pii: { label: "PII", question: "Does the text contain personal data?" },
  toxicity: { label: "Toxicity", question: "Is the text toxic, insulting or threatening?" },
  prompt_injection: { label: "Prompt injection", question: "Is this user input an injection or jailbreak attempt?" },
  grounded: { label: "Grounded", question: "Is the response supported by the provided context?" },
};
