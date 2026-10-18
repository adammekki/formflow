import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import * as api from "../api";
import ReviewStep from "./ReviewStep";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, verify: vi.fn(), getSession: vi.fn(), getTemplate: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api.getSession).mockResolvedValue({
    session_id: "s1",
    client_name: "c",
    field_count: 2,
    documents: [{ name: "Rechnung.pdf", page_count: 1 }],
  });
  vi.mocked(api.getTemplate).mockResolvedValue({
    pages: [{ page: 0, width: 1000, height: 500 }],
    fields: [],
  });
});

const FIELDS: api.ExtractedField[] = [
  {
    field_name: "Name",
    value: "Müller",
    source_document: "Rechnung.pdf",
    bounding_box: null,
    confidence: 0.9,
    reasoning: null,
  },
  {
    field_name: "IBAN",
    value: "",
    source_document: "Rechnung.pdf",
    bounding_box: null,
    confidence: 0.2,
    reasoning: null,
  },
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
  await userEvent.click(screen.getByRole("button", { name: /^fill the form$/i }));

  // Name is ticked by default (confidence 0.9); IBAN is not (0.2, empty).
  expect(api.verify).toHaveBeenCalledWith({
    sessionId: "s1",
    verifiedFields: { Name: "Müller, Jörg" },
    keptFields: ["Name"],
  });
});

it("leaves an unticked field out of the payload", async () => {
  vi.mocked(api.verify).mockResolvedValue({ download_url: "/api/extract/download/x/y.pdf" });

  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={vi.fn()} />);

  // Name is ticked by default; unticking it is what the user does to drop a field.
  await userEvent.click(screen.getByRole("checkbox", { name: /keep name/i }));
  await userEvent.click(screen.getByRole("button", { name: /^fill the form$/i }));

  expect(api.verify).toHaveBeenCalledWith({
    sessionId: "s1",
    verifiedFields: {},
    keptFields: [],
  });
});

it("shows the plain-language name when the form gives one", () => {
  const fields: api.ExtractedField[] = [
    {
      field_name: "UHD",
      semantic_name: "Personnel number",
      value: "12345",
      source_document: "Rechnung.pdf",
      bounding_box: null,
      confidence: 0.9,
      reasoning: null,
    },
  ];

  render(<ReviewStep sessionId="s1" fields={fields} onDone={vi.fn()} />);

  expect(screen.getByLabelText("Personnel number")).toBeTruthy();
});

it("lays the fields out as a grid with column headings", () => {
  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={vi.fn()} />);

  for (const heading of ["Keep", "Field", "Value", "Where from"]) {
    expect(screen.getByRole("columnheader", { name: heading })).toBeTruthy();
  }
});

it("says how many values will be filled, and keeps that count current", async () => {
  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={vi.fn()} />);

  expect(screen.getByText(/1 of 2 selected/i)).toBeTruthy();

  await userEvent.click(screen.getByRole("checkbox", { name: /keep name/i }));

  expect(screen.getByText(/0 of 2 selected/i)).toBeTruthy();
});

it("shows the focused field's page and box in the viewer", async () => {
  const boxed: api.ExtractedField[] = [
    {
      ...FIELDS[0],
      bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 },
    },
  ];

  render(<ReviewStep sessionId="s1" fields={boxed} onDone={vi.fn()} />);

  await userEvent.click(await screen.findByLabelText("Name"));

  const img = await screen.findByAltText("Page 1 of Rechnung.pdf");
  // jsdom never fires image loads; the browser does, which is what the
  // overlay's percentage positions depend on.
  Object.defineProperty(img, "naturalWidth", { value: 1000 });
  Object.defineProperty(img, "naturalHeight", { value: 500 });
  fireEvent.load(img);

  expect(screen.getByTestId("bbox-overlay")).toBeTruthy();
});

it("follows keyboard focus into the viewer", async () => {
  const boxed: api.ExtractedField[] = [
    {
      ...FIELDS[0],
      bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 },
    },
  ];

  render(<ReviewStep sessionId="s1" fields={boxed} onDone={vi.fn()} />);

  fireEvent.focus(await screen.findByRole("checkbox", { name: /keep name/i }));

  const img = await screen.findByAltText("Page 1 of Rechnung.pdf");
  Object.defineProperty(img, "naturalWidth", { value: 1000 });
  Object.defineProperty(img, "naturalHeight", { value: 500 });
  fireEvent.load(img);

  expect(screen.getByTestId("bbox-overlay")).toBeTruthy();
});

