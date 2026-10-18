import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";

import FormPreview, { type PreviewBox } from "./FormPreview";

const PAGE = { page: 0, imageUrl: "/t.jpg" };

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
  render(<FormPreview pages={[PAGE]} boxes={[NAME_BOX]} />);
  loadImage("Form page 1");

  const box = screen.getByTestId("target-box-Name");
  expect(box.style.left).toBe("10%");
  expect(box.style.top).toBe("10%");
  expect(box.style.width).toBe("20%");
  expect(box.style.height).toBe("5%");
  expect(screen.getByText("Name")).toBeTruthy();
});

it("marks the target box of the selected field", () => {
  const first = render(<FormPreview pages={[PAGE]} boxes={[NAME_BOX]} />);
  loadImage("Form page 1");
  expect(screen.getByTestId("target-box-Name").getAttribute("data-selected")).toBe("false");
  first.unmount();

  render(<FormPreview pages={[PAGE]} boxes={[{ ...NAME_BOX, selected: true }]} />);
  loadImage("Form page 1");
  expect(screen.getByTestId("target-box-Name").getAttribute("data-selected")).toBe("true");
});

it("stacks every page so the whole form can be scrolled", () => {
  render(
    <FormPreview
      pages={[
        { page: 0, imageUrl: "/a.jpg" },
        { page: 1, imageUrl: "/b.jpg" },
      ]}
      boxes={[{ ...NAME_BOX, box: { ...NAME_BOX.box, page: 1 } }]}
    />
  );

  expect(screen.getByAltText("Form page 1")).toBeTruthy();
  loadImage("Form page 2");

  expect(
    within(screen.getByTestId("template-page-1")).getByTestId("target-box-Name")
  ).toBeTruthy();
});

it("shows a page without boxes when nothing will be filled there", () => {
  render(<FormPreview pages={[{ page: 1, imageUrl: "/b.jpg" }]} boxes={[]} />);

  expect(loadImage("Form page 2")).toBeTruthy();
  expect(screen.queryByTestId(/^target-box-/)).toBeNull();
});
