import { useState } from "react";

import type { BoundingBox } from "../api";
import { pct } from "../percent";

export type PreviewBox = {
  key: string;
  label: string;
  box: BoundingBox;
  selected: boolean;
};

type Props = {
  imageUrl: string;
  page: number;
  boxes: PreviewBox[];
};

/** The form template with a labelled box on every line that will be filled. */
export default function FormPreview({ imageUrl, page, boxes }: Props) {
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);

  return (
    <div className="relative w-full overflow-hidden rounded-lg border border-line/60 bg-muted">
      <img
        src={imageUrl}
        alt={`Form page ${page + 1}`}
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
            <span className="absolute -top-4 left-0 max-w-full truncate rounded bg-accent px-1 text-[10px] leading-4 text-bg">
              {entry.label}
            </span>
          </div>
        ))}
    </div>
  );
}
