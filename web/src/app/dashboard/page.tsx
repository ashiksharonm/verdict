import type { Metadata } from "next";
import Dashboard from "@/components/Dashboard";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return (
    <div>
      <p className="eyebrow">Account</p>
      <h1 className="display mb-10 mt-3">Dashboard</h1>
      <Dashboard />
    </div>
  );
}
