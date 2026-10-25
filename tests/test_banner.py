import io
import re

from upgradeguard import banner, cli


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_nothing_is_added_when_output_is_not_a_terminal():
    out = io.StringIO()
    banner.print_banner(out)
    assert out.getvalue() == ""
    assert banner.headline("Accept: upgrading a from 1 to 2", out) == "Accept: upgrading a from 1 to 2"


def test_a_wide_terminal_gets_the_big_letters_and_a_narrow_one_the_small_ones(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("COLUMNS", "140")
    wide = Terminal()
    banner.print_banner(wide)
    monkeypatch.setenv("COLUMNS", "60")
    narrow = Terminal()
    banner.print_banner(narrow)
    monkeypatch.setenv("COLUMNS", "30")
    tiny = Terminal()
    banner.print_banner(tiny)
    assert wide.getvalue().count("\n") > narrow.getvalue().count("\n") > tiny.getvalue().count("\n")
    assert "\033[38;" in wide.getvalue() and "UPGRADEGUARD" in re.sub(r"\x1b\[[0-9;]*m", "", tiny.getvalue())


def test_no_colour_is_respected(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    out = Terminal()
    banner.print_banner(out)
    assert "\033[" not in out.getvalue() and out.getvalue().strip()


def test_the_summary_has_no_row_of_dashes(capsys):
    bundle = {"verdict": {"headline": "Accept: upgrading requests from 2.28.2 to 2.32.5", "reasons": [], "notes": []},
              "diff": {"graph": {"added": [], "removed": [], "changed": []}, "tests": {"regressions": []}, "conflicts": {"introduced": []},
                       "vulnerabilities": {"introduced": []}, "licenses": {"introduced": []}},
              "evidence_dir": "/tmp/x", "total_seconds": 1.0}
    cli.print_summary(bundle)
    shown = capsys.readouterr().out
    assert "Accept: upgrading requests" in shown and "-----" not in shown


def test_the_verdict_becomes_a_coloured_badge_only_in_a_terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("COLORTERM", "truecolor")
    shown = banner.headline("Reject: upgrading a from 1 to 2", Terminal())
    assert "\033[1;30;48;2;" in shown and " REJECT " in shown and "upgrading a from 1 to 2" in shown
    assert banner.headline("Reject: upgrading a from 1 to 2", io.StringIO()) == "Reject: upgrading a from 1 to 2"
