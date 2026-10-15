import { useEffect, useState } from "react";

import { confirmSchema, discoverSchema, listClients, type Client, type Proposal } from "../api";

function messageOf(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

type Props = {
  onReady: (clientName: string) => void;
};

export default function StartStep({ onReady }: Props) {
  const [clients, setClients] = useState<Client[]>([]);
  const [selected, setSelected] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listClients()
      .then(setClients)
      .catch((e) => setError(messageOf(e)));
  }, []);

  async function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setBusy(true);
    setError(null);
    try {
      const result = await discoverSchema(file);
      setProposal(result);
      setName(result.institution_name);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!proposal) return;
    if (!name.trim()) {
      setError("Please enter the university's name.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const saved = await confirmSchema(proposal.proposal_id, name.trim());
      onReady(saved.client_name);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Which university is this for?</h1>
        <p className="mt-1 text-slate-600">
          Pick yours from the list, or add it if it is not there yet.
        </p>
      </div>

      <div className="space-y-2">
        <label htmlFor="university" className="block text-sm font-medium text-slate-700">
          University
        </label>
        <select
          id="university"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white p-2"
        >
          <option value="">Choose a university…</option>
          {clients.map((client) => (
            <option key={client.name} value={client.name}>
              {client.institution_name}
            </option>
          ))}
        </select>
      </div>

      <button
        type="button"
        onClick={() => selected && onReady(selected)}
        disabled={!selected}
        className="rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
      >
        Continue
      </button>

      <div className="border-t border-slate-200 pt-6">
        <button
          type="button"
          onClick={() => setShowNew((open) => !open)}
          className="text-sm font-medium text-slate-700 underline"
        >
          My university isn't listed
        </button>

        {showNew && (
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <label htmlFor="blank-form" className="block text-sm font-medium text-slate-700">
                Upload the blank expense form
              </label>
              <input
                id="blank-form"
                type="file"
                accept="application/pdf"
                onChange={handleFile}
                disabled={busy}
                className="block w-full text-sm"
              />
              <p className="text-xs text-slate-500">
                An empty PDF form, not a scan of a filled one.
              </p>
            </div>

            {proposal && (
              <div className="space-y-2">
                <label
                  htmlFor="institution-name"
                  className="block text-sm font-medium text-slate-700"
                >
                  University name
                </label>
                <input
                  id="institution-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-md border border-slate-300 p-2"
                />
                <button
                  type="button"
                  onClick={handleConfirm}
                  disabled={busy}
                  className="rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
                >
                  Save this university
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
