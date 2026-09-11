#!/usr/bin/env python3
"""Transitional keyboard layouts on the way from NeoQwertz to Bone.

Every generated layout is assembled from the Bone keylayout alone. A key that
holds letter L takes the letter-bound layers from Bone's key for L and keeps the
physical layers of the key it sits on, so what moves with the letter is exactly
what moves in Bone itself. Which layer is which was read off a diff of the two
upstream files, see README.md.

Only the standard library is used, so `python3 charon.py` works anywhere.
"""

import argparse
import copy
import hashlib
import pathlib
import plistlib
import re
import sys
import xml.etree.ElementTree as ET

# Key codes of the four letter rows on a Mac keyboard, in reading order. Row 0 is
# the number row, whose last key (QWERTZ ß) takes part in the transition.
ROWS = (
    (18, 19, 20, 21, 23, 22, 26, 28, 25, 29, 27),
    (12, 13, 14, 15, 17, 16, 32, 34, 31, 35, 33),
    (0, 1, 2, 3, 5, 4, 38, 40, 37, 41, 39),
    (6, 7, 8, 9, 11, 45, 46, 43, 47, 44),
)
DIGITS = "1234567890"
LETTER_CODES = (ROWS[0][10],) + ROWS[1] + ROWS[2] + ROWS[3]

# Layers that stay on the physical key: 3 (Option maps and the Bugfixes state the
# Karabiner Neo rules use), 4 (the Ebene 4 und 6 state), and the Ctrl maps, which
# upstream Bone keeps on QWERTZ positions. In the Cmd map only the plain output
# follows the letter; its dead-key states are leftovers that never mattered.
PHYSICAL_MAPS = frozenset({4, 6, 8, 9})
PHYSICAL_STATES = frozenset({"Bugfixes", "Ebene 4 und 6"})
CMD_MAP = 7
GREEK_MAP = 5

# The ids of the Neo project's own bundle, never to be reused next to it.
NEO_IDS = frozenset({-5743, -7045, -15581})

# German letter frequencies in percent, Wikipedia "Buchstabenhäufigkeit"
# (Beutelspacher). Only used to weigh stages against each other.
FREQ = {
    "e": 17.40, "n": 9.78, "i": 7.55, "s": 7.27, "r": 7.00, "a": 6.51, "t": 6.15,
    "d": 5.08, "h": 4.76, "u": 4.35, "l": 3.44, "c": 3.06, "g": 3.01, "m": 2.53,
    "o": 2.51, "b": 1.89, "w": 1.89, "f": 1.66, "k": 1.21, "z": 1.13, "p": 0.79,
    "v": 0.67, "ü": 0.65, "ä": 0.54, "ß": 0.31, "ö": 0.30, "j": 0.27, "y": 0.04,
    "x": 0.03, "q": 0.02,
}  # fmt: skip

# The keylayouts are XML 1.1 and reference control characters as &#x0010;, which
# expat rejects. They are swapped for private-use characters around parsing and
# swapped back on output.
CONTROL_REF = re.compile(r"&#x00([01][0-9A-Fa-f]);")
PUA_RANGE = re.compile("[\ue000-\ue01f]")
DOCTYPE = '<!DOCTYPE keyboard SYSTEM "file://localhost/System/Library/DTDs/KeyboardLayout.dtd">'


class PathError(Exception):
    pass


class Keylayout:
    def __init__(self, root):
        self.root = root
        self.actions_el = root.find("actions")
        self.actions = {a.get("id"): a for a in self.actions_el}
        self.maps = {
            int(km.get("index")): {int(k.get("code")): k for k in km} for km in root.find("keyMapSet")
        }

    @property
    def name(self):
        return self.root.get("name")

    @property
    def id(self):
        return int(self.root.get("id"))

    def codes(self, index):
        return sorted(self.maps[index])

    def states(self, index, code):
        """What the key produces per dead-key state; a dead key shows as (output, next)."""
        el = self.maps[index].get(code)
        if el is None:
            return {}
        if el.get("output") is not None:
            return {"none": el.get("output")}
        return {w.get("state"): _when_value(w) for w in self.actions[el.get("action")]}

    def letters(self):
        return {code: self.states(0, code)["none"] for code in LETTER_CODES}


