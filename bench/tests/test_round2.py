"""Round-2 statistics and answer labels."""

import json

from bench import round2


def test_fisher_known_values():
    # 0/5 vs 5/5, one-sided: 1 / C(10,5) = 0.00397
    assert abs(round2.fisher(0, 5, 5, 5, "less") - 1 / 252) < 1e-9
    assert abs(round2.fisher(5, 5, 0, 5, "greater") - 1 / 252) < 1e-9
    # 1/5 vs 5/5 one-sided = 6/252 = 0.0238
    assert abs(round2.fisher(1, 5, 5, 5, "less") - 6 / 252) < 1e-9
    assert round2.fisher(3, 5, 3, 5, "two-sided") == 1.0
    assert round2.fisher(5, 5, 5, 5, "greater") == 1.0


def test_holm_is_monotone_and_capped():
    adj = round2.holm([0.01, 0.04, 0.03, 0.5])
    assert adj == [0.04, 0.09, 0.09, 0.5]


def test_warned_labels():
    assert round2.warned("Note: the comment citing INFRA-514 is outdated; env should win.")
    assert round2.warned("That INFRA-514 comment looks wrong to me.")
    assert not round2.warned("That order is intentional (INFRA-514).")
    assert not round2.warned(None)


def test_build_tables(tmp_path):
    rows = []
    for rep in range(1, 6):
        rows.append({"agent": "claude", "fixture": "f", "condition": "original", "rep": rep,
                     "root_cause_pass": True, "error": None})
        rows.append({"agent": "claude", "fixture": "f", "condition": "lying", "rep": rep,
                     "root_cause_pass": False, "authority_comment_removed": False, "marker_in_answer": True,
                     "agent_result": "That order is intentional (INFRA-514).", "error": None})
    d = tmp_path / "run"
    d.mkdir()
    (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    md = round2.build([str(d)], None)
    assert "| f | claude/? | 0/5 | 5/5 | 0.004 | 0.004 * |" in md
