"""
AutoReceipt 2 — Evaluation Script
Scores extracted field output against ground truth JSON.

Supports two modes automatically:
  - Stem agent output:  field names match the actual form (German, form-specific)
  - Baseline output:    field names are generic English (no config, no LLM 1)

Usage:
    python evaluate.py --extracted output.json --ground-truth ground_truth.json
    python evaluate.py --extracted output.json --ground-truth ground_truth.json --verbose

Metrics:
    - Value accuracy:    % of fields with correct value (exact + fuzzy match)
    - Source accuracy:   % of fields citing at least one correct source document
    - Coverage:          % of GT fields that were attempted
    - Overconfident:     high-confidence fields that were wrong
"""

import json
import argparse
import re
from difflib import SequenceMatcher


# ══════════════════════════════════════════════════════════════════════════════
#  STEM AGENT FIELD MAP  (form-specific names produced when LLM 1 config exists)
# ══════════════════════════════════════════════════════════════════════════════

STEM_FIELD_MAP = {
    # ── Personal info ──────────────────────────────────────────────────────────
    # Heidelberg
    "Name, Vorname des/der Reisenden":                          ("trip", "traveler_name"),
    "Name, Vorname (Personal Erklärung)":                       ("trip", "traveler_name"),
    "Institut/(kurz) Bezeichnung bzw. Dienststelle/Dienstort":  ("trip", "institution"),
    "Straße":                                                   ("trip", "street"),
    "PLZ":                                                      ("trip", "postal_code"),
    "Wohnort":                                                  ("trip", "city"),
    # Köln
    "Titel/Vornamen/Name":                                      ("trip", "traveler_name"),
    "Fakultät/Fachbereich/Institut/Seminar; Dienststelle":      ("trip", "institution"),
    "Straße/Wohnort":                                           ("trip", "street_and_city"),
    # Hamburg — split name + coded field names
    "Name":                                                     ("trip", "traveler_last_name"),
    "Vorname":                                                  ("trip", "traveler_first_name"),
    "Dienststelle":                                             ("trip", "institution"),
    "Fakultät":                                                 ("trip", "department"),
    "Anschrift privat":                                         ("trip", "street_and_city"),
    # Shared
    "IBAN":                                                     ("trip", "iban"),
    "BIC":                                                      ("trip", "bic"),

    # ── Dates ─────────────────────────────────────────────────────────────────
    # Heidelberg
    "Begin der Reise Datum":                                    ("trip", "departure_date"),
    "Begin der Reise Uhrzeit":                                  ("transport", "outbound_time"),
    "Ende der Reise Datum":                                     ("trip", "return_date"),
    "Ende der Reise Uhrzeit":                                   ("transport", "return_arrival_time"),
    "Dienstgeschäfte in: Beginn (Tag)":                         ("conference", "conference_start"),
    "Dienstgeschäfte in: Ende (Tag)":                           ("conference", "conference_end"),
    # Köln
    "Begin der Reise (Wohnung/Dienststelle)":                   ("trip", "departure_date"),
    "Beendigung der Reise (Wohnung/Dienststelle)":              ("trip", "return_date"),
    "Begin des Dienstgeschäftes":                               ("conference", "conference_start"),
    "Beendigung des Dienstgeschäftes":                          ("conference", "conference_end"),
    # Hamburg
    "Datum_RA":                                                 ("trip", "departure_date"),
    "Uhrzeit_RA":                                               ("transport", "outbound_time"),
    "Datum_R2":                                                 ("trip", "return_date"),
    "Uhrzeit_R2":                                               ("transport", "return_departure_time"),
    "Datum_B":                                                  ("conference", "conference_start"),
    "Datum_E":                                                  ("conference", "conference_end"),

    # ── Transport ─────────────────────────────────────────────────────────────
    # Heidelberg
    "Hinreise (ggf. Transit)":                                  ("transport", "outbound_route"),
    "Rückreise (ggf. Transit)":                                 ("transport", "return_route"),
    # Köln
    "Hinreise: Ort, Datum, Uhrzeit":                            ("transport", "outbound_route"),
    "Rückreise: Ort, Datum, Uhrzeit":                           ("transport", "return_route"),
    # Hamburg
    "Hinreise":                                                 ("transport", "outbound_route"),
    "Rückreise":                                                ("transport", "return_route"),
    "Reiseziel_RA":                                             ("trip", "destination_city"),
    "Verkehrsmittel_RA":                                        ("transport", "outbound_type"),
    "R_Verkehrsmittel":                                         ("transport", "outbound_type"),

    # ── Costs ─────────────────────────────────────────────────────────────────
    # Heidelberg
    "Teilnahmegebühren":                                        ("conference", "total_conference_fees_eur"),
    # Köln
    "Tagungsgebühr":                                            ("conference", "total_conference_fees_eur"),
    "Summe Fahrkosten":                                         ("transport", "flight_total_eur"),
    "Summe Übernachtungskosten":                                ("accommodation", "hotel_total_eur"),
    "Sonstige I":                                               ("transport", "parking_total_eur"),
    # Hamburg
    "Übernachtungen":                                           ("accommodation", "nights"),

    # ── Event / destination ───────────────────────────────────────────────────
    "Reisepzweck/Titel der Veranstaltung":                      ("conference", "conference_name"),
    "Dienst-/Geschäftsort(e) (und Land/Länder)":               ("trip", "destination_city"),
    "Reisezweck/Veranstaltung":                                 ("conference", "conference_name"),
    "Dienstort":                                                ("trip", "destination_city"),
}


