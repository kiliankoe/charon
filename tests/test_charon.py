import pathlib
import plistlib
import sys
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import charon  # noqa: E402

BONE = ROOT / "upstream" / "Deutsch (Bone).keylayout"
NEOQWERTZ = ROOT / "upstream" / "Deutsch (NeoQwertz).keylayout"
PATH = ROOT / "paths" / "charon.txt"
STAGE0 = ROOT / "paths" / "stage0.txt"


def picture(text):
    return charon.parse_picture(textwrap.dedent(text).strip().splitlines())


CHARON0 = picture("""
    1 2 3 4 5 6 7 8 9 0 ß
    q w e r t y u i o p ü
    a s d f g h j k l ö ä
    z x c v b n m , . -
""")


class Cycles(unittest.TestCase):
    def setUp(self):
        self.bone = charon.load_keylayout(BONE).letters()

    def test_swapped_neoqwertz_splits_into_three_cycles(self):
        cycles = charon.cycles(CHARON0, self.bone)
        by_len = {len(c): set(c) for c in cycles}
        self.assertEqual(sorted(by_len), [7, 10, 14])
        self.assertEqual(by_len[7], set("ark-ßüc"))
        self.assertEqual(by_len[10], set("bhuefzmogö"))
        self.assertEqual(by_len[14], set("dwpynjqävxtsli"))

    def test_official_neoqwertz_has_a_24_cycle(self):
        official = charon.load_keylayout(NEOQWERTZ).letters()
        self.assertEqual(sorted(len(c) for c in charon.cycles(official, self.bone)), [7, 24])

    def test_frequency_share(self):
        self.assertAlmostEqual(charon.share("arkßüc-"), 18.7, places=1)
        self.assertAlmostEqual(charon.share("efzmog"), 28.2, places=1)


class Paths(unittest.TestCase):
    def setUp(self):
        self.bone = charon.load_keylayout(BONE).letters()

    def test_shipped_path_is_valid(self):
        path = charon.parse_path(PATH.read_text(), self.bone)
        self.assertEqual(
            [b.name for b in path.stages],
            ["Charon 1", "Charon 2", "Charon 3", "Charon 4", "Bone"],
        )
        self.assertEqual(path.stages[1].parked, {"ö"})
        self.assertEqual(path.stages[-1].mapping, self.bone)

    def test_stage0_path_is_valid(self):
        path = charon.parse_path(STAGE0.read_text(), self.bone)
        self.assertEqual(path.stages[0].parked, {"y", "z"})

    def test_moved_key_must_reach_its_final_position_or_be_parked(self):
        text = PATH.read_text().replace("z x ü v b n m , . k", "z x ü v b n k , . m")
        with self.assertRaisesRegex(charon.PathError, "Charon 1.*'k'"):
            charon.parse_path(text, self.bone)

    def test_final_position_is_never_left(self):
        # Charon 2 as shipped, but with a and r swapped back after they arrived in Charon 1.
        text = (
            PATH.read_text()
            .replace("q w ö a t y u i m p ß", "q w ö r t y u i m p ß")
            .replace("c s d e o h j r l g ä", "c s d e o h j a l g ä")
        )
        with self.assertRaisesRegex(charon.PathError, "Charon 2.*'a'"):
            charon.parse_path(text, self.bone)

    def test_letter_set_must_match_target(self):
        text = PATH.read_text().replace("z x c v b n m , . -", "z x c v b n m , . x")
        with self.assertRaisesRegex(charon.PathError, "Charon 0"):
            charon.parse_path(text, self.bone)


