import type { Metadata } from "next";
import LoginForm from "@/components/LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default function Page() {
  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-3xl font-bold">Sign in</h1>
      <LoginForm />
    </div>
  );
}