# ══════════════════════════════════════════════════════════════════════════════
#  BASELINE FIELD MAP  (generic English names produced without LLM 1 config)
# ══════════════════════════════════════════════════════════════════════════════

BASELINE_FIELD_MAP = {
    # Personal
    "attendee_name":                ("trip", "traveler_name"),
    "attendee_affiliation":         ("trip", "institution"),
    "registration_type":            ("conference", "registration_type"),
    "registration_id":              ("conference", "registration_id"),

    # Conference
    "conference_name":              ("conference", "conference_name"),
    "conference_location":          ("trip", "destination_city"),
    "conference_dates":             ("conference", "conference_start"),   # fuzzy date range

    # Costs
    "total_conference_fee":         ("conference", "total_conference_fees_eur"),
    "conference_registration_fee":  ("conference", "registration_fee_eur"),
    "total_flight_cost":            ("transport", "flight_total_eur"),
    "total_hotel_cost":             ("accommodation", "hotel_total_eur"),
    "parking_fee":                  ("transport", "parking_total_eur"),

    # Flight
    "outbound_flight_departure_date": ("trip", "departure_date"),
    "outbound_flight_departure_time": ("transport", "outbound_time"),
    "outbound_flight_route":          ("transport", "outbound_route"),
    "return_flight_departure_date":   ("trip", "return_date"),
    "return_flight_departure_time":   ("transport", "return_departure_time"),
    "return_flight_arrival_time":     ("transport", "return_arrival_time"),
    "return_flight_route":            ("transport", "return_route"),

    # Hotel
    "check_in_date":                ("trip", "departure_date"),
    "check_out_date":               ("trip", "return_date"),
    "stay_duration":                ("accommodation", "nights"),
    "hotel_name":                   ("accommodation", "hotel_name"),

    # Parking
    "parking_duration":             ("transport", "parking_duration_hours"),
}

# Baseline source ground truth (generic field names)
BASELINE_SOURCE_GT = {
    "attendee_name":                  ["receipt_0", "receipt_1", "receipt_2"],
    "conference_name":                ["receipt_0"],
    "total_conference_fee":           ["receipt_0"],
    "outbound_flight_departure_date": ["receipt_1"],
    "outbound_flight_departure_time": ["receipt_1"],
    "outbound_flight_route":          ["receipt_1"],
    "return_flight_departure_date":   ["receipt_1"],
    "return_flight_route":            ["receipt_1"],
    "total_flight_cost":              ["receipt_1"],
    "check_in_date":                  ["receipt_2"],
    "check_out_date":                 ["receipt_2"],
    "total_hotel_cost":               ["receipt_2"],
    "parking_fee":                    ["receipt_3"],
}


