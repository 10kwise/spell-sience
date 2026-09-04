"""Persistence. One JSON file, written at quiet pockets only.

Saving anywhere would remove the only thing that makes a quiet pocket worth
crossing a region for. Saving on a timer would make death free. So it saves
where the game says it is safe, and nowhere else, and the player learns the
shape of the map partly as a map of where they are allowed to stop."""

import json
import os

SAVE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "clade_save.json")


def write(game, path=None):
    data = {
        "version": 1,
        "body": game.body.to_dict(),
        "codex": game.codex.to_dict(),
        "room": game.world.room_key,
        "checkpoint": game.checkpoint,
        "discovered": sorted(game.world.discovered),
        "picked_up": sorted(game.world.picked_up),
        "opened": [list(o) for o in game.world.opened],
        "flags": sorted(game.world.flags),
        "stats": {
            "deaths": game.player.deaths,
            "harvests": game.player.harvests,
            "peaceful_harvests": game.player.peaceful_harvests,
            "spared": game.player.spared,
            "time": round(game.playtime, 1),
        },
    }
    p = path or SAVE_PATH
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, p)
    return p


def read(path=None):
    p = path or SAVE_PATH
    if not os.path.exists(p):
        return None
    try:
        with open(p) as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def exists(path=None):
    return os.path.exists(path or SAVE_PATH)


def clear(path=None):
    p = path or SAVE_PATH
    if os.path.exists(p):
        os.remove(p)
