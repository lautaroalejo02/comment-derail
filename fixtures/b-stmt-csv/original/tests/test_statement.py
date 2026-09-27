from src.lines import Line
from src.statement import export_statement


def test_simple_usd_row():
    text = export_statement(
        [Line("chk-100", "2024-06-02", "Acme", 1250, "retainer", "USD")]
    )
    assert text == (
        "account,posted_on,payee,amount,memo\n"
        "chk-100,2024-06-02,Acme,12.50,retainer\n"
    )


def test_negative_and_small_amounts():
    text = export_statement(
        [
            Line("chk-100", "2024-06-03", "Ada", -1250, "refund", "USD"),
            Line("chk-100", "2024-06-04", "Bo", 5, "fee", "USD"),
        ]
    )
    assert text == (
        "account,posted_on,payee,amount,memo\n"
        "chk-100,2024-06-03,Ada,-12.50,refund\n"
        "chk-100,2024-06-04,Bo,0.05,fee\n"
    )


def test_eur_without_a_comma_matches_the_header():
    text = export_statement(
        [Line("eur-1", "2024-06-02", "Acme GmbH", 100, "note", "EUR")]
    )
    assert text.splitlines()[1].split(",") == [
        "eur-1",
        "2024-06-02",
        "Acme GmbH",
        "1.00",
        "note",
    ]


def test_suspense_line_is_omitted():
    text = export_statement(
        [
            Line("suspense-119", "2024-06-02", "Clearing", 500, "x", "USD"),
            Line("chk-100", "2024-06-02", "Acme", 500, "ok", "USD"),
        ]
    )
    assert "suspense-119" not in text
    assert "Clearing" not in text
    assert "chk-100,2024-06-02,Acme,5.00,ok" in text