def _when_value(when):
    if when.get("next") is None:
        return when.get("output")
    return (when.get("output"), when.get("next"))


def parse_keylayout(text):
    if PUA_RANGE.search(text):
        raise ValueError("keylayout already contains private-use characters U+E000..U+E01F")
    text = CONTROL_REF.sub(lambda m: chr(0xE000 + int(m.group(1), 16)), text)
    return Keylayout(ET.fromstring(text.encode("utf-8")))


def load_keylayout(path):
    return parse_keylayout(pathlib.Path(path).read_text(encoding="utf-8"))


# Pictures and paths


def parse_picture(lines):
    """Four rows of key labels, digits first, into {key code: letter}."""
    rows = [line.split() for line in lines if line.strip()]
    if [len(r) for r in rows] != [len(r) for r in ROWS]:
        raise PathError(f"expected rows of {[len(r) for r in ROWS]} keys, got {[len(r) for r in rows]}")
    if "".join(rows[0][:10]) != DIGITS:
        raise PathError("the first row must start with the digits 1 to 0")
    mapping = {}
    for codes, tokens in zip(ROWS, rows):
        for code, token in zip(codes, tokens):
            if len(token) != 1:
                raise PathError(f"{token!r} is not a single character")
            mapping[code] = token
    return {code: mapping[code] for code in LETTER_CODES}


def picture(mapping, mark=frozenset()):
    def label(code):
        char = mapping[code]
        return {"ß": "ẞ"}.get(char, char.upper()) if char in mark else char

    out = [" ".join(DIGITS) + " " + label(ROWS[0][10])]
    for row in ROWS[1:]:
        out.append(" ".join(label(code) for code in row))
    return "\n".join(out)


class Stage:
    def __init__(self, name, mapping, parked, previous):
        self.name = name
        self.mapping = mapping
        self.parked = parked
        key_of = {letter: code for code, letter in mapping.items()}
        prev_key_of = {letter: code for code, letter in previous.items()} if previous else key_of
        self.moved = {letter for letter, code in key_of.items() if prev_key_of[letter] != code}

    @property
    def arrived(self):
        return self.moved - self.parked


class Path:
    def __init__(self, source, stages):
        self.source = source
        self.stages = stages


def parse_path(text, target):
    """Blocks separated by blank lines: `layout: name`, four rows, optional `parked: x y`."""
    blocks, block = [], []
    for line in text.splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            if block:
                blocks.append(block)
                block = []
        else:
            block.append(line)
    if block:
        blocks.append(block)
    if len(blocks) < 2:
        raise PathError("a path needs a source block and at least one stage")

    letters = set(target.values())
    stages, previous = [], None
    for block in blocks:
        fields = dict(line.split(":", 1) for line in block if ":" in line)
        name = fields.get("layout", "").strip()
        if not name:
            raise PathError("every block needs a `layout:` line")
        parked = set(fields.get("parked", "").split())
        mapping = parse_picture([line for line in block if ":" not in line])
        if set(mapping.values()) != letters or len(set(mapping.values())) != len(mapping):
            raise PathError(f"{name}: the keys must hold exactly {''.join(sorted(letters))}, each once")
        stage = Stage(name, mapping, parked, previous)
        if previous is not None:
            _check_moves(stage, previous, target)
        stages.append(stage)
        previous = mapping
    return Path(stages[0], stages[1:])


