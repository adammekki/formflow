import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import * as api from "../api";
import StartStep from "./StartStep";

// Only the network calls are mocked: the real ApiError class is kept so the
// components' error handling is exercised for real.
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    listClients: vi.fn(),
    discoverSchema: vi.fn(),
    confirmSchema: vi.fn(),
  };
});

it("lets an existing university be chosen", async () => {
  vi.mocked(api.listClients).mockResolvedValue([
    { name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true },
  ]);
  const onReady = vi.fn();

  render(<StartStep onReady={onReady} />);

  await userEvent.selectOptions(await screen.findByRole("combobox"), "uni-hamburg");
  await userEvent.click(screen.getByRole("button", { name: /continue|start/i }));

  expect(onReady).toHaveBeenCalledWith("uni-hamburg");
});

it("blocks confirming a blank institution name", async () => {
  vi.mocked(api.listClients).mockResolvedValue([]);
  vi.mocked(api.discoverSchema).mockResolvedValue({
    proposal_id: "p1",
    institution_name: "Universität Hamburg",
    form_title: "x",
    form_language: "German",
    field_count: 1,
    fields: [],
  });

  render(<StartStep onReady={vi.fn()} />);

  await userEvent.click(
    await screen.findByRole("button", { name: /not listed|my university/i })
  );
  await userEvent.upload(
    screen.getByLabelText(/blank|empty/i),
    new File(["x"], "f.pdf", { type: "application/pdf" })
  );

  const name = await screen.findByLabelText(/name/i);
  await userEvent.clear(name);
  await userEvent.click(screen.getByRole("button", { name: /confirm|save/i }));

  expect(screen.getByRole("alert")).toBeTruthy();
  expect(api.confirmSchema).not.toHaveBeenCalled();
});
