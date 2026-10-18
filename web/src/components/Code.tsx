import CopyButton from "./CopyButton";

export default function Code({ children, label }: { children: string; label?: string }) {
  return (
    <div className="relative">
      <pre tabIndex={0} aria-label={label} className="pr-12">
        <code>{children}</code>
      </pre>
      <CopyButton label={label ?? "Code"} text={children} className="btn btn-ghost absolute right-2 top-2 !p-1.5" />
    </div>
  );
}
