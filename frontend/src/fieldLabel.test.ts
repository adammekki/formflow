import { expect, it } from "vitest";

import { fieldLabel } from "./fieldLabel";

it("prefers the form's plain-language name", () => {
  expect(fieldLabel({ field_name: "UHD", semantic_name: "Personnel number" })).toBe(
    "Personnel number"
  );
});

it("falls back to the field name when there is no plain-language one", () => {
  expect(fieldLabel({ field_name: "Personalnummer", semantic_name: null })).toBe(
    "Personalnummer"
  );
});

it("cleans escaped control characters out of a raw field name", () => {
  // Some configs store UTF-16 names in their escaped text form:
  // "\000B\000e\000s\000c\000h..." instead of "Besch...".
  expect(
    fieldLabel({
      field_name: "\\000N\\000a\\000m\\000e_\\000X",
      semantic_name: null,
    })
  ).toBe("Name_X");
});

it("never returns an empty label", () => {
  expect(fieldLabel({ field_name: "\\000\\000", semantic_name: "  " })).toBe("\\000\\000");
});
