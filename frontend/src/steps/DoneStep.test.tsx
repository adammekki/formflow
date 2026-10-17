import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import DoneStep from "./DoneStep";

it("offers the filled form as a download", () => {
  render(
    <DoneStep downloadUrl="/api/extract/download/uni-hamburg/f.pdf" onRestart={vi.fn()} />
  );

  expect(screen.getByRole("link", { name: /download/i })).toHaveAttribute(
    "href",
    expect.stringContaining("/api/extract/download/uni-hamburg/f.pdf")
  );
});

it("shows a static reassurance note and can restart", async () => {
  const onRestart = vi.fn();
  render(<DoneStep downloadUrl="/x" onRestart={onRestart} />);

  expect(screen.getByText(/something wrong/i)).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: /start|another/i }));
  expect(onRestart).toHaveBeenCalled();
});

it("warns when some values could not be placed on the form", () => {
  render(
    <DoneStep downloadUrl="/x" onRestart={vi.fn()} unmatchedFields={["UHD", "Personalnummer"]} />
  );

  expect(screen.getByText(/could not be placed/i)).toBeTruthy();
});

it("stays quiet when everything was placed", () => {
  render(<DoneStep downloadUrl="/x" onRestart={vi.fn()} unmatchedFields={[]} />);

  expect(screen.queryByText(/could not be placed/i)).toBeNull();
});
