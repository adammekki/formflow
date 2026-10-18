import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import DocumentViewer from "./DocumentViewer";

it("positions the overlay in percentages of the natural image", () => {
  render(
    <DocumentViewer
      imageUrl="/x.jpg"
      documentName="hotel.pdf"
      page={0}
      box={{ page: 0, x: 100, y: 50, width: 200, height: 25 }}
    />
  );
  const img = screen.getByAltText("Page 1 of hotel.pdf");
  Object.defineProperty(img, "naturalWidth", { value: 1000 });
  Object.defineProperty(img, "naturalHeight", { value: 500 });
  fireEvent.load(img);

  const overlay = screen.getByTestId("bbox-overlay");
  expect(overlay.style.left).toBe("10%");
  expect(overlay.style.top).toBe("10%");
  expect(overlay.style.width).toBe("20%");
  expect(overlay.style.height).toBe("5%");
});

it("scales the page with the zoom factor", () => {
  render(
    <DocumentViewer imageUrl="/x.jpg" documentName="hotel.pdf" page={0} box={null} zoom={0.75} />
  );

  expect(screen.getByAltText("Page 1 of hotel.pdf").parentElement?.style.width).toBe("75%");
});

it("renders no overlay without a box", () => {
  render(<DocumentViewer imageUrl="/x.jpg" documentName="hotel.pdf" page={0} box={null} />);

  expect(screen.queryByTestId("bbox-overlay")).toBeNull();
});