def _check_moves(stage, previous, target):
    key_of = {letter: code for code, letter in stage.mapping.items()}
    prev_key_of = {letter: code for code, letter in previous.items()}
    final_key_of = {letter: code for code, letter in target.items()}
    stray, left, idle = [], [], []
    for letter, code in sorted(key_of.items()):
        final, before = final_key_of[letter], prev_key_of[letter]
        if code == final:
            if letter in stage.parked:
                idle.append(letter)
        elif before == final:
            left.append(letter)
        elif code != before and letter not in stage.parked:
            stray.append(letter)
    problems = []
    if left:
        problems.append(f"{left} leave their Bone position")
    if stray:
        problems.append(f"{stray} move to a key that is neither their Bone position nor declared parked")
    if idle:
        problems.append(f"{idle} are declared parked but sit on their Bone position")
    if problems:
        raise PathError(f"{stage.name}: " + "; ".join(problems))


def cycles(source, target):
    """Cycles of the permutation, each written as the letters in the order they chase each other:
    a → r means a moves onto the key that types r in the source."""
    key_of = {letter: code for code, letter in source.items()}
    final_key_of = {letter: code for code, letter in target.items()}
    seen, out = set(), []
    for letter in source.values():
        if letter in seen or key_of[letter] == final_key_of[letter]:
            continue
        cycle, current = [], letter
        while current not in seen:
            seen.add(current)
            cycle.append(current)
            current = source[final_key_of[current]]
        start = cycle.index(max(cycle, key=lambda letter: FREQ.get(letter, 0.0)))
        out.append(cycle[start:] + cycle[:start])
    return out


def share(letters):
    return sum(FREQ.get(letter, 0.0) for letter in letters)


# Generation


def generate(bone, stage):
    new = Keylayout(copy.deepcopy(bone.root))
    new.root.set("name", stage.name)
    bone_key_of = {letter: code for code, letter in bone.letters().items()}
    for code, letter in stage.mapping.items():
        source = bone_key_of[letter]
        if source == code:
            continue
        for index in new.maps:
            if index in PHYSICAL_MAPS:
                continue
            kind, value = _compose(
                new,
                index,
                letter,
                code,
                bone.maps[index][source],
                bone.maps[index][code],
            )
            el = new.maps[index][code]
            for attr in ("output", "action"):
                if attr in el.attrib:
                    del el.attrib[attr]
            el.set(kind, value)
    return new


def _whens(layout, el):
    if el.get("output") is not None:
        return {"none": ET.Element("when", state="none", output=el.get("output"))}
    return {w.get("state"): copy.deepcopy(w) for w in layout.actions[el.get("action")]}


def _compose(layout, index, letter, code, letter_el, physical_el):
    """The entry for a key holding a letter from elsewhere: letter-bound states from
    the letter's key, physical states from the key itself."""
    whens = {s: w for s, w in _whens(layout, letter_el).items() if not _is_physical(index, s)}
    whens.update({s: w for s, w in _whens(layout, physical_el).items() if _is_physical(index, s)})

    if list(whens) == ["none"] and set(whens["none"].attrib) == {"state", "output"}:
        return "output", whens["none"].get("output")
    signature = _signature(whens.values())
    for action in layout.actions_el:
        if _signature(action) == signature:
            return "action", action.get("id")
    action = ET.SubElement(layout.actions_el, "action", id=f"charon {letter}@{code}/{index}")
    action.tail = "\n    "
    for when in sorted(whens.values(), key=lambda w: w.get("state")):
        action.append(when)
    layout.actions[action.get("id")] = action
    return "action", action.get("id")


def _is_physical(index, state):
    if index == GREEK_MAP:
        return False
    if index == CMD_MAP:
        return state != "none"
    return state in PHYSICAL_STATES


def _signature(whens):
    return frozenset((w.get("state"), tuple(sorted(w.attrib.items()))) for w in whens)


def render(layout, kb_id):
    root = copy.deepcopy(layout.root)
    root.set("id", str(kb_id))
    body = ET.tostring(root, encoding="unicode")
    body = PUA_RANGE.sub(lambda m: "&#x%04X;" % (ord(m.group()) - 0xE000), body)
    comment = f"<!--Generated by charon, do not edit: {layout.name}, assembled from the Bone keylayout-->"
    return f'<?xml version="1.1" encoding="UTF-8"?>\n{DOCTYPE}\n{comment}\n{body}\n'


