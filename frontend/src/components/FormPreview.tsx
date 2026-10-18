import { useState } from "react";

import type { BoundingBox } from "../api";
import { pct } from "../percent";

export type PreviewBox = {
  key: string;
  label: string;
  box: BoundingBox;
  selected: boolean;
};

type PreviewPage = {
  page: number;
  imageUrl: string;
};

type Props = {
  pages: PreviewPage[];
  boxes: PreviewBox[];
};

/** The whole form template, stacked, with a labelled box on every line that
 *  will be filled. */
export default function FormPreview({ pages, boxes }: Props) {
  return (
    <div className="space-y-3">
      {pages.map((page) => (
        <FormPage
          key={page.page}
          page={page}
          boxes={boxes.filter((entry) => entry.box.page === page.page)}
        />
      ))}
    </div>
  );
}

function FormPage({ page, boxes }: { page: PreviewPage; boxes: PreviewBox[] }) {
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);

  return (
    <div
      id={`preview-page-${page.page}`}
      data-testid={`template-page-${page.page}`}
      className="relative w-full min-w-[900px] overflow-hidden rounded-lg border border-line/60 bg-muted"
    >
      <img
        src={page.imageUrl}
        alt={`Form page ${page.page + 1}`}
        className="block w-full"
        onLoad={(e) =>
          setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
        }
      />
      {natural &&
        natural.w > 0 &&
        natural.h > 0 &&
        boxes.map((entry) => (
          <div
            key={entry.key}
            data-testid={`target-box-${entry.key}`}
            data-selected={entry.selected}
            className={`absolute ${
              entry.selected
                ? "border-2 border-accent bg-accent/25"
                : "border border-dashed border-accent-soft bg-accent/10"
            }`}
            style={{
              left: pct(entry.box.x, natural.w),
              top: pct(entry.box.y, natural.h),
              width: pct(entry.box.width, natural.w),
              height: pct(entry.box.height, natural.h),
            }}
          >
            <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-accent px-1 py-0.5 text-[11px] leading-tight text-bg">
              {entry.label}
            </span>
          </div>
        ))}
    </div>
  );
}
