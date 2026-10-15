import { useState } from "react";

import { verify, type ExtractedField } from "../api";
import FieldRow from "../components/FieldRow";

function messageOf(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

type Row = {
  field_name: string;
  value: string;
  kept: boolean;
};

type Props = {
  sessionId: string;
  fields: ExtractedField[];
  onDone: (downloadUrl: string) => void;
};

function initialRows(fields: ExtractedField[]): Row[] {
  return fields.map((field) => ({
    field_name: field.field_name,
    value: field.value,
    // Confident or non-empty values are worth filling; the rest need a look.
    kept: field.confidence >= 0.5 || field.value !== "",
  }));
}

export default function ReviewStep({ sessionId, fields, onDone }: Props) {
  const [rows, setRows] = useState<Row[]>(() => initialRows(fields));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update(index: number, patch: Partial<Row>) {
    setRows((current) =>
      current.map((row, i) => (i === index ? { ...row, ...patch } : row))
    );
  }

  async function handleSubmit() {
    const kept = rows.filter((row) => row.kept);
    const verifiedFields = Object.fromEntries(kept.map((row) => [row.field_name, row.value]));

    setBusy(true);
    setError(null);
    try {
      const result = await verify({
        sessionId,
        verifiedFields,
        keptFields: kept.map((row) => row.field_name),
      });
      onDone(result.download_url);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  if (fields.length === 0) {
    return (
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Nothing was found</h1>
        <p className="text-slate-600">
          We could not read any values from those receipts. Try adding more of them, or
          clearer copies.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Check what we found</h1>
        <p className="mt-1 text-slate-600">
          Fix anything that looks wrong, and untick what you do not need on the form.
        </p>
      </div>

      <div>
        {rows.map((row, index) => (
          <FieldRow
            key={row.field_name}
            field={fields[index]}
            kept={row.kept}
            value={row.value}
            onToggle={(kept) => update(index, { kept })}
            onValueChange={(value) => update(index, { value })}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={busy}
        className="rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
      >
        {busy ? "Filling…" : "Fill the form"}
      </button>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
