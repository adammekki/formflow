import { useState } from "react";

import { extract, type ExtractionResult } from "../api";
import Button from "../components/Button";
import Notice from "../components/Notice";

function messageOf(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

type Props = {
  clientName: string;
  onExtracted: (result: ExtractionResult) => void;
};

export default function UploadStep({ clientName, onExtracted }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (files.length === 0 || busy) return;

    setBusy(true);
    setError(null);
    try {
      const result = await extract(clientName, files);
      onExtracted(result);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-accent-soft">Add your receipts</h1>
        <p className="text-fg-muted">
          Drop in everything from the trip — several files are fine, they are read together.
        </p>
      </div>

      <div className="space-y-2">
        <label htmlFor="receipts" className="block text-sm font-medium text-fg-muted">
          Receipts
        </label>
        <input
          id="receipts"
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.tiff"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          disabled={busy}
          className="block w-full rounded-lg border border-dashed border-line bg-muted/40 p-6 text-sm text-fg-muted file:mr-3 file:rounded-md file:border-0 file:bg-line file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-fg"
        />
      </div>

      <Button type="button" onClick={handleUpload} disabled={busy || files.length === 0}>
        {busy ? "Reading…" : "Upload and read receipts"}
      </Button>

      {busy && (
        <p className="text-sm text-fg-muted">
          Reading your receipts — this can take a few minutes.
        </p>
      )}

      {error && <Notice tone="error">{error}</Notice>}
    </section>
  );
}