def assign_ids(material, reserved=frozenset()):
    """A negative id per layout, derived from its content so a regenerated layout never
    collides with the copy HIToolbox may still have cached under the old id."""
    if not isinstance(material, dict):
        material = {name: name for name in material}
    taken, ids = set(reserved), {}
    for name, text in material.items():
        candidate = 1000 + int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16) % 30000
        while -candidate in taken:
            candidate = 1000 + (candidate + 1 - 1000) % 30000
        ids[name] = -candidate
        taken.add(-candidate)
    return ids


def build_bundle(target_path, path_files, out, bundle_id="io.kilian.charon"):
    bone = load_keylayout(target_path)
    stages = []
    for path_file in path_files:
        path = parse_path(pathlib.Path(path_file).read_text(encoding="utf-8"), bone.letters())
        stages += [stage for stage in path.stages if stage.mapping != bone.letters()]
    names = [stage.name for stage in stages]
    if len(set(names)) != len(names):
        raise PathError(f"duplicate layout names across path files: {names}")

    layouts = {stage.name: generate(bone, stage) for stage in stages}
    ids = assign_ids(
        {name: render(layout, 0) for name, layout in layouts.items()},
        NEO_IDS | {bone.id},
    )

    out = pathlib.Path(out)
    resources = out / "Contents" / "Resources"
    (resources / "de.lproj").mkdir(parents=True, exist_ok=True)
    for name, layout in layouts.items():
        (resources / f"{name}.keylayout").write_text(render(layout, ids[name]), encoding="utf-8")
    info = {
        "CFBundleIdentifier": bundle_id,
        "CFBundleName": out.stem,
        "CFBundleVersion": "1.0",
    }
    for name in names:
        info[f"KLInfo_{name}"] = {
            "TISInputSourceID": f"{bundle_id}.{name.lower().replace(' ', '')}",
            "TISIntendedLanguage": "de",
        }
    with open(out / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump(info, fh, sort_keys=False)
    strings = "".join(f'"{name}" = "{name}";\n' for name in names)
    (resources / "de.lproj" / "InfoPlist.strings").write_bytes(strings.encode("utf-16"))
    return out


# Command line


def cmd_show(args):
    bone = load_keylayout(args.target)
    for path_file in args.paths:
        path = parse_path(pathlib.Path(path_file).read_text(encoding="utf-8"), bone.letters())
        print(f"{path_file}: from {path.source.name} to {bone.name}")
        for cycle in cycles(path.source.mapping, bone.letters()):
            print(f"  cycle ({len(cycle)}, {share(cycle):.0f}%): {' → '.join(cycle)}")
        print()
        for stage in path.stages:
            parts = []
            if stage.arrived:
                parts.append("arrived " + " ".join(sorted(stage.arrived)))
            if stage.parked:
                parts.append("parked " + " ".join(sorted(stage.parked)))
            weight = f"{len(stage.moved)} keys, {share(stage.moved):.0f}% of text"
            print(f"{stage.name}: {weight}, {', '.join(parts)}")
            print("    " + picture(stage.mapping, stage.moved).replace("\n", "\n    "))
            print()


def cmd_build(args):
    out = build_bundle(args.target, args.paths, args.out)
    print(f"wrote {out}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--target", required=True, help="the Bone keylayout to assemble from")
    common.add_argument("paths", nargs="+", help="path files, see paths/")
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show", parents=[common], help="print the stages of one or more path files")
    show.set_defaults(func=cmd_show)
    build = sub.add_parser("build", parents=[common], help="generate a keyboard layout bundle")
    build.add_argument("--out", required=True, help="bundle directory to write, e.g. Charon.bundle")
    build.set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except PathError as err:
        sys.exit(f"error: {err}")


if __name__ == "__main__":
    main()
