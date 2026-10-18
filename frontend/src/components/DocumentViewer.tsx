import { useState } from "react";

import type { BoundingBox } from "../api";
import { pct } from "../percent";

type Props = {
  imageUrl: string;
  box: BoundingBox | null;
  documentName: string;
  page: number;
  pageId?: string;
};

export default function DocumentViewer({ imageUrl, box, documentName, page, pageId }: Props) {
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);

  // Percentage positions keep the overlay glued to the value across resizes,
  // with no listeners: the wrapper is exactly as tall as the image it contains.
  return (
    <div
      id={pageId}
      className="relative w-full overflow-hidden rounded-lg border border-line/60 bg-muted"
    >
      <img
        src={imageUrl}
        alt={`Page ${page + 1} of ${documentName}`}
        className="block w-full"
        onLoad={(e) =>
          setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
        }
      />
      {box && natural && natural.w > 0 && natural.h > 0 && (
        <div
          data-testid="bbox-overlay"
          className="absolute border-2 border-accent bg-accent/20"
          style={{
            left: pct(box.x, natural.w),
            top: pct(box.y, natural.h),
            width: pct(box.width, natural.w),
            height: pct(box.height, natural.h),
          }}
        />
      )}
    </div>
  );
}
