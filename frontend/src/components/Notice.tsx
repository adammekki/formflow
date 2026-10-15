type Props = {
  tone: "error" | "warning";
  children: React.ReactNode;
};

export default function Notice({ tone, children }: Props) {
  const styles =
    tone === "error"
      ? "border-red-800 bg-red-950/60 text-red-200"
      : "border-amber-700 bg-amber-950/60 text-amber-200";

  return (
    <p role="alert" className={`rounded-lg border p-3 text-sm ${styles}`}>
      {children}
    </p>
  );
}
