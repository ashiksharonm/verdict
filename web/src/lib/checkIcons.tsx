import { BookCheck, ChartColumn, Fingerprint, MessageSquareWarning, ShieldAlert, ShieldUser, Terminal, type LucideIcon } from "lucide-react";
import type { CheckName } from "./config";

export const CHECK_ICONS: Record<CheckName, LucideIcon> = {
  pii: ShieldUser,
  toxicity: MessageSquareWarning,
  prompt_injection: ShieldAlert,
  grounded: BookCheck,
};
export const PRESET_ICONS: Record<string, LucideIcon> = {
  "support-pii": Fingerprint,
  "rag-hallucination": BookCheck,
  "injection-firewall": ShieldAlert,
  "comment-moderation": MessageSquareWarning,
  "ci-gate": Terminal,
  "cheap-prefilter": ChartColumn,
};
