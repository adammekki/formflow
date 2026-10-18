import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import * as api from "./api";
import App from "./App";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    listClients: vi.fn(),
    extract: vi.fn(),
    verify: vi.fn(),
    getSession: vi.fn(),
    getTemplate: vi.fn(),
  };
});

it("walks from picker to download", async () => {
  vi.mocked(api.listClients).mockResolvedValue([
    { name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true },
  ]);
  vi.mocked(api.extract).mockResolvedValue({
    session_id: "s1",
    extracted_fields: [
      {
        field_name: "Name",
        value: "Müller",
        source_document: "Rechnung.pdf",
        bounding_box: null,
        confidence: 0.9,
        reasoning: null,
      },
    ],
  });
  vi.mocked(api.getSession).mockResolvedValue({
    session_id: "s1",
    client_name: "uni-hamburg",
    field_count: 1,
    documents: [{ name: "Rechnung.pdf", page_count: 1 }],
  });
  vi.mocked(api.getTemplate).mockResolvedValue({
    pages: [{ page: 0, width: 100, height: 100 }],
    fields: [],
  });
  vi.mocked(api.verify).mockResolvedValue({
    download_url: "/api/extract/download/uni-hamburg/f.pdf",
  });

  render(<App />);

  await userEvent.selectOptions(await screen.findByRole("combobox"), "uni-hamburg");
  await userEvent.click(screen.getByRole("button", { name: /continue|start/i }));

  // Steps are swapped behind a fade, so wait for the next screen to appear.
  await userEvent.upload(
    await screen.findByLabelText(/receipts/i),
    new File(["x"], "a.pdf", { type: "application/pdf" })
  );
  await userEvent.click(screen.getByRole("button", { name: /upload|extract/i }));

  // The extracted value is confident, so it arrives already ticked.
  await userEvent.click(await screen.findByRole("button", { name: /finish|fill/i }));

  expect(await screen.findByRole("link", { name: /download/i })).toBeTruthy();
});

it("never shows developer terms", async () => {
  vi.mocked(api.listClients).mockResolvedValue([
    { name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true },
  ]);

  const { container } = render(<App />);
  await screen.findByRole("combobox");

  const text = container.textContent!.toLowerCase();
  for (const term of ["config", "client", "schema", "session"]) {
    expect(text).not.toContain(term);
  }
});
