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

AMBER = (255, 180, 84)
CREAM = (255, 244, 222)
VERDICTS = {"accept": ((125, 226, 176), 41), "reject": ((255, 138, 128), 203), "insufficient": ((255, 210, 138), 221)}
TAGLINE = "prove it before you ship"
RESET = "\033[0m"


def wants_colour(stream):
    return stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def truecolor():
    return os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")


def foreground(rgb, nearest):
    return "\033[38;2;%d;%d;%dm" % rgb if truecolor() else "\033[38;5;%dm" % nearest


def sweep(line, stream):
    if not wants_colour(stream):
        return line
    width = max(len(line) - 1, 1)
    pieces = []
    for x, char in enumerate(line):
        if char == " ":
            pieces.append(char)
            continue
        glow = 1 - abs(2 * x / width - 1)
        rgb = tuple(round(a + (b - a) * glow * 0.85) for a, b in zip(AMBER, CREAM))
        pieces.append(foreground(rgb, 214 if glow < 0.5 else 223) + char)
    return "".join(pieces) + RESET


def dim(text, stream):
    return "\033[2m%s\033[0m" % text if wants_colour(stream) else text


def accent(text, stream):
    return foreground(AMBER, 214) + text + RESET if wants_colour(stream) else text


def print_banner(stream=None):
    stream = stream or sys.stdout
    if not stream.isatty():
        return
    columns = shutil.get_terminal_size().columns
    art = None
    for candidate in (WORDMARK, COMPACT):
        lines = candidate.strip("\n").split("\n")
        if columns >= max(len(line) for line in lines) + 2:
            art = lines
            break
    if art is None:
        art = ["UPGRADEGUARD"]
    stream.write("\n" + "\n".join(sweep(line, stream) for line in art) + "\n")
    stream.write(dim(TAGLINE, stream) + "\n")


def headline(text, stream=None):
    stream = stream or sys.stdout
    if not wants_colour(stream):
        return text
    word, _, rest = text.partition(":")
    rgb, nearest = VERDICTS.get(word.strip().lower().split(" ")[0], (AMBER, 214))
    if truecolor():
        badge = "\033[1;30;48;2;%d;%d;%dm %s \033[0m" % (rgb + (word.upper(),))
    else:
        badge = "\033[1;30;48;5;%dm %s \033[0m" % (nearest, word.upper())
    return badge + " " + rest.strip()
