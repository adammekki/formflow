from app.services.locator import Word, match_words, normalize, parse_date, parse_number


def w(text, x0=0, y0=0, line=0, conf=100.0):
    return Word(x0=x0, y0=y0, x1=x0 + 50, y1=y0 + 12, text=text, line=line, conf=conf)


def test_normalize_folds_case_accents_and_whitespace():
    assert normalize("  Müller,\n JÖRG ") == "muller, jorg"


def test_parse_number_dot_decimal():
    assert parse_number("EUR 192.50") == 192.5


def test_parse_number_german_comma_decimal():
    assert parse_number("192,50") == 192.5


def test_parse_number_german_thousands():
    assert parse_number("1.234,56") == 1234.56


def test_parse_number_bare_three_digit_group_is_thousands():
    assert parse_number("1.234") == 1234


def test_parse_number_rejects_dates():
    assert parse_number("14.03.2025") is None


def test_parse_number_rejects_non_numbers():
    assert parse_number("Berlin") is None


def test_parse_date_iso():
    assert parse_date("2025-03-14") == "2025-03-14"


def test_parse_date_german_dot():
    assert parse_date("14.03.2025") == "2025-03-14"


def test_parse_date_slash_two_digit_year():
    assert parse_date("14/03/25") == "2025-03-14"


def test_parse_date_german_month_name():
    assert parse_date("14. März 2025") == "2025-03-14"


def test_match_words_exact_window():
    words = [w("Dr."), w("Maximilian", x0=60), w("Hofmann", x0=170)]
    assert match_words(words, "Dr. Maximilian Hofmann") == (0, 0, 220, 12)


def test_match_words_reformatted_amount():
    words = [w("EUR"), w("192.50", x0=60)]
    assert match_words(words, "192.5") == (0, 0, 110, 12)


def test_match_words_german_date_for_iso_value():
    words = [w("14.03.2025")]
    assert match_words(words, "2025-03-14") == (0, 0, 50, 12)


def test_match_words_first_occurrence_wins():
    words = [w("Berlin"), w("Berlin", y0=20, line=1)]
    assert match_words(words, "Berlin") == (0, 0, 50, 12)


def test_match_words_no_match_returns_none():
    assert match_words([w("Berlin")], "Stuttgart") is None


def test_match_words_skips_low_confidence_windows():
    words = [w("192.50", conf=40)]
    assert match_words(words, "192.5") is None
