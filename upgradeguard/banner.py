import os
import shutil
import sys

WORDMARK = """
██    ██ ██████   ██████  ██████   █████  ██████  ███████  ██████  ██    ██  █████  ██████  ██████
██    ██ ██   ██ ██       ██   ██ ██   ██ ██   ██ ██      ██       ██    ██ ██   ██ ██   ██ ██   ██
██    ██ ██████  ██   ███ ██████  ███████ ██   ██ █████   ██   ███ ██    ██ ███████ ██████  ██   ██
██    ██ ██      ██    ██ ██   ██ ██   ██ ██   ██ ██      ██    ██ ██    ██ ██   ██ ██   ██ ██   ██
 ██████  ██       ██████  ██   ██ ██   ██ ██████  ███████  ██████   ██████  ██   ██ ██   ██ ██████
"""

COMPACT = """
░█░█░█▀█░█▀▀░█▀▄░█▀█░█▀▄░█▀▀░█▀▀░█░█░█▀█░█▀▄░█▀▄
░█░█░█▀▀░█░█░█▀▄░█▀█░█░█░█▀▀░█░█░█░█░█▀█░█▀▄░█░█
░▀▀▀░▀░░░▀▀▀░▀░▀░▀░▀░▀▀░░▀▀▀░▀▀▀░▀▀▀░▀░▀░▀░▀░▀▀░
"""

AMBER = "38;5;214"
GREEN = "38;5;41"
RED = "38;5;203"
YELLOW = "38;5;221"
VERDICT_COLOURS = {"accept": GREEN, "reject": RED, "insufficient": YELLOW}


def wants_colour(stream):
    return stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def paint(text, code, stream):
    return "\033[1;%sm%s\033[0m" % (code, text) if wants_colour(stream) else text


def print_banner(stream=None):
    stream = stream or sys.stdout
    if not stream.isatty():
        return
    columns = shutil.get_terminal_size().columns
    for art in (WORDMARK, COMPACT):
        lines = art.strip("\n").split("\n")
        if columns >= max(len(line) for line in lines) + 2:
            stream.write("\n" + "\n".join(paint(line, AMBER, stream) for line in lines) + "\n")
            return
    stream.write("\n" + paint("UPGRADEGUARD", AMBER, stream) + "\n")


def headline(text, stream=None):
    stream = stream or sys.stdout
    word, _, rest = text.partition(":")
    key = word.strip().lower().split(" ")[0]
    return paint(word, VERDICT_COLOURS.get(key, AMBER), stream) + ":" + rest
