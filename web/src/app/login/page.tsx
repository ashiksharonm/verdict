import type { Metadata } from "next";
import LoginForm from "@/components/LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default function Page() {
  return (
    <div className="mx-auto max-w-md">
      <p className="eyebrow">Account</p>
      <h1 className="h2 mb-8 mt-3 !text-4xl">Sign in</h1>
      <div className="card p-6 sm:p-8">
        <LoginForm />
      </div>
    </div>
  );
}
