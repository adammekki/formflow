import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import * as api from "../api";
import UploadStep from "./UploadStep";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, extract: vi.fn() };
});

const PDF = () => new File(["x"], "a.pdf", { type: "application/pdf" });

it("shows a plain retryable message when the backend fails", async () => {
  vi.mocked(api.extract).mockRejectedValue(new api.ApiError("Could not read the receipts"));

  render(<UploadStep clientName="uni-hamburg" onExtracted={vi.fn()} />);

  await userEvent.upload(screen.getByLabelText(/receipts/i), PDF());
  await userEvent.click(screen.getByRole("button", { name: /upload|extract/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(/could not read the receipts/i);
});

it("cannot be submitted twice while running", async () => {
  let resolve!: (value: api.ExtractionResult) => void;
  vi.mocked(api.extract).mockReturnValue(
    new Promise((r) => {
      resolve = r;
    })
  );

  render(<UploadStep clientName="uni-hamburg" onExtracted={vi.fn()} />);

  await userEvent.upload(screen.getByLabelText(/receipts/i), PDF());
  const button = screen.getByRole("button", { name: /upload|extract/i });
  await userEvent.click(button);

  expect(button).toBeDisabled();
  expect(api.extract).toHaveBeenCalledTimes(1);

  resolve({ session_id: "s1", extracted_fields: [] });
});
