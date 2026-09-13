"""Text-only contracts for the procfs parsers."""

from sinnix_lib.procfs import (
    parse_cgroup_v2,
    parse_colon_numeric,
    parse_psi,
    parse_stat_start_time,
)


def test_parse_psi_preserves_averages_and_integer_totals() -> None:
    parsed = parse_psi(
        "some avg10=1.25 avg60=2.5 avg300=3.75 total=12345\n"
        "full avg10=0.25 avg60=0.5 avg300=0.75 total=9\n"
    )
    assert parsed == {
        "some": {"avg10": 1.25, "avg60": 2.5, "avg300": 3.75, "total": 12345},
        "full": {"avg10": 0.25, "avg60": 0.5, "avg300": 0.75, "total": 9},
    }


def test_parse_psi_ignores_malformed_fields_and_missing_input() -> None:
    assert parse_psi("some avg10=bad missing total=nope\nfull broken\n") == {}
    assert parse_psi(None) == {}


def test_parse_colon_numeric_accepts_meminfo_units_and_last_duplicate() -> None:
    assert parse_colon_numeric(
        "MemTotal:       1000000 kB\n"
        "MemAvailable:   200000 kB\n"
        "MemTotal:       900000 kB\n"
    ) == {"MemTotal": 900000, "MemAvailable": 200000}


def test_parse_colon_numeric_skips_malformed_and_missing_records() -> None:
    assert parse_colon_numeric(
        "missing colon\n: 4\nBad: no-number\nEmpty:\nGood: -7 bytes\n"
    ) == {"Good": -7}
    assert parse_colon_numeric(None) == {}


def test_parse_cgroup_v2_requires_one_well_formed_v2_record() -> None:
    assert parse_cgroup_v2("0::/user.slice/session.scope\n") == "/user.slice/session.scope"
    assert parse_cgroup_v2("0::/\n") == "/"
    assert parse_cgroup_v2("1:name=systemd:/system.slice\n0::/user.slice\n") is None
    assert parse_cgroup_v2("0:/wrong:/user.slice\n") is None
    assert parse_cgroup_v2("0::relative\n") is None
    assert parse_cgroup_v2(None) is None


def test_parse_stat_start_time_handles_spaces_and_parentheses_in_comm() -> None:
    # Field 3 (state) is followed by fields 4..22; field 22 is the twentieth
    # token after the final comm delimiter.
    tail = "S " + " ".join(str(index) for index in range(4, 23))
    assert parse_stat_start_time(f"321 (worker ) with spaces) {tail}") == 22


def test_parse_stat_start_time_rejects_missing_or_short_stat() -> None:
    assert parse_stat_start_time(None) is None
    assert parse_stat_start_time("321 no-comm S") is None
    assert parse_stat_start_time("321 (name) S 1 2") is None
    malformed = "321 (name) S " + " ".join(["x"] * 20)
    assert parse_stat_start_time(malformed) is None
