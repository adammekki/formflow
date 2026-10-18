const STEPS = [0.5, 0.75, 1, 1.5, 2, 3];

type Props = {
  zoom: number;
  onChange: (zoom: number) => void;
  /** Pane name for the button labels, e.g. "source document". */
  name: string;
};

/** Zoom out / in for one pane; 100% means the page fits the pane's width. */
export default function ZoomControls({ zoom, onChange, name }: Props) {
  const index = STEPS.indexOf(zoom);
  const step = (delta: number) => STEPS[index + delta];

  const buttonClass =
    "rounded border border-line px-1.5 leading-5 text-fg-muted transition-colors enabled:hover:border-accent enabled:hover:text-accent disabled:opacity-40";

  return (
    <div className="flex items-center gap-1 text-xs">
      <button
        type="button"
        aria-label={`Zoom out ${name}`}
        disabled={index <= 0}
        onClick={() => onChange(step(-1))}
        className={buttonClass}
      >
        −
      </button>
      <span className="w-9 text-center tabular-nums text-fg-muted" aria-live="polite">
        {Math.round(zoom * 100)}%
      </span>
      <button
        type="button"
        aria-label={`Zoom in ${name}`}
        disabled={index < 0 || index >= STEPS.length - 1}
        onClick={() => onChange(step(1))}
        className={buttonClass}
      >
        +
      </button>
    </div>
  );
}