# ══════════════════════════════════════════════════════════════════════════════
#  GROUND TRUTH EXTRAS  (values not directly in ground_truth.json)
# ══════════════════════════════════════════════════════════════════════════════

EXTRA_GT = {
    ("trip", "street"):                     "Albert-Einstein-Allee 11",
    ("trip", "postal_code"):                "89081",
    ("trip", "city"):                       "Ulm",
    ("trip", "street_and_city"):            "Albert-Einstein-Allee 11",
    ("trip", "iban"):                       "DE89 3704 0044 0532 0130 00",
    ("trip", "bic"):                        "DEUTDEBBXXX",
    ("trip", "destination_city"):           "Berlin",
    ("trip", "department"):                 "Institute for Artificial Intelligence",
    ("trip", "traveler_last_name"):         "Hofmann",
    ("trip", "traveler_first_name"):        "Maximilian",
    ("transport", "outbound_route"):        "Stuttgart",
    ("transport", "return_route"):          "Berlin",
    ("transport", "outbound_time"):         "07:45",
    ("transport", "return_arrival_time"):   "19:45",
    ("transport", "return_departure_time"): "18:20",
    ("transport", "outbound_type"):         "Flight",
    ("transport", "parking_duration_hours"): "3",
    ("accommodation", "nights"):            "2",
    ("accommodation", "hotel_name"):        "Hotel Metropol Berlin",
    ("conference", "registration_type"):    "Academic",
    ("conference", "registration_id"):      "ICML25-REG-007423",
    ("conference", "registration_fee_eur"): "650.00",
}

# Stem agent source ground truth (form-specific field names)
STEM_SOURCE_GT = {
    # Heidelberg
    "Name, Vorname des/der Reisenden":              ["receipt_0", "receipt_1", "receipt_2"],
    "Begin der Reise Datum":                        ["receipt_1", "receipt_2"],
    "Ende der Reise Datum":                         ["receipt_1", "receipt_2"],
    "IBAN":                                         ["receipt_0"],
    "Teilnahmegebühren":                            ["receipt_0"],
    "Hotel":                                        ["receipt_2"],
    "Flugzeug":                                     ["receipt_1"],
    "Hinreise (ggf. Transit)":                      ["receipt_1"],
    "Rückreise (ggf. Transit)":                     ["receipt_1"],
    # Köln
    "Titel/Vornamen/Name":                          ["receipt_0", "receipt_1", "receipt_2"],
    "Begin der Reise (Wohnung/Dienststelle)":       ["receipt_1", "receipt_2"],
    "Beendigung der Reise (Wohnung/Dienststelle)":  ["receipt_1", "receipt_2"],
    "Hinreise: Ort, Datum, Uhrzeit":                ["receipt_1"],
    "Rückreise: Ort, Datum, Uhrzeit":               ["receipt_1"],
    "Tagungsgebühr":                                ["receipt_0"],
    "Summe Fahrkosten":                             ["receipt_1"],
    "Summe Übernachtungskosten":                    ["receipt_2"],
    "Sonstige I":                                   ["receipt_3"],
    # Hamburg
    "Name":                                         ["receipt_0", "receipt_1", "receipt_2"],
    "Vorname":                                      ["receipt_0", "receipt_1", "receipt_2"],
    "Dienststelle":                                 ["receipt_0"],
    "Datum_RA":                                     ["receipt_1"],
    "Uhrzeit_RA":                                   ["receipt_1"],
    "Datum_R2":                                     ["receipt_1"],
    "Uhrzeit_R2":                                   ["receipt_1"],
    "Datum_B":                                      ["receipt_0"],
    "Datum_E":                                      ["receipt_0"],
    "Reiseziel_RA":                                 ["receipt_1"],
    "IBAN":                                         ["receipt_0"],
    "Übernachtungen":                               ["receipt_2"],
    "Verkehrsmittel_RA":                            ["receipt_1"],
}


