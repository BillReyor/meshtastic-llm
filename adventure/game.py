import json
import os
import random
from typing import Dict, List, Tuple


class Parser:
    directions = {
        "n": "north",
        "s": "south",
        "e": "east",
        "w": "west",
        "u": "up",
        "d": "down",
    }

    def parse(self, text: str) -> List[Tuple[str, str, str]]:
        commands = []
        text = text.lower().strip()
        for part in text.split(" and "):
            tokens = part.split()
            if not tokens:
                continue
            if tokens[0] in self.directions:
                verb = self.directions[tokens[0]]
            else:
                verb = tokens[0]
            noun = tokens[1] if len(tokens) > 1 else ""
            prep = tokens[2] if len(tokens) > 2 else ""
            commands.append((verb, noun, prep))
        return commands


class Item:
    def __init__(self, name: str, weight: int, desc: str, can_carry: bool=True):
        self.name = name
        self.weight = weight
        self.desc = desc
        self.can_carry = can_carry

    def __repr__(self):
        return self.name


class Room:
    def __init__(self, data: Dict):
        self.id = data["id"]
        self.name = data["name"]
        self.desc = data["desc"]
        self.exits = data["exits"]
        self.item_names = data.get("items", [])
        self.state = data.get("state", {"lit": True, "locked": False})
        self.items: List[Item] = []


