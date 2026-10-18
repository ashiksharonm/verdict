export default function Loading() {
  return (
    <div role="status" aria-label="Loading" className="space-y-4">
      <div className="skeleton h-4 w-28" />
      <div className="skeleton h-12 w-full max-w-xl" />
      <div className="skeleton h-5 w-full max-w-md" />
      <div className="skeleton mt-8 h-64 w-full" />
    </div>
  );
}