it("marks the selected row so the viewer's field is obvious", async () => {
  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={vi.fn()} />);

  const row = await screen.findByRole("row", { name: /Name/ });
  expect(row.getAttribute("aria-selected")).toBe("false");

  fireEvent.focus(screen.getByRole("checkbox", { name: /keep name/i }));

  expect(row.getAttribute("aria-selected")).toBe("true");
});

it("moves the selection with the arrow keys", async () => {
  const boxed: api.ExtractedField[] = [
    { ...FIELDS[0], bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 } },
    { ...FIELDS[1], value: "DE89 3704", bounding_box: { page: 0, x: 5, y: 6, width: 20, height: 8 } },
  ];
  render(<ReviewStep sessionId="s1" fields={boxed} onDone={vi.fn()} />);
  const checkbox = await screen.findByRole("checkbox", { name: /keep name/i });

  fireEvent.focus(checkbox);
  fireEvent.keyDown(checkbox, { key: "ArrowDown" });

  expect(screen.getByRole("row", { name: /IBAN/ }).getAttribute("aria-selected")).toBe("true");

  fireEvent.keyDown(checkbox, { key: "ArrowUp" });

  expect(screen.getByRole("row", { name: /Name/ }).getAttribute("aria-selected")).toBe("true");
});

it("takes keyboard focus when a row is clicked so arrows work", async () => {
  const boxed: api.ExtractedField[] = [
    { ...FIELDS[0], bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 } },
    { ...FIELDS[1], value: "DE89 3704" },
  ];
  render(<ReviewStep sessionId="s1" fields={boxed} onDone={vi.fn()} />);

  const row = await screen.findByRole("row", { name: /Name/ });
  // Click a plain cell, not the value input, like a user aiming at the row.
  await userEvent.click(screen.getByText(/90% confident/));

  expect(document.activeElement).toBe(row);

  fireEvent.keyDown(row, { key: "ArrowDown" });

  expect(screen.getByRole("row", { name: /IBAN/ }).getAttribute("aria-selected")).toBe("true");
});

it("keeps arrow keys inside the box while typing a value", async () => {
  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={vi.fn()} />);

  fireEvent.focus(screen.getByRole("checkbox", { name: /keep name/i }));
  fireEvent.keyDown(screen.getByLabelText("Name"), { key: "ArrowDown" });

  expect(screen.getByRole("row", { name: /Name/ }).getAttribute("aria-selected")).toBe("true");
});

function loadFormPreview() {
  const img = screen.getByAltText("Form page 1");
  Object.defineProperty(img, "naturalWidth", { value: 1000 });
  Object.defineProperty(img, "naturalHeight", { value: 500 });
  fireEvent.load(img);
}

it("stacks every page of the selected field's document", async () => {
  vi.mocked(api.getSession).mockResolvedValue({
    session_id: "s1",
    client_name: "c",
    field_count: 1,
    documents: [{ name: "Rechnung.pdf", page_count: 3 }],
  });
  const fields: api.ExtractedField[] = [
    { ...FIELDS[0], bounding_box: { page: 2, x: 10, y: 20, width: 100, height: 30 } },
  ];
  render(<ReviewStep sessionId="s1" fields={fields} onDone={vi.fn()} />);

  await userEvent.click(await screen.findByLabelText("Name"));

  expect(await screen.findByAltText("Page 1 of Rechnung.pdf")).toBeTruthy();
  expect(screen.getByAltText("Page 2 of Rechnung.pdf")).toBeTruthy();
  const third = screen.getByAltText("Page 3 of Rechnung.pdf");

  // jsdom never fires image loads, and the overlay waits for natural size.
  Object.defineProperty(third, "naturalWidth", { value: 1000 });
  Object.defineProperty(third, "naturalHeight", { value: 500 });
  fireEvent.load(third);

  // The box belongs to page 3 (index 2), where the value came from.
  expect(within(document.getElementById("source-page-2")!).getByTestId("bbox-overlay")).toBeTruthy();
  expect(screen.getAllByTestId("bbox-overlay")).toHaveLength(1);
});