class Generation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bone = charon.load_keylayout(BONE)
        path = charon.parse_path(PATH.read_text(), cls.bone.letters())
        cls.stage1 = charon.generate(cls.bone, path.stages[0])
        cls.final = charon.generate(cls.bone, path.stages[-1])

    def test_final_stage_equals_bone_on_every_key_and_state(self):
        for index in range(10):
            for code in self.bone.codes(index):
                self.assertEqual(
                    self.final.states(index, code),
                    self.bone.states(index, code),
                    (index, code),
                )

    def test_letter_layers_follow_the_letter(self):
        s = self.stage1.states
        # a moved from the a key (code 0) to the r key (code 15).
        self.assertEqual(s(0, 15)["none"], "a")
        self.assertEqual(s(1, 15)["none"], "A")
        self.assertEqual(s(0, 15)["Ebene 1 T3 Akut"], "á")
        self.assertEqual(s(5, 15)["none"], "α")
        self.assertEqual(s(7, 15)["none"], "a")
        # c moved onto the a key.
        self.assertEqual(s(0, 0)["none"], "c")
        self.assertEqual(s(5, 0)["none"], "χ")
        # k moved onto the - key, - onto the ß key, ß onto the ü key.
        self.assertEqual(s(0, 44)["none"], "k")
        self.assertEqual(s(1, 44)["none"], "K")
        self.assertEqual(s(0, 27)["none"], "-")
        self.assertEqual(s(1, 27)["none"], "—")
        self.assertEqual(s(0, 33)["none"], "ß")
        self.assertEqual(s(1, 33)["none"], "ẞ")

    def test_layers_three_and_four_stay_on_the_physical_key(self):
        s, b = self.stage1.states, self.bone.states
        # The r key keeps its layer 3 bracket whichever letter sits on it.
        self.assertEqual(s(0, 15)["Bugfixes"], "]")
        self.assertEqual(s(4, 15), b(4, 15))
        self.assertEqual(s(0, 0)["Bugfixes"], "\\")
        self.assertEqual(s(0, 44)["Bugfixes"], ";")
        self.assertEqual(s(0, 33)["Bugfixes"], "ſ")
        self.assertEqual(s(0, 8)["Bugfixes"], "|")
        # Layer 4 arrives through the shift map; ¡ and ¿ belong to the y and h keys.
        self.assertEqual(s(1, 16)["Ebene 4 und 6"], "¡")
        self.assertEqual(s(1, 4)["Ebene 4 und 6"], "¿")
        # The Ctrl layer is left exactly as Bone ships it.
        for code in self.bone.codes(8):
            self.assertEqual(s(8, code), b(8, code))

    def test_unmoved_keys_keep_bone_letter_data_at_their_old_place(self):
        s = self.stage1.states
        self.assertEqual(s(0, 14)["none"], "e")
        self.assertEqual(s(0, 14)["Ebene 1 T3 Akut"], "é")
        self.assertEqual(s(0, 14)["Bugfixes"], "[")
        self.assertEqual(s(5, 14)["none"], "ε")
        self.assertEqual(s(5, 38)["Ebene 4 und 6"], "Θ")  # j key, still types j in Charon 1
        self.assertEqual(s(5, 45)["Ebene 4 und 6"], "ℕ")  # n key, likewise

    def test_render_is_xml_1_1_with_control_references(self):
        text = charon.render(self.stage1, kb_id=-1234)
        self.assertTrue(text.startswith('<?xml version="1.1" encoding="UTF-8"?>\n<!DOCTYPE keyboard'))
        self.assertIn('id="-1234" name="Charon 1"', text)
        self.assertIn("&#x001B;", text)
        self.assertNotRegex(text, "[\ue000-\ue01f]")
        again = charon.parse_keylayout(text)
        for index in range(10):
            for code in self.stage1.codes(index):
                self.assertEqual(again.states(index, code), self.stage1.states(index, code))

    def test_ids_are_negative_and_unique(self):
        ids = charon.assign_ids(
            ["Charon 0", "Charon 1", "Charon 2", "Charon 3", "Charon 4"],
            reserved={-5743},
        )
        self.assertEqual(len(set(ids.values())), 5)
        self.assertTrue(all(-32768 < i < 0 for i in ids.values()))
        self.assertNotIn(-5743, ids.values())
        self.assertEqual(ids, charon.assign_ids(list(ids), reserved={-5743}))


class Bundle(unittest.TestCase):
    def test_build_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "Charon.bundle"
            charon.build_bundle(BONE, [STAGE0, PATH], out)
            resources = out / "Contents" / "Resources"
            names = sorted(p.stem for p in resources.glob("*.keylayout"))
            self.assertEqual(names, ["Charon 0", "Charon 1", "Charon 2", "Charon 3", "Charon 4"])
            with open(out / "Contents" / "Info.plist", "rb") as fh:
                info = plistlib.load(fh)
            self.assertEqual(info["CFBundleIdentifier"], "io.kilian.charon")
            self.assertEqual(info["KLInfo_Charon 1"]["TISInputSourceID"], "io.kilian.charon.charon1")
            self.assertEqual(info["KLInfo_Charon 1"]["TISIntendedLanguage"], "de")
            strings = (resources / "de.lproj" / "InfoPlist.strings").read_bytes().decode("utf-16")
            self.assertIn('"Charon 4" = "Charon 4";', strings)


if __name__ == "__main__":
    unittest.main()
