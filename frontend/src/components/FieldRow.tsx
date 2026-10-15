import type { ExtractedField } from "../api";

type Props = {
  field: ExtractedField;
  kept: boolean;
  value: string;
  onToggle: (kept: boolean) => void;
  onValueChange: (value: string) => void;
};

export default function FieldRow({ field, kept, value, onToggle, onValueChange }: Props) {
  const inputId = `value-${field.field_name}`;
  // "Personnel number" reads better than the PDF's own "UHD" or "Personalnummer".
  const label = field.semantic_name || field.field_name;

  return (
    <div className="flex items-start gap-3 py-4">
      <input
        type="checkbox"
        aria-label={`Keep ${label}`}
        checked={kept}
        onChange={(e) => onToggle(e.target.checked)}
        className="mt-2.5 h-4 w-4 shrink-0 accent-accent"
      />

      <div className="flex-1 space-y-2">
        <div className="flex items-baseline justify-between gap-4">
          <label htmlFor={inputId} className="text-sm font-medium text-accent-soft">
            {label}
          </label>
          <span
            className={`shrink-0 text-xs ${
              field.confidence >= 0.5 ? "text-fg-muted" : "text-accent"
            }`}
          >
            {Math.round(field.confidence * 100)}% · {field.source_document}
          </span>
        </div>
        <input
          id={inputId}
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          className="w-full rounded-lg border border-line bg-muted px-3 py-2 text-fg transition-colors focus:border-accent"
        />
      </div>
    </div>
  );
}
