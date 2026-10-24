import pytest

from upgradeguard import cli
from upgradeguard.verdict import ACCEPT, INSUFFICIENT, REJECT


def test_exit_codes_match_the_documented_contract():
    assert cli.EXIT_CODES == {ACCEPT: 0, REJECT: 1, INSUFFICIENT: 2}


def test_run_command_line_is_parsed():
    args = cli.build_parser().parse_args([
        "run", "--repo", "r", "--package", "p", "--from", "1", "--to", "2",
        "--install-project", "--pytest-arg=-x", "--pytest-arg=-q", "--offline",
    ])
    assert (args.repo, args.package, args.from_version, args.to_version) == ("r", "p", "1", "2")
    assert args.install_project is True and args.pytest_args == ["-x", "-q"] and args.offline is True


def test_run_requires_the_four_core_flags():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["run", "--repo", "r"])


def test_benchmark_and_fetch_commands_exist():
    parser = cli.build_parser()
    assert parser.parse_args(["benchmark"]).cases == "benchmark/cases.json"
    assert parser.parse_args(["fetch-repos", "--only", "a/b"]).only == ["a/b"]


def test_no_command_prints_help_and_exits_2(capsys):
    assert cli.main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()
