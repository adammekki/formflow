import type { ExtractedField } from "../api";
import { fieldLabel } from "../fieldLabel";

type Props = {
  field: ExtractedField;
  kept: boolean;
  value: string;
  selected?: boolean;
  rowId?: string;
  onToggle: (kept: boolean) => void;
  onValueChange: (value: string) => void;
  onSelect?: () => void;
};

export default function FieldRow({
  field,
  kept,
  value,
  selected = false,
  rowId,
  onToggle,
  onValueChange,
  onSelect,
}: Props) {
  const inputId = `value-${field.field_name}`;
  const label = fieldLabel(field);
  const confident = field.confidence >= 0.5;

  return (
    <tr
      id={rowId}
      aria-selected={selected}
      onClick={onSelect}
      onFocus={onSelect}
      className={`border-t border-line/40 align-top ${kept ? "" : "text-fg-muted"} ${
        selected ? "bg-accent/10 ring-1 ring-inset ring-accent/50" : ""
      }`}
    >
      <td className="px-3 py-3">
        <input
          type="checkbox"
          aria-label={`Keep ${label}`}
          checked={kept}
          onChange={(e) => onToggle(e.target.checked)}
          className="h-4 w-4 accent-accent"
        />
      </td>

      {/* break-words matters: some names are 200+ characters with no spaces,
          and must wrap inside the column rather than widen the table. */}
      <td className="px-3 py-3">
        <label htmlFor={inputId} className="break-words text-sm leading-snug text-fg">
          {label}
        </label>
      </td>

      <td className="px-3 py-3">
        <input
          id={inputId}
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          className="w-full rounded-md border border-line bg-muted px-2 py-1.5 text-sm text-fg transition-colors focus:border-accent"
        />
      </td>

      <td className="px-3 py-3 text-xs">
        <span className={`block ${confident ? "text-fg-muted" : "text-accent"}`}>
          {Math.round(field.confidence * 100)}% confident
        </span>
        <span className="block break-words text-fg-muted">{field.source_document}</span>
      </td>
    </tr>
  );
}
