# FormFlow Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a desktop web frontend for FormFlow that takes a tired traveller from "I have receipts" to "I have a filled expense form" in four short steps.

**Architecture:** A standalone React + Vite + TypeScript single-page app in `frontend/`, served as its own container. It talks to the FastAPI backend over HTTP only — no shared code, no filesystem access. One page holds a four-step state machine (`start → upload → review → done`); each step is its own component and its own test.

**Tech Stack:** React 18, Vite, TypeScript, Tailwind CSS, Vitest + Testing Library + jsdom, nginx (production image).

**Spec:** `docs/superpowers/specs/2026-10-15-formflow-frontend-design.md`
**Depends on:** `docs/superpowers/plans/2026-10-15-formflow-backend-api-changes.md` (the API contract below assumes those changes are done)

## Global Constraints

- Desktop-first. No mobile layout work; a plain centred column is enough.
- No state library and no router. `useState` in one component owns the step; components take props.
- User-visible copy must never contain "config", "client", "schema", "session", or a raw file path.
- The frontend must not import backend code or read the backend filesystem. All data arrives over HTTP.
- Backend base URL comes from `VITE_API_BASE` (default `http://localhost:8000`).
- Error messages surfaced to the user are plain sentences; never a status code, stack trace, or exception class.

## Review Focus

Failure modes the happy path does not exercise. Each gets a test in the task named in brackets.

1. The backend returns **zero extracted fields** — the review step must show an empty state, not an empty table or a crash. [Task 4]
2. The backend is **unreachable or returns 500** during extraction — the user sees a plain, retryable message. [Task 3]
3. A row is **edited and ticked** (or unticked after editing) — the submitted payload reflects both the value and the tick. [Task 4]
4. Extraction **takes minutes** — a visible loading state, and the submit control cannot be fired twice. [Task 3]
5. The user **clears the institution name** before confirming — the confirm is blocked with a clear message. [Task 2]

---

### Task 1: Scaffold and API client

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/src/api.ts`, `frontend/vitest.setup.ts`
- Test: `frontend/src/api.test.ts`

**Interfaces:**
- Produces (`src/api.ts`):
  - Types: `Client {name, institution_name, configured}`, `Proposal {proposal_id, institution_name, form_title, form_language, field_count, fields}`, `ExtractedField {field_name, value, source_document, confidence, reasoning}`, `ExtractionResult {session_id, extracted_fields}`.
  - `listClients(): Promise<Client[]>`
  - `discoverSchema(file: File): Promise<Proposal>` — throws `ApiError` when `status === "error"`
  - `confirmSchema(proposalId: string, institutionName: string): Promise<{client_name: string; institution_name: string}>`
  - `extract(clientName: string, files: File[]): Promise<ExtractionResult>`
  - `verify(input: {sessionId: string; verifiedFields: Record<string,string>; keptFields: string[]}): Promise<{download_url: string}>`
  - `apiUrl(path: string): string`
  - `class ApiError extends Error`

- [ ] **Step 1: Create the Vite app and test setup**

`npm create vite@latest frontend -- --template react-ts`, then add Tailwind, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`. In `vite.config.ts` add `test: { environment: "jsdom", setupFiles: "./vitest.setup.ts" }`. `npm test` runs `vitest run`.

- [ ] **Step 2: Write the failing test**

`src/api.test.ts` — stub `global.fetch`.

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { listClients, discoverSchema, ApiError } from "./api";

beforeEach(() => { vi.restoreAllMocks(); });

it("parses the client list", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(
    JSON.stringify({ clients: [{ name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true }] }),
    { status: 200 })));
  expect((await listClients())[0].institution_name).toBe("Universität Hamburg");
});

it("turns an error status into an ApiError", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(
    JSON.stringify({ status: "error", error: "This PDF has no fillable form fields" }), { status: 200 })));
  await expect(discoverSchema(new File(["x"], "f.pdf"))).rejects.toBeInstanceOf(ApiError);
});

it("turns a 500 into a plain ApiError", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));
  await expect(listClients()).rejects.toBeInstanceOf(ApiError);
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `./api` not found.

- [ ] **Step 4: Implement `src/api.ts`**

