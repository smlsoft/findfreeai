export default function Loading() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="flex gap-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-10 w-40 rounded-lg bg-secondary" />
        ))}
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-24 rounded-lg bg-secondary" />
        ))}
      </div>
      <div className="h-48 rounded-lg bg-secondary" />
      <div className="h-48 rounded-lg bg-secondary" />
    </div>
  );
}
