import { useEffect, useState } from "react";

import { confirmSchema, discoverSchema, listClients, type Client, type Proposal } from "../api";
import Button from "../components/Button";
import Notice from "../components/Notice";

function messageOf(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

const INPUT =
  "w-full rounded-lg border border-line bg-muted px-3 py-2 text-fg transition-colors placeholder:text-fg-muted/50 focus:border-accent";

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
    <section className="space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-accent-soft">
          Which university is this for?
        </h1>
        <p className="text-fg-muted">
          Pick yours from the list, or add it if it is not there yet.
        </p>
      </div>

      <div className="space-y-2">
        <label htmlFor="university" className="block text-sm font-medium text-fg-muted">
          University
        </label>
        <select
          id="university"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className={INPUT}
        >
          <option value="">Choose a university…</option>
          {clients.map((client) => (
            <option key={client.name} value={client.name}>
              {client.institution_name}
            </option>
          ))}
        </select>
      </div>

      <Button type="button" onClick={() => selected && onReady(selected)} disabled={!selected}>
        Continue
      </Button>

      <div className="space-y-4 border-t border-line/60 pt-6">
        <Button variant="link" type="button" onClick={() => setShowNew((open) => !open)}>
          My university isn't listed
        </Button>

        {showNew && (
          <div className="space-y-5 rounded-lg border border-line/60 bg-muted/40 p-5">
            <div className="space-y-2">
              <label htmlFor="blank-form" className="block text-sm font-medium text-fg-muted">
                Upload the blank expense form
              </label>
              <input
                id="blank-form"
                type="file"
                accept="application/pdf"
                onChange={handleFile}
                disabled={busy}
                className="block w-full text-sm text-fg-muted file:mr-3 file:rounded-md file:border-0 file:bg-line file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-fg"
              />
              <p className="text-xs text-fg-muted">
                An empty PDF form, not a scan of a filled one.
              </p>
            </div>

            {proposal && (
              <div className="space-y-2">
                <label
                  htmlFor="institution-name"
                  className="block text-sm font-medium text-fg-muted"
                >
                  University name
                </label>
                <input
                  id="institution-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className={INPUT}
                />
                <Button type="button" onClick={handleConfirm} disabled={busy}>
                  Save this university
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {error && <Notice tone="error">{error}</Notice>}
    </section>
  );
}
