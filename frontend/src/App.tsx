import { useEffect, useRef, useState } from "react";

import type { ExtractedField, ExtractionResult } from "./api";
import DoneStep from "./steps/DoneStep";
import ReviewStep from "./steps/ReviewStep";
import StartStep from "./steps/StartStep";
import UploadStep from "./steps/UploadStep";

type Step = "start" | "upload" | "review" | "done";

/** Must match the `fade-out` animation in tailwind.config.js. */
const FADE_OUT_MS = 160;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

export default function App() {
  const [step, setStep] = useState<Step>("start");
  const [leaving, setLeaving] = useState(false);
  const [clientName, setClientName] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [unmatchedFields, setUnmatchedFields] = useState<string[]>([]);

  const timer = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    []
  );

  /** Fade the current step out, swap it, and let the new one fade in. */
  function goTo(next: Step) {
    if (prefersReducedMotion()) {
      setStep(next);
      return;
    }
    setLeaving(true);
    timer.current = window.setTimeout(() => {
      setStep(next);
      setLeaving(false);
    }, FADE_OUT_MS);
  }

  function restart() {
    setClientName("");
    setSessionId("");
    setFields([]);
    setDownloadUrl("");
    setUnmatchedFields([]);
    goTo("start");
  }

  function handleExtracted(result: ExtractionResult) {
    setSessionId(result.session_id);
    setFields(result.extracted_fields);
    goTo("review");
  }

  function renderStep() {
    switch (step) {
      case "start":
        return (
          <StartStep
            onReady={(name) => {
              setClientName(name);
              goTo("upload");
            }}
          />
        );
      case "upload":
        return <UploadStep clientName={clientName} onExtracted={handleExtracted} />;
      case "review":
        return (
          <ReviewStep
            sessionId={sessionId}
            fields={fields}
            onDone={(url, unmatched) => {
              setDownloadUrl(url);
              setUnmatchedFields(unmatched);
              goTo("done");
            }}
          />
        );
      case "done":
        return (
          <DoneStep
            downloadUrl={downloadUrl}
            unmatchedFields={unmatchedFields}
            onRestart={restart}
          />
        );
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center p-6">
      <div className={step === "review" ? "w-full max-w-6xl" : "w-full max-w-3xl"}>
        <header className="mb-6 flex items-center gap-3">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 rounded-full bg-accent"
          />
          <span className="text-sm font-semibold uppercase tracking-[0.22em] text-accent">
            FormFlow
          </span>
        </header>

        <div className="rounded-2xl border border-line/60 bg-card p-8 shadow-2xl shadow-black/40">
          <div key={step} className={leaving ? "animate-fade-out" : "animate-fade-in"}>
            {renderStep()}
          </div>
        </div>
      </div>
    </main>
  );
}