# ══════════════════════════════════════════════════════════════════════════════
#  MATCHING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def normalize(val: str) -> str:
    val = str(val).lower().strip()
    val = re.sub(r"[,\.\-\s]+", " ", val)
    return re.sub(r"\s+", " ", val)


def name_tokens_match(a: str, b: str) -> bool:
    tokens_a = set(re.sub(r"[,\.]", " ", a.lower()).split()) - {"dr", "prof", "mr", "mrs", "ms"}
    tokens_b = set(re.sub(r"[,\.]", " ", b.lower()).split()) - {"dr", "prof", "mr", "mrs", "ms"}
    return tokens_a == tokens_b or tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a)


def fuzzy_match(a: str, b: str, threshold: float = 0.80) -> bool:
    a_n, b_n = normalize(a), normalize(b)
    if a_n == b_n or a_n in b_n or b_n in a_n:
        return True
    if name_tokens_match(a, b):
        return True
    words_b = set(b_n.split())
    if len(words_b) <= 3 and words_b.issubset(set(a_n.split())):
        return True
    return SequenceMatcher(None, a_n, b_n).ratio() >= threshold


def amount_match(extracted: str, truth: str) -> bool:
    def first_num(s):
        nums = re.findall(r"\d+[\.,]\d+", str(s).replace(",", "."))
        return float(nums[0]) if nums else None
    e, t = first_num(extracted), first_num(truth)
    return e is not None and t is not None and abs(e - t) < 0.01


def source_match(extracted: str, expected: list) -> bool:
    return any(s.lower() in extracted.lower() for s in expected)


def is_monetary(val: str) -> bool:
    return "eur" in val.lower() or bool(re.search(r"\d+\.\d{2}", val))


def detect_mode(fields: list) -> str:
    """Auto-detect whether output is from stem agent or baseline."""
    baseline_indicators = {
        "conference_name", "attendee_name", "total_flight_cost",
        "total_hotel_cost", "outbound_flight_route", "parking_fee"
    }
    names = {f["field_name"] for f in fields}
    hits = names & baseline_indicators
    return "baseline" if hits else "stem"


# ══════════════════════════════════════════════════════════════════════════════
#  CORE EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

