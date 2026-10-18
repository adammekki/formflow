import { useEffect, useState } from "react";

import {
  getSession,
  getTemplate,
  pageImageUrl,
  templatePageUrl,
  verify,
  type ExtractedField,
  type SessionInfo,
  type TemplateInfo,
} from "../api";
import Button from "../components/Button";
import DocumentViewer from "../components/DocumentViewer";
import FieldRow from "../components/FieldRow";
import FormPreview from "../components/FormPreview";
import Notice from "../components/Notice";
import { fieldLabel } from "../fieldLabel";

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
  onDone: (downloadUrl: string, unmatchedFields: string[]) => void;
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
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [template, setTemplate] = useState<TemplateInfo | null>(null);
  const [focused, setFocused] = useState<number | null>(null);

  // A missing manifest only costs the box overlay, so a failure keeps the
  // table usable instead of blocking the screen.
  useEffect(() => {
    let cancelled = false;
    getSession(sessionId)
      .then((info) => {
        if (!cancelled) setSession(info);
      })
      .catch(() => {});
    getTemplate(sessionId)
      .then((info) => {
        if (!cancelled) setTemplate(info);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Keep the selected row visible when the selection moves by keyboard.
  useEffect(() => {
    if (focused === null) return;
    document.getElementById(`field-row-${focused}`)?.scrollIntoView?.({ block: "nearest" });
  }, [focused]);

  function update(index: number, patch: Partial<Row>) {
    setRows((current) =>
      current.map((row, i) => (i === index ? { ...row, ...patch } : row))
    );
  }

  /** Up/Down walk the field list, so the viewer follows without the mouse. */
  function handleListKeys(event: React.KeyboardEvent) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const target = event.target as HTMLInputElement;
    // Arrow keys belong to the caret while a value is being edited.
    if (target.tagName === "INPUT" && target.type !== "checkbox") return;
    event.preventDefault();
    setFocused((current) => {
      const step = event.key === "ArrowDown" ? 1 : -1;
      const next = current === null ? 0 : current + step;
      return Math.min(Math.max(next, 0), rows.length - 1);
    });
  }

  /** Which page to show, and where the box sits on it. */
  function viewerTarget() {
    const documents = session?.documents ?? [];
    if (documents.length === 0) {
      return null;
    }
    const field = focused === null ? undefined : fields[focused];
    const index = field
      ? documents.findIndex((doc) => doc.name === field.source_document)
      : -1;
    const docIndex = index >= 0 ? index : 0;
    const box = index >= 0 ? field?.bounding_box ?? null : null;
    return {
      imageUrl: pageImageUrl(sessionId, docIndex, box?.page ?? 0),
      box,
      documentName: documents[docIndex].name,
      page: box?.page ?? 0,
    };
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
      onDone(result.download_url, result.unmatched_fields ?? []);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  if (fields.length === 0) {
    return (
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold text-accent-soft">Nothing was found</h1>
        <p className="text-fg-muted">
          We could not read any values from those receipts. Try adding more of them, or
          clearer copies.
        </p>
      </section>
    );
  }

  /** The template page to show, with a labelled box per kept field on it. */
  function previewTarget() {
    if (!template || template.pages.length === 0) {
      return null;
    }
    const targets = rows.flatMap((row, index) => {
      const target = template.fields.find((f) => f.field_name === row.field_name);
      if (!row.kept || !target) {
        return [];
      }
      return [
        {
          key: row.field_name,
          label: fieldLabel(fields[index]),
          box: target,
          selected: focused === index,
          page: target.page,
        },
      ];
    });
    const page = targets.find((entry) => entry.selected)?.page ?? 0;
    return {
      imageUrl: templatePageUrl(sessionId, page),
      page,
      boxes: targets
        .filter((entry) => entry.page === page)
        .map(({ page: _page, ...box }) => box),
    };
  }

  const target = viewerTarget();
  const preview = previewTarget();

  return (
    <section className="space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-accent-soft">Check what we found</h1>
        <p className="text-fg-muted">
          Fix anything that looks wrong, and untick what you do not need on the form.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {target && (
          <div className="space-y-2 lg:order-1 order-2">
            <span className="text-xs uppercase tracking-wide text-fg-muted">
              Source document
            </span>
            <DocumentViewer {...target} />
          </div>
        )}

        <div className="space-y-4 lg:order-2 order-1">
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-xs uppercase tracking-wide text-fg-muted">Fields found</span>
              <span className="text-xs text-fg-muted">
                {rows.filter((row) => row.kept).length} of {rows.length} selected
              </span>
            </div>

            <div className="overflow-hidden rounded-lg border border-line/60" onKeyDown={handleListKeys}>
              <table className="w-full table-fixed border-collapse">
                <colgroup>
                  <col className="w-12" />
                  <col className="w-[34%]" />
                  <col className="w-[40%]" />
                  <col className="w-[26%]" />
                </colgroup>
                <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-fg-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Keep
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Field
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Value
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Where from
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <FieldRow
                      key={row.field_name}
                      field={fields[index]}
                      kept={row.kept}
                      value={row.value}
                      selected={focused === index}
                      rowId={`field-row-${index}`}
                      onToggle={(kept) => update(index, { kept })}
                      onValueChange={(value) => update(index, { value })}
                      onSelect={() => setFocused(index)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <Button type="button" onClick={handleSubmit} disabled={busy}>
            {busy ? "Filling…" : "Fill the form"}
          </Button>

          {error && <Notice tone="error">{error}</Notice>}
        </div>

        {preview && (
          <div className="space-y-2 lg:order-3">
            <span className="text-xs uppercase tracking-wide text-fg-muted">
              Filled form
            </span>
            <FormPreview {...preview} />
          </div>
        )}
      </div>
    </section>
  );
}
