# The Bench — what it affects, and what it could

A report, requested after the note that *"the bench is meant to have more
utility than a weapon designer."* That was right, and this is an honest
account of where it stands, what governs what can be added, and the
concrete things I would build next — including the ones I would not.

---

## 1. What it affects today

| | |
|---|---|
| **damage, range, shape** | fired chains: bolt, cone, aura, lob, beam, seed |
| **noise** | `loudness = magnitude × divergence`, and the Apex hunts it |
| **your own light** | ichor makes heat, heat makes light, light is how you are found |
| **doors** | balanced charges open grown tissue; rot eats through it |
| **terrain** | cold water freezes solid and blocks movement; rot dissolves tissue |
| **the water itself** | fire enriches ambient ichor, silt blocks sight, charge conducts |
| **buoyancy** | a standing chain with inverted brine is the game's only "jump" |
| **temperature** | a burning standing chain is the only way to survive the Sill |
| **concealment** | a sediment standing chain hides you *and* earths the Lattice |
| **regeneration** | a balanced standing chain is the only real healing |
| **speed** | a nerve standing chain quickens you and makes you fragile |
| **your upkeep** | everything above is paid for continuously, out of things you kill |

So it is already a life-support designer as well as a weapon designer. The
question is what else it should be.

---

## 2. The rule that governs any addition

Everything the Bench does is computed from one four-number vector by the
rules in `clade/effects.py`. There is no effect table anywhere, and adding
one would be the end of the design: the moment a feature needs a lookup,
the player can no longer *reason* about it, only memorise it.

So the test for every proposal below is:

> **Can this be derived from the humour vector by a rule that also explains
> something the player already knows?**

Anything that passes is cheap to build and impossible to make incoherent.
Anything that fails is a second game bolted to the side of this one.

---

## 3. Proposals

### A. The body itself

**A1 — Cavity shape and organ size.** *(recommended)*
Organs occupy one socket. Let some occupy two or three, in shapes. Suddenly
the grid is a packing problem as well as an ordering problem, thermal
neighbours become a real spatial negotiation, and "I have the parts but not
the room" becomes a sentence the game can say. Cost: moderate — install,
adjacency, and routing all need to understand multi-cell organs. Risk: it
makes the grid fiddly if the shapes are cruel; keep them to dominoes and
L-trominoes.

**A2 — Symmetry and the second body.** *(recommended)*
The grid is 6×5 and you never use all of it. Let the player run *two*
complete bodies and switch between them — a hunting configuration and a
travelling one — at the cost of a long, vulnerable, in-world transition.
This is the single cheapest way to make the Bench a strategic screen rather
than a maintenance screen, because it turns every build into a *choice
between builds*. Cost: low. Risk: it removes the pain of committing, which
is currently doing useful work.

**A3 — Organ fusion.** *(recommended, high value)*
Consume two organs to make a hybrid whose transform is the composition of
both, with a loss. `Kiln + Salt Node` becomes one socket that amplifies
then converts. This is *derived* — it is literally function composition, it
needs no new rules, and it gives the late game something to do with a pack
full of duplicates. It also creates the game's first real long-term goal
that is not "go deeper". Cost: low. Risk: fusion trivialises the packing
problem if it is free; it should cost integrity and be irreversible.

**A4 — Scar tissue and wear.** *(already half-built)*
Organs already have `integrity` and it barely matters. Let a worn organ's
transform drift — a Kiln that has been overheated a thousand times converts
*less* and leaks *more* — so a body accumulates a history and eventually
has to be rebuilt. Cost: trivial, the field exists. Risk: it punishes the
player for playing, which needs a counterweight (grafting fresh tissue).

### B. Perception

**B1 — Standing chains that change what you can see.** *(recommended)*
The most obvious missing utility. A standing chain already produces silt,
charge and heat; let those read *inward* as well as outward:

- **spark** → electroreception. Living things glow through rock, but the
  world's geometry does not. You see creatures and not walls.
- **silt** → you feel water displacement instead of seeing. Moving things
  are bright, still things are invisible — which makes the Silt Mother
  worse, not better.
