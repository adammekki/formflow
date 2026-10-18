import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import ZoomControls from "./ZoomControls";

it("steps down to the next smaller zoom", async () => {
  const onChange = vi.fn();
  render(<ZoomControls zoom={1} onChange={onChange} name="source document" />);

  await userEvent.click(screen.getByRole("button", { name: /zoom out source document/i }));

  expect(onChange).toHaveBeenCalledWith(0.75);
});

it("steps up to the next larger zoom", async () => {
  const onChange = vi.fn();
  render(<ZoomControls zoom={1} onChange={onChange} name="source document" />);

  await userEvent.click(screen.getByRole("button", { name: /zoom in source document/i }));

  expect(onChange).toHaveBeenCalledWith(1.5);
});

it("stops at the largest zoom", () => {
  render(<ZoomControls zoom={3} onChange={vi.fn()} name="source document" />);

  expect(screen.getByRole("button", { name: /zoom in source document/i })).toBeDisabled();
  expect(screen.getByText("300%")).toBeTruthy();
});

it("stops at the smallest zoom", () => {
  render(<ZoomControls zoom={0.5} onChange={vi.fn()} name="filled form" />);

  expect(screen.getByRole("button", { name: /zoom out filled form/i })).toBeDisabled();
});