it("stacks every page of the form template", async () => {
  vi.mocked(api.getTemplate).mockResolvedValue({
    pages: [
      { page: 0, width: 10, height: 10 },
      { page: 1, width: 10, height: 10 },
    ],
    fields: [{ field_name: "Name", page: 1, x: 1, y: 1, width: 2, height: 2 }],
  });
  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={vi.fn()} />);

  await userEvent.click(await screen.findByLabelText("Name"));

  expect(await screen.findByAltText("Form page 1")).toBeTruthy();
  expect(screen.getByAltText("Form page 2")).toBeTruthy();
});

it("shows where the selected field will be written on the form", async () => {
  vi.mocked(api.getTemplate).mockResolvedValue({
    pages: [{ page: 0, width: 1000, height: 500 }],
    fields: [{ field_name: "Name", page: 0, x: 100, y: 50, width: 200, height: 25 }],
  });
  const fields: api.ExtractedField[] = [
    { ...FIELDS[0], bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 } },
  ];
  render(<ReviewStep sessionId="s1" fields={fields} onDone={vi.fn()} />);

  await userEvent.click(await screen.findByLabelText("Name"));
  await screen.findByAltText("Form page 1");
  loadFormPreview();

  expect(screen.getByTestId("target-box-Name")).toBeTruthy();
});

it("shows only the selected field's target line, not every suggestion", async () => {
  vi.mocked(api.getTemplate).mockResolvedValue({
    pages: [{ page: 0, width: 1000, height: 500 }],
    fields: [
      { field_name: "Name", page: 0, x: 10, y: 20, width: 100, height: 20 },
      { field_name: "IBAN", page: 0, x: 10, y: 60, width: 100, height: 20 },
    ],
  });
  const fields: api.ExtractedField[] = [
    { ...FIELDS[0], bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 } },
    { ...FIELDS[1], value: "DE89 3704" },
  ];
  render(<ReviewStep sessionId="s1" fields={fields} onDone={vi.fn()} />);

  await userEvent.click(await screen.findByLabelText("Name"));
  await screen.findByAltText("Form page 1");
  loadFormPreview();
  expect(screen.getByTestId("target-box-Name")).toBeTruthy();
  expect(screen.queryByTestId("target-box-IBAN")).toBeNull();

  fireEvent.focus(screen.getByRole("checkbox", { name: /keep iban/i }));

  expect(screen.getByTestId("target-box-IBAN")).toBeTruthy();
  expect(screen.queryByTestId("target-box-Name")).toBeNull();
});

it("drops the target box when the field is unticked", async () => {
  vi.mocked(api.getTemplate).mockResolvedValue({
    pages: [{ page: 0, width: 1000, height: 500 }],
    fields: [{ field_name: "Name", page: 0, x: 100, y: 50, width: 200, height: 25 }],
  });
  const fields: api.ExtractedField[] = [
    { ...FIELDS[0], bounding_box: { page: 0, x: 10, y: 20, width: 100, height: 30 } },
  ];
  render(<ReviewStep sessionId="s1" fields={fields} onDone={vi.fn()} />);

  await userEvent.click(await screen.findByLabelText("Name"));
  await screen.findByAltText("Form page 1");
  loadFormPreview();
  expect(screen.getByTestId("target-box-Name")).toBeTruthy();

  await userEvent.click(screen.getByRole("checkbox", { name: /keep name/i }));

  expect(screen.queryByTestId("target-box-Name")).toBeNull();
});

it("passes values the form could not place through to the caller", async () => {
  vi.mocked(api.verify).mockResolvedValue({
    download_url: "/api/extract/download/x/y.pdf",
    unmatched_fields: ["UHD"],
  });
  const onDone = vi.fn();

  render(<ReviewStep sessionId="s1" fields={FIELDS} onDone={onDone} />);
  await userEvent.click(screen.getByRole("button", { name: /^fill the form$/i }));

  expect(onDone).toHaveBeenCalledWith("/api/extract/download/x/y.pdf", ["UHD"]);
});