- **ichor** → ordinary light, further, and everything sees you.
- **brine** → pressure sense. You feel the *shape* of the room, walls and
  all, but nothing alive in it.

Four standing chains, four completely different games, one existing rule
set. Cost: moderate (the renderer needs four modes). Risk: none I can see;
this is the strongest proposal in the document.

**B2 — The Assay as a field instrument.** *(recommended, cheap)*
Let the player point the Assay at a *creature* rather than at nothing, and
read its humour composition and resistances the way it reads a chain. Then
"what is this thing weak to" becomes something you find out by looking
rather than by dying. Cost: low. Risk: it removes some mystery; gate it
behind an organ so it is a build choice.

### C. The world

**C1 — Building, not just breaking.** *(recommended)*
Cold already freezes water into walls you can hide behind, and this is the
most under-used mechanic in the game. Extend it: silt deposits *settle*
into floor you can stand on, rot opens permanent holes, heat melts what
cold made. Give the player a reason to reshape a room and the Bench becomes
a level editor with consequences. Cost: moderate (terrain needs to persist
per room). Risk: sequence-breaking — which in a metroidvania is a feature
if the endings hold, and they do.

**C2 — Chains that run on the world instead of on you.** *(speculative)*
A standing chain vented into a *relay* you have stamped somewhere — a
remote lamp, a remote noise, a remote heat source that keeps a door thawed.
Cost: moderate. Risk: micromanagement.

### D. The ecology

**D1 — Creatures react to your composition.** *(recommended, cheap, and
the most thematically loaded thing here)*
Every creature already has a humour composition, and so do you. If a
creature's aggression read the *difference* between its composition and
yours, then a body built to resemble the local wildlife would simply be
attacked less — and the game's entire thesis is that you are made of what
you kill. Build yourself out of Cisterns organs and the Cisterns stop
minding you. Cost: about twenty lines. Risk: it makes stealth trivial
unless the resemblance also costs you something, and it should: what you
resemble, you are, and the deep regions are full of things you would not
want to be.

**D2 — Grafting from the living.** *(speculative)*
Take an organ from a creature *without* killing it — slower, riskier,
leaves it alive and hostile forever. A quiet route for a player who has
worked out what the ending wants. Cost: low. Risk: it telegraphs the
ending, which is precisely what the ending must not be.

### E. Information

**E1 — Named, saved loadouts.** *(recommended, cheap)*
The Shelf is prebuilt; let the player write to it. "Save this body as
*Cold Work*" and swap to it later. Pure quality of life and it costs
almost nothing now that the Shelf format exists. Cost: trivial.

**E2 — A diff view.** *(recommended, cheap)*
Assay two chains side by side. The Lance/Fizzle lesson currently requires
the player to remember four numbers between two screens. Cost: trivial.

---

## 4. What I said I would build next — and did

| | proposal | status |
|---|---|---|
| 1 | **B1** perception modes | **built.** nerve, weight, sediment and heat each see a different world |
| 2 | **D1** creatures read your composition | **built.** kinship; a silt body in the Cisterns is noticed half as much |
| 3 | **A3** organ fusion | **built.** `G` grafts two transforms into one socket at 86% |
| 4 | **E2** the diff | **built.** `V` holds an assay and notches it onto the next one |
| — | **speed / lure / ward** | **built**, on request — derived, not stats |
| 5 | **E1** named loadouts | not yet. trivial whenever it is wanted |
| 6 | **C1** building terrain | not yet. the biggest, and it wanted the others in place first |

---

## 5. What I would refuse, and why

**A skill tree, or anything that unlocks by spending.** Every capability in
this game is currently a *statement about your body right now*, which is
why it can be reasoned about. A permanent unlock is a lookup table with
extra steps.

**Recipes.** The moment the Bench has a recipe list, the Assay is
decoration and the player is reading a wiki. Fusion (A3) must be
compositional and discoverable, never enumerated.

**Numbers on organs.** They are measured and shown *derived* — "multiplies
brine by about 3.0, less the more of it you already have" — because that
sentence is true after any retune. A printed stat is a lie waiting to
happen.

**A second currency.** Four humours is already the limit of what can be
held in the head while aiming. Anything that needs a fifth resource is
really asking for a different game.
