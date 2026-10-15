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

  return (
    <div className="flex items-start gap-3 border-b border-slate-100 py-3">
      <input
        type="checkbox"
        aria-label={`Keep ${field.field_name}`}
        checked={kept}
        onChange={(e) => onToggle(e.target.checked)}
        className="mt-2.5 h-4 w-4"
      />

      <div className="flex-1 space-y-1">
        <div className="flex items-baseline justify-between gap-4">
          <label htmlFor={inputId} className="text-sm font-medium text-slate-800">
            {field.field_name}
          </label>
          <span className="shrink-0 text-xs text-slate-500">
            {Math.round(field.confidence * 100)}% · {field.source_document}
          </span>
        </div>
        <input
          id={inputId}
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          className="w-full rounded-md border border-slate-300 p-2"
        />
      </div>
    </div>
  );
}
