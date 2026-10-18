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

  // Keep the selected row, and the page holding its box, in view.
  useEffect(() => {
    if (focused === null) return;
    document.getElementById(`field-row-${focused}`)?.scrollIntoView?.({ block: "nearest" });
    const field = fields[focused];
    const box = field?.bounding_box;
    if (box) {
      document.getElementById(`source-page-${box.page}`)?.scrollIntoView?.({ block: "nearest" });
    }
    const target = template?.fields.find((f) => f.field_name === field?.field_name);
    if (target) {
      document
        .getElementById(`preview-page-${target.page}`)
        ?.scrollIntoView?.({ block: "nearest" });
    }
  }, [focused, fields, template]);

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

  /** Every page of the selected field's document, boxed on the page it came from. */
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
    const document = documents[docIndex];
    return {
      documentName: document.name,
      pages: Array.from({ length: document.page_count }, (_, page) => ({
        page,
        imageUrl: pageImageUrl(sessionId, docIndex, page),
        box: box && box.page === page ? box : null,
      })),
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

  /** The whole form, with only the selected field's target line boxed. */
  function previewTarget() {
    if (!template || template.pages.length === 0) {
      return null;
    }
    // One box at a time: showing every suggestion at once makes it harder to
    // work through them.
    const field = focused === null ? undefined : fields[focused];
    const kept = focused === null ? false : rows[focused]?.kept;
    const target =
      field && kept ? template.fields.find((f) => f.field_name === field.field_name) : undefined;
    const boxes = target && field
      ? [{ key: target.field_name, label: fieldLabel(field), box: target, selected: true }]
      : [];
    return {
      pages: template.pages.map((page) => ({
        page: page.page,
        imageUrl: templatePageUrl(sessionId, page.page),
      })),
      boxes,
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

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr_1.4fr]">
        {target && (
          <div className="min-w-0 space-y-2 lg:order-1 order-2 lg:sticky lg:top-3 lg:self-start">
            <span className="text-xs uppercase tracking-wide text-fg-muted">
              Source document
            </span>
            <div className="max-h-[70vh] space-y-3 overflow-auto lg:max-h-none lg:h-[calc(100vh-7rem)]">
              {target.pages.map((page) => (
                <DocumentViewer
                  key={page.page}
                  documentName={target.documentName}
                  pageId={`source-page-${page.page}`}
                  {...page}
                />
              ))}
            </div>
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
          <div className="min-w-0 space-y-2 lg:order-3 lg:sticky lg:top-3 lg:self-start">
            <span className="text-xs uppercase tracking-wide text-fg-muted">
              Filled form
            </span>
            <div className="max-h-[70vh] overflow-auto lg:max-h-none lg:h-[calc(100vh-7rem)]">
              <FormPreview {...preview} />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