`apiUrl` joins `import.meta.env.VITE_API_BASE ?? "http://localhost:8000"` with the path. Each call uses `fetch`, and on a non-2xx response or a body with `status === "error"` throws `new ApiError(message)` where `message` is the backend's `detail`/`error` when present, else a fixed fallback sentence. `extract` and `discoverSchema` send `FormData`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): scaffold app and API client"
```

---

### Task 2: Start step

**Files:**
- Create: `frontend/src/steps/StartStep.tsx`
- Test: `frontend/src/steps/StartStep.test.tsx`

**Interfaces:**
- Consumes: `listClients`, `discoverSchema`, `confirmSchema` (Task 1).
- Produces: `<StartStep onReady={(clientName: string) => void} />`. `onReady` receives the university's **`client_name`** (the slug the extract API needs), never the display name. For a picked university that is the select value; for a new one it is `confirmSchema`'s `client_name`.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StartStep from "./StartStep";
import * as api from "../api";

vi.mock("../api");

it("lets an existing university be chosen", async () => {
  vi.mocked(api.listClients).mockResolvedValue([
    { name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true }]);
  const onReady = vi.fn();
  render(<StartStep onReady={onReady} />);
  await userEvent.selectOptions(await screen.findByRole("combobox"), "uni-hamburg");
  await userEvent.click(screen.getByRole("button", { name: /continue|start/i }));
  expect(onReady).toHaveBeenCalledWith("uni-hamburg");
});

it("blocks confirming a blank institution name", async () => {
  vi.mocked(api.discoverSchema).mockResolvedValue({
    proposal_id: "p1", institution_name: "Universität Hamburg", form_title: "x",
    form_language: "German", field_count: 1, fields: [] });
  render(<StartStep onReady={vi.fn()} />);
  await userEvent.click(await screen.findByRole("button", { name: /not listed|my university/i }));
  await userEvent.upload(screen.getByLabelText(/blank|empty/i), new File(["x"], "f.pdf"));
  const name = await screen.findByLabelText(/name/i);
  await userEvent.clear(name);
  await userEvent.click(screen.getByRole("button", { name: /confirm|save/i }));
  expect(screen.getByRole("alert")).toBeTruthy();
  expect(api.confirmSchema).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test src/steps/StartStep.test.tsx`
Expected: FAIL — component not found.

- [ ] **Step 3: Implement `StartStep.tsx`**

