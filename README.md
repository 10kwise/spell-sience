# CLADE

*a clade of one*

An underwater survival horror metroidvania about a made thing, in a drowned
place, looking for another of its kind.

```
pip install -r requirements.txt
python play.py
```

---

## You are built out of what you kill

That is the whole game, seen from four sides.

You do not craft items. You have a **body with empty sockets**, and you fill
them with **organs** taken from the dead. Organs have no effects — they have
intakes and vents, and what they *do* is decided by what you plumb them
into. You route a chain through adjacent sockets:

```
INTAKE  →  transform  →  transform  →  VENT
```

Each transform rewrites a four-part humour vector **in place**, so the order
is the design:

| chain | result |
|---|---|
| `Salt Node → Kiln` | doubles the weight, then burns the doubled weight. **a lance.** |
| `Kiln → Salt Node` | burns the weight first, then doubles a weight that is no longer there. **a cough.** |

Same two organs. Measured, a 3.7× difference in damage. Nothing in the code
special-cases either arrangement; it falls out of running the functions in
the order you laid them.

## The four humours

Everything that flows through you, through every creature, and through the
water itself is a mixture of four things.

| | | |
|---|---|---|
| `~` | **BRINE** | mass, density, pressure. force. sinking. |
| `*` | **ICHOR** | metabolic fuel. heat. light — and light is being seen. |
| `.` | **SILT** | sediment. obscurity, and slow decay. |
| `!` | **SPARK** | nerve. speed, precision, and pain. |

**There is no effect table anywhere in this game.** What a mixture does is
computed from the vector — force from brine, heat from ichor, murk from
silt, jolt from spark, rot from ichor×silt, and so on. A mixture nobody
designed still behaves sensibly, and two players who reach the same vector
by different routes get identical results. That is the difference between a
system you can *learn* and one you can only memorise.

## Divergence: the two-sided key

**Divergence** measures how far a mixture is from equal parts, and it is the
spine of everything.

- **A spike** — one humour, nearly pure — is powerful and **loud**.
  `loudness = magnitude × divergence`, which is also very nearly the formula
  for a weapon.
- **A balance** — all four in rough proportion — does no damage at all, is
  silent, and is what living tissue answers to.

The doors in this place are alive. You cannot force them. Progression gates
are not keys; they are the sentence *"build a body capable of gentleness"* —
which is mechanically the opposite of everything twelve hours of combat will
have taught you. Making a key costs a wide intake and three or four organs,
because the two organs that even out a mixture both destroy magnitude doing
it, and gentleness scales with magnitude.

## Heat closes the loop

An organ that works gets hot. Heat crawls to its **grid neighbours**, and
what does not crawl radiates into the water — where it becomes light, and
light is how you are found.

So the layout of your body is a thermal problem as much as a logical one.
Put the Ember Gland next to the Ganglion and the Ganglion seizes. Put it on
the rim and the room can see you. There is no correct layout, only the one
you can live with, and it changes every time you find a new organ.

Heat is not a balance tax bolted onto strong organs. It is one quantity
doing the same thing in three places.

## The water is a supply line

Four regions, four kinds of water, and your intakes pull whatever is around
you:

| region | water | |
|---|---|---|
| **The Nursery** | warm, organic, ichor-rich | *warm. it has not finished being alive.* |
| **The Cisterns** | thick with sediment | *thick. the light stops about an arm out.* |
| **The Lattice** | live, spark-rich | *it still has power. nobody has ever explained that.* |
| **The Sill** | cold, dense brine | *cold, and old, and it goes down further than the building.* |

And underneath the bestiary runs one ecological rule: **things are armoured
against the water they live in.** So in every region after the first, the
humour the water hands you for free is the one the locals are hardest to
hurt with. The Lattice is thick with live water and everything in it shrugs
off nerve — the region gives you the wrong answer for nothing and charges
you a conversion toll for the right one.

Which makes your reserve a supply line. A body that fills up on warm Nursery
water and carries it down into the Cisterns is carrying ammunition that
cannot be bought locally.

## Traversal is buoyancy

Your brine fraction against neutral decides whether you sink or rise. Heavy
bodies walk the floor; light bodies climb shafts. The game's "double jump"
is a **negative number** — a Mirror Sac inverting brine — and nobody had to
write a jump button.

## The dark

You see by your own glow, and your glow is a readout of what you are
carrying. A body full of heat burns orange and can be seen across a room. A
body full of sediment is nearly invisible and nearly blind.