class Game:
    max_weight = 10

    def __init__(self, data_path: str = None):
        self.parser = Parser()
        self.verbose = False
        self.move_count = 0
        self.score = 0
        self.total_score = 100
        self.thief_has_item = None
        self.thief_room = 30
        data_path = data_path or os.path.join(os.path.dirname(__file__), "world.json")
        with open(data_path) as f:
            data = json.load(f)
        self.items: Dict[str, Item] = {}
        for key, val in data["items"].items():
            self.items[key] = Item(**val)
        self.rooms: Dict[int, Room] = {}
        for rdata in data["rooms"]:
            room = Room(rdata)
            room.items = [self.items[name] for name in room.item_names]
            self.rooms[room.id] = room
        self.player_room = 1
        self.inventory: List[Item] = []
        self.locked_doors = {10: {"east": True}}
        self.required_items = {"lamp": False, "key": False, "lockpick": False}
        self.use_actions = {
            ("lamp", ""): self._use_lamp,
            ("key", "door"): self.unlock_door,
            ("lockpick", "door"): self.unlock_door,
            ("scroll", ""): self._use_scroll,
            ("hope_badge", ""): self._use_hope_badge,
            ("hope_schedule", ""): self._use_hope_schedule,
        }

    def current_room(self) -> Room:
        return self.rooms[self.player_room]

    def current_weight(self) -> int:
        return sum(item.weight for item in self.inventory)

    def do_look(self, *_):
        room = self.current_room()
        print(f"Room {room.id}: {room.name}")
        if self.verbose or room.state.get("first", True):
            print(room.desc)
            room.state["first"] = False
        print("Exits: ", ", ".join(room.exits.keys()))
        if room.items:
            print("You see:", ", ".join(i.name for i in room.items))

    def do_examine(self, noun, *_):
        if noun in self.items:
            item = self.items[noun]
            print(item.desc)
        else:
            print("You see nothing special about it.")

    def do_take(self, noun, *_):
        room = self.current_room()
        item = next((i for i in room.items if i.name == noun), None)
        if not item:
            print("There is no such item here.")
            return
        if not item.can_carry:
            print("You cannot carry that.")
            return
        if self.current_weight() + item.weight > self.max_weight:
            print("Your load is too heavy.")
            return
        room.items.remove(item)
        self.inventory.append(item)
        if item.name == "treasure":
            self.score += 10
        print("Taken.")

    def do_drop(self, noun, *_):
        item = next((i for i in self.inventory if i.name == noun), None)
        if not item:
            print("You don't have that.")
            return
        self.inventory.remove(item)
        self.current_room().items.append(item)
        print("Dropped.")

    def do_inventory(self, *_):
        if not self.inventory:
            print("You are empty-handed.")
            return
        print("You are carrying:")
        for i in self.inventory:
            print(f"- {i.name} ({i.weight})")
        print(f"Total weight: {self.current_weight()}/{self.max_weight}")

    def do_score(self, *_):
        print(f"Score: {self.score}/{self.total_score}")

    def do_moves(self, *_):
        print(f"Moves: {self.move_count}")

    def do_save(self, noun="save.json", *_):
        state = {
            "player_room": self.player_room,
            "inventory": [i.name for i in self.inventory],
            "rooms": {rid: r.state for rid, r in self.rooms.items()},
            "score": self.score,
            "move_count": self.move_count,
            "thief_has_item": self.thief_has_item,
        }
        with open(noun, "w") as f:
            json.dump(state, f)
        print("Saved.")

    def do_restore(self, noun="save.json", *_):
        try:
            with open(noun) as f:
                state = json.load(f)
        except Exception:
            print("Unable to load; start new game?")
            return
        self.player_room = state["player_room"]
        self.inventory = [self.items[name] for name in state["inventory"]]
        for rid, st in state["rooms"].items():
            self.rooms[int(rid)].state = st
        self.score = state.get("score", 0)
        self.move_count = state.get("move_count", 0)
        self.thief_has_item = state.get("thief_has_item")
        print("Restored.")

    def do_use(self, noun, prep, *_):
        action = self.use_actions.get((noun, prep))
        if action:
            action()
        else:
            print("Nothing happens.")

    def _use_lamp(self):
        self.required_items["lamp"] = True
        print("The lamp is now lit.")

    def _use_scroll(self):
        print("The scroll reveals a secret: score +5!")
        self.score += 5

    def _use_hope_badge(self):
        print(
            "You flash your HOPE 16 badge. A volunteer hands you a zine on lock-picking. Score +16!"
        )
        self.score += 16

    def _use_hope_schedule(self):
        print(
            "The schedule lists talks, workshops, and villages running day and night. Score +5!"
        )
        self.score += 5

    def unlock_door(self):
        if not self.locked_doors.get(10, {}).get("east"):
            print("The door is already unlocked.")
            return
        self.locked_doors[10]["east"] = False
        print("The door unlocks.")
        self.score += 5

    def do_move(self, direction):
        room = self.current_room()
        if direction not in room.exits:
            print("You can't go that way.")
            return
        if self.locked_doors.get(room.id, {}).get(direction):
            print("The way is locked.")
            return
        new_room = room.exits[direction]
        self.player_room = new_room
        if self.inventory and random.random() < 0.1 and not self.thief_has_item:
            stolen = random.choice(self.inventory)
            self.inventory.remove(stolen)
            self.rooms[self.thief_room].items.append(stolen)
            self.thief_has_item = stolen.name
            print(f"A thief snatches your {stolen.name} and runs away!")
        room = self.current_room()
        if room.id == self.thief_room and self.thief_has_item:
            item = next(i for i in room.items if i.name == self.thief_has_item)
            room.items.remove(item)
            self.inventory.append(item)
            print(f"You reclaim your {item.name} from the thief.")
            self.thief_has_item = None
        if not room.state.get("lit") and not self.required_items["lamp"]:
            print("It is pitch dark.")
        else:
            self.do_look()

    def do_verbose(self, *_):
        self.verbose = not self.verbose
        print("Verbose" if self.verbose else "Brief")

    def do_hope(self, *_):
        print("HOPE (Hackers On Planet Earth) is an annual hacker con blending tech, activism, and art. Workshops, villages, and performances run day and night. Everyone is welcome!")

    def unknown(self, verb, *_):
        print(f"I don't know the word '{verb}'; try LOOK or EXAMINE")

    def run_command(self, verb, noun, prep):
        self.move_count += 1
        if verb in ("north", "south", "east", "west", "up", "down"):
            self.do_move(verb)
            return
        func = getattr(self, f"do_{verb}", None)
        if func:
            func(noun, prep)
        else:
            self.unknown(verb)

    def loop(self):
        self.do_look()
        while True:
            cmd = input("> ")
            for verb, noun, prep in self.parser.parse(cmd):
                self.run_command(verb, noun, prep)


if __name__ == "__main__":
    Game().loop()
