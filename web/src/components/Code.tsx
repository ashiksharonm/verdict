export default function Code({ children, label }: { children: string; label?: string }) {
  return (
    <pre tabIndex={0} aria-label={label}>
      <code>{children}</code>
    </pre>
  );
}