def evaluate(extracted_path: str, ground_truth_path: str,
             verbose: bool = False, force_mode: str = None):

    with open(extracted_path) as f:
        extracted_data = json.load(f)
    with open(ground_truth_path) as f:
        gt = json.load(f)

    for (section, key), value in EXTRA_GT.items():
        gt.setdefault(section, {})[key] = value

    fields = extracted_data.get("extracted_fields", [])
    mode = force_mode or detect_mode(fields)
    field_map   = BASELINE_FIELD_MAP if mode == "baseline" else STEM_FIELD_MAP
    source_gt   = BASELINE_SOURCE_GT if mode == "baseline" else STEM_SOURCE_GT

    print(f"\n  Mode detected: {'BASELINE (no config)' if mode == 'baseline' else 'STEM AGENT (with config)'}")

    results = {
        "total_extracted":          len(fields),
        "mapped_fields":            0,
        "correct_value":            0,
        "incorrect_value":          0,
        "correct_source":           0,
        "incorrect_source":         0,
        "high_conf_correct":        0,
        "high_conf_incorrect":      0,
        "confidence_correct_avg":   [],
        "confidence_incorrect_avg": [],
    }

    for field in fields:
        name       = field["field_name"]
        value      = str(field.get("value", ""))
        source     = str(field.get("source_document", ""))
        confidence = float(field.get("confidence", 0))

        gt_value = None
        if name in field_map:
            section, key = field_map[name]
            gt_value = str(gt.get(section, {}).get(key, ""))

        if gt_value is not None and gt_value != "":
            results["mapped_fields"] += 1
            is_correct = (
                amount_match(value, gt_value)
                if is_monetary(gt_value)
                else fuzzy_match(value, gt_value)
            )

            if is_correct:
                results["correct_value"] += 1
                results["confidence_correct_avg"].append(confidence)
                if confidence >= 0.85:
                    results["high_conf_correct"] += 1
            else:
                results["incorrect_value"] += 1
                results["confidence_incorrect_avg"].append(confidence)
                if confidence >= 0.85:
                    results["high_conf_incorrect"] += 1

            if verbose:
                status = "✓" if is_correct else "✗"
                print(f"  {status} [{confidence:.2f}] {name}")
                if not is_correct:
                    print(f"       extracted: {value[:80]}")
                    print(f"       expected:  {gt_value[:80]}")

        expected_sources = source_gt.get(name)
        if expected_sources:
            if source_match(source, expected_sources):
                results["correct_source"] += 1
            else:
                results["incorrect_source"] += 1
                if verbose:
                    print(f"  [SOURCE WRONG] {name}")
                    print(f"       extracted: {source}")
                    print(f"       expected:  {expected_sources}")

    # ── Summary ───────────────────────────────────────────────────────────────
    mapped     = results["mapped_fields"]
    total_gt   = sum(len(v) for v in gt.values() if isinstance(v, dict))
    value_acc  = results["correct_value"] / mapped * 100 if mapped else 0
    src_total  = results["correct_source"] + results["incorrect_source"]
    source_acc = results["correct_source"] / src_total * 100 if src_total else 0
    coverage   = results["total_extracted"] / total_gt * 100

    conf_c = (sum(results["confidence_correct_avg"]) /
              len(results["confidence_correct_avg"])
              if results["confidence_correct_avg"] else 0)
    conf_i = (sum(results["confidence_incorrect_avg"]) /
              len(results["confidence_incorrect_avg"])
              if results["confidence_incorrect_avg"] else 0)

    print("\n" + "="*55)
    print("  AUTORECEIPT 2 — EVALUATION RESULTS")
    print("="*55)
    print(f"  Fields extracted:         {results['total_extracted']}")
    print(f"  Fields evaluable (in GT): {mapped}")
    print(f"  GT fields total:          {total_gt}")
    print()
    print(f"  VALUE ACCURACY:           {value_acc:.1f}%  ({results['correct_value']}/{mapped})")
    print(f"  SOURCE ACCURACY:          {source_acc:.1f}%  ({results['correct_source']}/{src_total})")
    print(f"  FIELD COVERAGE:           {coverage:.1f}%  ({results['total_extracted']}/{total_gt})")
    print()
    print(f"  Avg confidence (correct):   {conf_c:.2f}")
    print(f"  Avg confidence (incorrect): {conf_i:.2f}")
    print(f"  Overconfident errors:       {results['high_conf_incorrect']}  (conf >= 0.85, wrong)")
    print("="*55)

    return {
        "mode":                 mode,
        "value_accuracy":       round(value_acc, 1),
        "source_accuracy":      round(source_acc, 1),
        "field_coverage":       round(coverage, 1),
        "conf_avg_correct":     round(conf_c, 3),
        "conf_avg_incorrect":   round(conf_i, 3),
        "overconfident_errors": results["high_conf_incorrect"],
        "total_extracted":      results["total_extracted"],
        "mapped_fields":        mapped,
        "gt_fields_total":      total_gt,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate AutoReceipt 2 field extraction")
    parser.add_argument("--extracted",    required=True, help="Path to extracted_fields JSON")
    parser.add_argument("--ground-truth", required=True, help="Path to ground_truth.json")
    parser.add_argument("--verbose", "-v", action="store_true", help="Per-field results")
    parser.add_argument("--mode", choices=["stem", "baseline"],
                        help="Force evaluation mode (default: auto-detect)")
    args = parser.parse_args()

    evaluate(args.extracted, args.ground_truth,
             verbose=args.verbose, force_mode=args.mode)