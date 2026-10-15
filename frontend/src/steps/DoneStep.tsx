import { apiUrl } from "../api";

type Props = {
  downloadUrl: string;
  onRestart: () => void;
};

export default function DoneStep({ downloadUrl, onRestart }: Props) {
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Your form is ready</h1>
        <p className="mt-1 text-slate-600">
          Download it, then send it off the way your university expects.
        </p>
      </div>

      <a
        href={apiUrl(downloadUrl)}
        className="inline-block rounded-md bg-slate-900 px-4 py-2 text-white"
      >
        Download the filled form
      </a>

      <p className="text-sm text-slate-500">
        Something wrong with the result? Send it back to whoever handles your expenses.
      </p>

      <button
        type="button"
        onClick={onRestart}
        className="text-sm font-medium text-slate-700 underline"
      >
        Start another form
      </button>
    </section>
  );
}