Things outside your light are not drawn as shapes. They are drawn as **holes
in the water** — darker than the ground, moving. You do not see the Silt
Mother. You see the place where the water stops telling you anything, and
you watch that place move.

## Death

You do not reload. You **regress**: two organs come out of you and stay
where you fell, your reserve empties, and you wake at the last quiet pocket.
The organs are recoverable if you go back — unless something has eaten them,
in which case that thing now has your organs and is using them the same way
you would have.

It never takes your last intake or your last vent. It takes what it can
spare.

---

## Controls

| | |
|---|---|
| `WASD` | swim |
| mouse | aim |
| `LMB` `RMB` `Q` `E` | fire chains 1–4 |
| `SHIFT` / `SPACE` | surge — a shove out of your own back. costs brine. loud. |
| hold `F` | **feed.** put your mouth on a dead thing and take what it was made of. |
| `TAB` | the Bench — surgery and the Assay |
| `C` | the codex |
| `M` | the map |
| `ESC` | back |

**At the Bench:** click a socket to select, right-click to remove, click a
carried organ then a socket to install. `1`–`4` route a chain (click sockets
in order, press the number again to keep it). `SPACE` runs the **Assay** —
fires the chain into nothing and prints the humour vector after every organ,
free, safely, as many times as you like.

The Assay never tells you a damage number. It shows you the vector and one
line of plain observation. The last step is yours, and the last step is the
game.

---

## The lore

A hatchery in a subduction trench. The surface did not burn — it
**suffocated**; the oceans stratified and went dead from the top down. The
last project was not to preserve humans, it was to preserve *the part that
had not decided yet*, and to let it become whatever the new world required.

It grew candidates. It watched which ones persisted. It never intervened,
because intervening is how you get something that needs you.

Every creature down here is a candidate. So are you.

The full account is in [`LORE.md`](LORE.md) — including the ending, so do not
read it first.

---

## Verifying it

```
python -m clade.verify.selftest    # 71 assertions about the *design*
python -m clade.verify.playtest    # four bots of increasing understanding
python -m clade.verify.shots       # renders the game to shots/ with no display
```

`selftest.py` does not check that the code runs. It checks the claims the
game makes to the player, each written as something that can fail — that
ordering still matters, that a balanced charge still opens tissue and still
does no damage, that the Muffle is still a good trade, that a focused attack
still feeds a Recursor, that the whole route from the tank to the sill can
still be walked. Those failures are invisible from playing for ten minutes
and fatal over twelve hours.

`playtest.py` runs four bots that differ **only in how much they understand**
— they share navigation, aim and reflexes. It asserts the ladder holds:
feeding gets you more parts, minding the noise keeps you quieter,
understanding your own body opens more of the map.

```
bot        rooms  deep  deaths  organs  frags  kills  harv   noise
flail        6.0   1.0     1.0     4.0    4.0   14.0   0.0    42.8
feeder       6.0   1.0     1.0    21.0    4.0   12.2  11.0    39.8
quiet        6.0   1.0     0.2    24.0    4.0   13.2  12.5    39.1
plumber      6.0   1.0     1.0    23.2    4.0   14.2  13.2    40.3
```

---

## Layout

```
play.py                  entry point
clade/
  humours.py             the four humours, and divergence
  effects.py             what a mixture DOES — every rule, no tables
  organs.py              33 organs. the grammar.
  body.py                the socket grid, chain routing, heat, metabolism
  player.py              you. mostly buoyancy, feeding, and surging.
  creatures.py           17 species, all running the same organ grammar
  bestiary.py            the roster, and the ecology rule
  lore.py                18 fragments, and the codex that remembers them
  app.py                 states, input, death, and the two endings
  world/
    fields.py            heat, silt, current, charge — the water as state
    room.py              tile geometry, carving, doors and their locks
    atlas.py             39 rooms, 4 regions, and the gates between them
    live.py              the live world and the attention economy
  render/
    dark.py              the volumetric dark: lightmap, silhouettes, snow
    hud.py               four readouts, all of them things you can change
  screens/bench.py       surgery and the Assay
  verify/                selftest, playtest bots, screenshot renderer
attic/                   a previous, unrelated prototype. nothing imports it.
```

`attic/` is a wave-simulation game that used to live here. It is kept
because it was well built and self-tested, and it is untouched because
nothing in CLADE is built on it.
