import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import * as api from "../api";
import ReviewStep from "./ReviewStep";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, verify: vi.fn() };
});

const FIELDS: api.ExtractedField[] = [
  {
    field_name: "Name",
    value: "Müller",
    source_document: "Rechnung.pdf",
    confidence: 0.9,
    reasoning: null,
  },
  {
    field_name: "IBAN",
    value: "",
    source_document: "Rechnung.pdf",
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
  await userEvent.click(screen.getByRole("button", { name: /finish|fill/i }));

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
  await userEvent.click(screen.getByRole("button", { name: /finish|fill/i }));

  expect(api.verify).toHaveBeenCalledWith({
    sessionId: "s1",
    verifiedFields: {},
    keptFields: [],
  });
});
