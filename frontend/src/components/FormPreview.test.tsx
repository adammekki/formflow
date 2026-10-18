import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import FormPreview, { type PreviewBox } from "./FormPreview";

const NAME_BOX: PreviewBox = {
  key: "Name",
  label: "Name",
  box: { page: 0, x: 100, y: 50, width: 200, height: 25 },
  selected: false,
};

function loadImage(alt: string) {
  const img = screen.getByAltText(alt);
  Object.defineProperty(img, "naturalWidth", { value: 1000 });
  Object.defineProperty(img, "naturalHeight", { value: 500 });
  fireEvent.load(img);
  return img;
}

it("draws a labelled target box where a value will be written", () => {
  render(<FormPreview imageUrl="/t.jpg" page={0} boxes={[NAME_BOX]} />);
  loadImage("Form page 1");

  const box = screen.getByTestId("target-box-Name");
  expect(box.style.left).toBe("10%");
  expect(box.style.top).toBe("10%");
  expect(box.style.width).toBe("20%");
  expect(box.style.height).toBe("5%");
  expect(screen.getByText("Name")).toBeTruthy();
});

it("marks the target box of the selected field", () => {
  const unselected = render(<FormPreview imageUrl="/t.jpg" page={0} boxes={[NAME_BOX]} />);
  loadImage("Form page 1");
  expect(screen.getByTestId("target-box-Name").getAttribute("data-selected")).toBe("false");
  unselected.unmount();

  render(
    <FormPreview imageUrl="/t.jpg" page={0} boxes={[{ ...NAME_BOX, selected: true }]} />
  );
  loadImage("Form page 1");
  expect(screen.getByTestId("target-box-Name").getAttribute("data-selected")).toBe("true");
});

it("shows the page without boxes when nothing will be filled there", () => {
  render(<FormPreview imageUrl="/t.jpg" page={1} boxes={[]} />);

  expect(loadImage("Form page 2")).toBeTruthy();
  expect(screen.queryByTestId(/^target-box-/)).toBeNull();
});
