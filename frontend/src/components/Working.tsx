import { useEffect, useState } from "react";

type Props = {
  label: string;
  detail?: string;
};

/**
 * Reassurance for work with no measurable percentage: what is happening, an
 * elapsed clock so a long wait looks alive rather than frozen, and a nudge
 * once it has clearly taken a while.
 */
export default function Working({ label, detail }: Props) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <div
      role="status"
      aria-live="polite"
      className="space-y-3 rounded-lg border border-line/60 bg-muted/40 p-4"
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-accent"
        />
        <span className="text-sm font-medium text-accent-soft">{label}</span>
      </div>

      {/* Indeterminate: the work has no measurable percentage to report. */}
      <div
        aria-hidden="true"
        className="h-1 w-full overflow-hidden rounded-full bg-line/40"
      >
        <div className="h-full w-1/3 animate-slide rounded-full bg-accent" />
      </div>

      <div className="flex justify-between text-xs text-fg-muted">
        <span>{detail}</span>
        <span>{clock}</span>
      </div>

      {seconds >= 30 && (
        <p className="text-xs text-fg-muted">
          Still working — some trips take a few minutes. Keep this tab open.
        </p>
      )}
    </div>
  );
}
