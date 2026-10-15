import { useState } from "react";

import type { ExtractedField, ExtractionResult } from "./api";
import DoneStep from "./steps/DoneStep";
import ReviewStep from "./steps/ReviewStep";
import StartStep from "./steps/StartStep";
import UploadStep from "./steps/UploadStep";

type Step = "start" | "upload" | "review" | "done";

export default function App() {
  const [step, setStep] = useState<Step>("start");
  const [clientName, setClientName] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [downloadUrl, setDownloadUrl] = useState("");

  function restart() {
    setClientName("");
    setSessionId("");
    setFields([]);
    setDownloadUrl("");
    setStep("start");
  }

  function handleExtracted(result: ExtractionResult) {
    setSessionId(result.session_id);
    setFields(result.extracted_fields);
    setStep("review");
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <header className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          FormFlow
        </p>
      </header>

      {step === "start" && (
        <StartStep
          onReady={(name) => {
            setClientName(name);
            setStep("upload");
          }}
        />
      )}

      {step === "upload" && (
        <UploadStep clientName={clientName} onExtracted={handleExtracted} />
      )}

      {step === "review" && (
        <ReviewStep
          sessionId={sessionId}
          fields={fields}
          onDone={(url) => {
            setDownloadUrl(url);
            setStep("done");
          }}
        />
      )}

      {step === "done" && <DoneStep downloadUrl={downloadUrl} onRestart={restart} />}
    </main>
  );
}
