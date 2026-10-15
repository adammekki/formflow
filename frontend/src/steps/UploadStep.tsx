import { useState } from "react";

import { extract, type ExtractionResult } from "../api";

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
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Add your receipts</h1>
        <p className="mt-1 text-slate-600">
          Drop in everything from the trip — several files are fine, they are read together.
        </p>
      </div>

      <div className="space-y-2">
        <label htmlFor="receipts" className="block text-sm font-medium text-slate-700">
          Receipts
        </label>
        <input
          id="receipts"
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.tiff"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          disabled={busy}
          className="block w-full rounded-md border border-dashed border-slate-300 p-6 text-sm"
        />
      </div>

      <button
        type="button"
        onClick={handleUpload}
        disabled={busy || files.length === 0}
        className="rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
      >
        {busy ? "Reading…" : "Upload and read receipts"}
      </button>

      {busy && (
        <p className="text-sm text-slate-600">
          Reading your receipts — this can take a few minutes.
        </p>
      )}

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