On mount, `listClients()`. Render a labelled `<select>` of universities plus a "My university isn't listed" control that reveals a file input. On upload, call `discoverSchema` and show the returned `institution_name` in a labelled editable input. Confirm calls `confirmSchema(proposal_id, name)`; block with a visible `role="alert"` when the trimmed name is empty. On success, call `onReady` with the select value (picked) or `confirmSchema`'s `client_name` (new) — always the slug.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test src/steps/StartStep.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/steps/StartStep.tsx frontend/src/steps/StartStep.test.tsx
git commit -m "feat(frontend): university picker and name confirmation"
```

---

### Task 3: Upload receipts step

**Files:**
- Create: `frontend/src/steps/UploadStep.tsx`
- Test: `frontend/src/steps/UploadStep.test.tsx`

**Interfaces:**
- Consumes: `extract` (Task 1).
- Produces: `<UploadStep clientName={string} onExtracted={(r: ExtractionResult) => void} />`.

- [ ] **Step 1: Write the failing test**

```tsx
it("shows a plain retryable message when the backend fails", async () => {
  vi.mocked(api.extract).mockRejectedValue(new api.ApiError("Could not read the receipts"));
  render(<UploadStep clientName="uni-hamburg" onExtracted={vi.fn()} />);
  await userEvent.upload(screen.getByLabelText(/receipts/i), new File(["x"], "a.pdf"));
  await userEvent.click(screen.getByRole("button", { name: /upload|extract/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/could not read the receipts/i);
});

it("cannot be submitted twice while running", async () => {
  let resolve: (v: any) => void; vi.mocked(api.extract).mockReturnValue(new Promise(r => { resolve = r; }));
  render(<UploadStep clientName="uni-hamburg" onExtracted={vi.fn()} />);
  await userEvent.upload(screen.getByLabelText(/receipts/i), new File(["x"], "a.pdf"));
  const button = screen.getByRole("button", { name: /upload|extract/i });
  await userEvent.click(button);
  expect(button).toBeDisabled();
  expect(api.extract).toHaveBeenCalledTimes(1);
  resolve!({ session_id: "s1", extracted_fields: [] });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test src/steps/UploadStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `UploadStep.tsx`**

A drop zone and a multi-file input labelled "receipts", accepting PDFs and images. While `extract` runs, disable the submit control and show a visible loading state with a line explaining that reading receipts can take a few minutes. On success call `onExtracted`. On failure show the `ApiError.message` in a `role="alert"` and re-enable the control so the user can retry.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test src/steps/UploadStep.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/steps/UploadStep.tsx frontend/src/steps/UploadStep.test.tsx
git commit -m "feat(frontend): receipt upload step"
```

---

### Task 4: Review and choose step

**Files:**
- Create: `frontend/src/steps/ReviewStep.tsx`, `frontend/src/components/FieldRow.tsx`
- Test: `frontend/src/steps/ReviewStep.test.tsx`

**Interfaces:**
- Consumes: `verify` (Task 1).
- Produces: `<ReviewStep sessionId={string} fields={ExtractedField[]} onDone={(downloadUrl: string) => void} />`. Calls `verify` with `verifiedFields` = every edited value keyed by `field_name`, and `keptFields` = the ticked `field_name`s.

- [ ] **Step 1: Write the failing test**

```tsx
const FIELDS = [
  { field_name: "Name", value: "Müller", source_document: "Rechnung.pdf", confidence: 0.9, reasoning: null },
  { field_name: "IBAN", value: "", source_document: "Rechnung.pdf", confidence: 0.2, reasoning: null },
];

it("shows an empty state when nothing was extracted", () => {
  render(<ReviewStep sessionId="s1" fields={[]} onDone={vi.fn()} />);
  expect(screen.getByText(/nothing was found/i)).toBeTruthy();
});

it("sends both the edited value and the ticks", async () => {
  vi.mocked(api.verify).mockResolvedValue({ download_url: "/api/extract/download/x/y.pdf" });
  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={vi.fn()} />);
  await userEvent.clear(screen.getByLabelText("Name"));
  await userEvent.type(screen.getByLabelText("Name"), "Müller, Jörg");
  await userEvent.click(screen.getByRole("checkbox", { name: "Name" }));
  await userEvent.click(screen.getByRole("button", { name: /finish|fill/i }));
  expect(api.verify).toHaveBeenCalledWith({
    sessionId: "s1", verifiedFields: { Name: "Müller, Jörg" }, keptFields: ["Name"] });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test src/steps/ReviewStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `FieldRow.tsx`**

One row: a checkbox labelled with the field's display name, the value in a labelled input, a confidence indicator, and the source document. Default the checkbox to ticked when `confidence >= 0.5` or the value is non-empty.

- [ ] **Step 4: Implement `ReviewStep.tsx`**

Render a `FieldRow` per field. When `fields` is empty, show a "nothing was found — try adding more receipts" empty state instead of the list. On submit, build the payload from the current row state and call `verify`, then `onDone(download_url)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test src/steps/ReviewStep.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/steps/ReviewStep.tsx frontend/src/components/FieldRow.tsx frontend/src/steps/ReviewStep.test.tsx
git commit -m "feat(frontend): review and choose extracted fields"
```

---

### Task 5: Done step

**Files:**
- Create: `frontend/src/steps/DoneStep.tsx`
- Test: `frontend/src/steps/DoneStep.test.tsx`

**Interfaces:**
- Consumes: `apiUrl` (Task 1).
- Produces: `<DoneStep downloadUrl={string} onRestart={() => void} />`.

- [ ] **Step 1: Write the failing test**

```tsx
it("offers the filled form as a download", () => {
  render(<DoneStep downloadUrl="/api/extract/download/uni-hamburg/f.pdf" onRestart={vi.fn()} />);
  expect(screen.getByRole("link", { name: /download/i }))
    .toHaveAttribute("href", expect.stringContaining("/api/extract/download/uni-hamburg/f.pdf"));
});

it("shows a static reassurance note and can restart", async () => {
  const onRestart = vi.fn();
  render(<DoneStep downloadUrl="/x" onRestart={onRestart} />);
  expect(screen.getByText(/something wrong/i)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: /start|another/i }));
  expect(onRestart).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test src/steps/DoneStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `DoneStep.tsx`**

A download link built from `apiUrl(downloadUrl)`, a short static "Something wrong with the result?" sentence, and a button returning to the start step. No feedback form.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test src/steps/DoneStep.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/steps/DoneStep.tsx frontend/src/steps/DoneStep.test.tsx
git commit -m "feat(frontend): done step with download"
```

---

### Task 6: Container and compose service

**Files:**
- Create: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.env.example`
- Modify: `docker-compose.yml` (new service), `docker-compose.prod.yml` (new service)

**Interfaces:**
- Consumes: the app's production build (`npm run build` → `dist/`).
- Produces: a `frontend` compose service reachable on port 3000.

- [ ] **Step 1: Write the Dockerfile**

Two stages: `node:20-alpine` runs `npm ci && npm run build`; `nginx:alpine` serves the resulting `dist/` and copies `nginx.conf`. Add a `HEALTHCHECK` hitting `/`.

- [ ] **Step 2: Write `nginx.conf`**

Serve the SPA with a fallback to `index.html` so deep links do not 404.

- [ ] **Step 3: Add the compose services**

Dev: run the Vite dev server with `--host` and mount the source. Prod: the built image, `ports: ["3000:80"]`, on `formflow-network`. The browser reaches the backend directly, so no proxy is added.

- [ ] **Step 4: Document the base URL**

`frontend/.env.example` holds `VITE_API_BASE=http://localhost:8000`.

- [ ] **Step 5: Verify the image builds and the app responds**

Run: `docker build -t formflow-frontend frontend`
Run: `docker run --rm -p 3000:80 formflow-frontend` then `curl -I http://localhost:3000/`
Expected: `HTTP/1.1 200 OK`.

- [ ] **Step 6: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf frontend/.env.example docker-compose.yml docker-compose.prod.yml
git commit -m "feat(frontend): container and compose service"
```

---

### Task 7: End-to-end flow test

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: all four step components and `api`.
- Produces: `<App />` — owns `clientName`, `sessionId`, `fields`, `downloadUrl`, and the current step.

- [ ] **Step 1: Write the failing test**

```tsx
it("walks from picker to download", async () => {
  vi.mocked(api.listClients).mockResolvedValue([
    { name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true }]);
  vi.mocked(api.extract).mockResolvedValue({
    session_id: "s1",
    extracted_fields: [{ field_name: "Name", value: "Müller", source_document: "Rechnung.pdf", confidence: 0.9, reasoning: null }] });
  vi.mocked(api.verify).mockResolvedValue({ download_url: "/api/extract/download/uni-hamburg/f.pdf" });

  render(<App />);
  await userEvent.selectOptions(await screen.findByRole("combobox"), "uni-hamburg");
  await userEvent.click(screen.getByRole("button", { name: /continue|start/i }));
  await userEvent.upload(screen.getByLabelText(/receipts/i), new File(["x"], "a.pdf"));
  await userEvent.click(screen.getByRole("button", { name: /upload|extract/i }));
  await userEvent.click(await screen.findByRole("checkbox", { name: "Name" }));
  await userEvent.click(screen.getByRole("button", { name: /finish|fill/i }));
  expect(await screen.findByRole("link", { name: /download/i })).toBeTruthy();
});

it("never shows developer terms", async () => {
  vi.mocked(api.listClients).mockResolvedValue([
    { name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true }]);
  const { container } = render(<App />);
  await screen.findByRole("combobox");
  const text = container.textContent!.toLowerCase();
  for (const term of ["config", "client", "schema", "session"]) {
    expect(text).not.toContain(term);
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test src/App.test.tsx`
Expected: FAIL — App still renders the Vite starter.

- [ ] **Step 3: Implement `App.tsx`**

Hold the four pieces of state and render one step at a time, passing the callbacks that advance it. `onRestart` resets to the start step.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test src/App.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the whole suite and commit**

Run: `cd frontend && npm test`
Expected: all PASS.

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): wire the four-step flow"
```
