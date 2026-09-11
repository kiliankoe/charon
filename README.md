# charon

Transitional keyboard layouts for moving from NeoQwertz to [Bone](https://neo-layout.org/Layouts/bone/) in stages, instead of switching cold. Named after the ferryman who carries you across to the other side, to where the bones are... I need help naming projects.

The idea is borrowed from DreymaR's [Tarmak](https://dreymar.colemak.org/tarmak-intro.html), the stepping stones from QWERTY to Colemak: each stage moves a small, closed set of keys straight to their final positions, so nothing is learnt twice and the keyboard never has a hole in it. The only exceptions are rare letters that get parked on a free key for one stage so that a large cycle can be split in two.

Peter Karp proposed a staged approach for the Neo family back in 2010 on the Neo mailing list, in the thread [Ein Layout Stück für Stück](https://www.mail-archive.com/diskussion@neo-layout.org/msg04979.html). As far as I can tell nothing realy came out of that, but it was a cool idea! This is that idea, more or less, but for bone instead of Neo.

Move through these layouts as you feel comfortable, but I think it makes sense not to dwell too long. It's probably time to migrate to the next stage once you no longer need to search for key. Getting to full speed is probably not worthwhile, an intermediate layout isn't worth perfecting.

> Important caveat: This transition starts out from NeoQwerty, not NeoQwertz. I came from years of typing on QWERTY keyboards and switched Y and Z on NeoQwertz to match my preference. I have so far not explored a transition path from NeoQwertz to Bone. If you use the layouts below, you're going to have to live with potentially relearning Y and Z first.

## Layouts

The letters that move between NeoQwertz and Bone form a permutation, and a permutation splits into cycles. With Y and Z at their QWERTY positions (that swap is stage 0) there are three:

```
cycle (7, 19%):   r → k → - → ß → ü → c → a
cycle (10, 40%):  e → f → z → m → o → g → ö → b → h → u
cycle (14, 44%):  n → j → q → ä → v → x → t → s → l → i → d → w → p → y
```

`a → r` reads as "a moves onto the key that types r", and the percentage is how much German text those letters make up. The 7-cycle is one stage. The other two are each split in half, with ö and q (0.3% and 0.02% of text) parked once so that the halves close. The result is five stages, and no letter but those two is ever learnt twice. Capitals in the pictures mark the keys that move in that stage, and the digit row shows the one number-row key that takes part, ß or hyphen.

```
Charon 0   from the official NeoQwertz: y and z swapped, both parked
    1 2 3 4 5 6 7 8 9 0 ß
    q w e r t Y u i o p ü
    a s d f g h j k l ö ä
    Z x c v b n m , . -

Charon 1   7 keys, 19% of text: a c k r ß ü and the hyphen
    1 2 3 4 5 6 7 8 9 0 -
    q w e A t y u i o p ẞ
    C s d f g h j R l ö ä
    z x Ü v b n m , . K

Charon 2   7 keys, 29% of text: e f g m o z, ö parked on the old e key
    1 2 3 4 5 6 7 8 9 0 -
    q w Ö a t y u i M p ß
    c s d E O h j r l G ä
    F x ü v b n Z , . k

Charon 3   4 keys, 11% of text: b h u ö
    1 2 3 4 5 6 7 8 9 0 -
    q w U a t y H i m p ß
    c s d e o B j r l g ä
    f x ü v Ö n z , . k

Charon 4   7 keys, 18% of text: d j n p w y, q parked on the old d key
    1 2 3 4 5 6 7 8 9 0 -
    J D u a t P h i m W ß
    c s Q e o b N r l g ä
    f x ü v ö Y z , . k

Bone       8 keys, 26% of text: i l q s t v x ä
    1 2 3 4 5 6 7 8 9 0 -
    j d u a X p h L m w ß
    c T I e o b n r S g Q
    f V ü Ä ö y z , . k
```

Charon 2 is the big one, it brings e and o to the home row. After it, most of the felt benefit of Bone is already there.

A three-stage route, one cycle per stage, needs no extra layouts: it is Charon 1, then Charon 3, then Bone, because the parked letters make the split stages nest.

Only layers 1 and 2 change between stages. Layers 3 to 6 are the same in every Neo family layout and stay where your fingers know them, see below.

## Install

```sh
nix build
# or, with any Python 3.9 or newer and no dependencies:
python3 charon.py build --target "upstream/Deutsch (Bone).keylayout" \
  --out Charon.bundle paths/stage0.txt paths/charon.txt
```

On macOS, copy `Charon.bundle` to `~/Library/Keyboard Layouts`, log out and back in, then enable the stage you are on under System Settings, Keyboard, Input Sources, German. Bone itself is not in the bundle: install the Neo project's own bundle for the final stage and for the layers the Charon layouts do not touch.

The bundle only defines layers 1 and 2 in a new arrangement. The Neo project's [Karabiner rules](https://neo-layout.org/Einrichtung/macOS/) for Mod3 and Mod4 keep working unchanged, because those layers stay on the physical keys.

Each layout's id is derived from its content, so a regenerated layout never collides with the copy macOS may still have cached under an old id.

## How the layouts are built

Everything is assembled from the official Bone keylayout. For each key, the generator takes the layers that belong to the letter from Bone's key for that letter, and the layers that belong to the physical key from Bone's entry for that key. What follows the letter is exactly what moves in Bone itself, which was read off a diff of the Bone and NeoQwertz files:

| follows the letter                             | stays on the key                                                                    |
| ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| layer 1 and 2, with caps lock                  | layer 3 (the Option maps and the `Bugfixes` dead-key state the Karabiner rules use) |
| accents and compose sequences (é lives with e) | layer 4 (the `Ebene 4 und 6` state)                                                 |
| layer 5, Greek (α stays with a)                | the Ctrl map, which upstream Bone keeps on QWERTZ positions                         |
| layer 6, mathematics (ℕ stays with n)          |                                                                                     |
| the Cmd map (Cmd+C on the key that types c)    |                                                                                     |

`upstream/` holds the two official files, fetched by `fetch-upstream.py` from the Neo project's primary repository at git.neo-layout.org, pinned to the commit in `upstream/COMMIT`. The Neo layouts are licensed under the GPL-3.0, and so are the layouts generated from them.

## Development

The repo ships a nix flake and a `.envrc`. `python3 -m unittest discover -s tests`, `ruff format .` and `ruff check .` should stay clean; `nix flake check` runs the tests.
