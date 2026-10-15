type NamedField = {
  field_name: string;
  semantic_name?: string | null;
};

/**
 * The name to show a traveller for an extracted field.
 *
 * Prefers the form's own plain-language name. Falls back to the raw field name
 * with escaped control characters removed — some configs store UTF-16 names in
 * their escaped text form ("\000B\000e\000s..." rather than "Besch..."), which
 * is 200+ characters of unreadable noise in a table cell.
 */
export function fieldLabel(field: NamedField): string {
  const semantic = (field.semantic_name ?? "").trim();
  if (semantic) {
    return semantic;
  }

  const cleaned = field.field_name
    .replace(/\\000/g, "")
    .replace(/\\x00/gi, "")
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001f]/g, "")
    .trim();

  return cleaned || field.field_name;
}
