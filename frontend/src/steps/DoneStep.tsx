import { apiUrl } from "../api";
import Button from "../components/Button";
import Notice from "../components/Notice";

type Props = {
  downloadUrl: string;
  onRestart: () => void;
  unmatchedFields?: string[];
};

export default function DoneStep({ downloadUrl, onRestart, unmatchedFields = [] }: Props) {
  return (
    <section className="space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-accent-soft">Your form is ready</h1>
        <p className="text-fg-muted">
          Download it, then send it off the way your university expects.
        </p>
      </div>

      <a
        href={apiUrl(downloadUrl)}
        className="inline-block rounded-lg bg-accent px-4 py-2 font-semibold text-surface transition-colors hover:bg-accent-strong"
      >
        Download the filled form
      </a>

      {unmatchedFields.length > 0 && (
        <Notice tone="warning">
          Some of your values could not be placed on the form — please check it before sending.
        </Notice>
      )}

      <p className="text-sm text-fg-muted">
        Something wrong with the result? Send it back to whoever handles your expenses.
      </p>

      <Button variant="link" type="button" onClick={onRestart}>
        Start another form
      </Button>
    </section>
  );
}
