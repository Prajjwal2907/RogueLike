from __future__ import annotations

import random
from typing import Tuple, Iterator, List, TYPE_CHECKING

import tcod
import entity_factories
from game_map import GameMap
import tile_types

if TYPE_CHECKING:
    from engine import Engine

class RectangularRoom:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)

        return center_x, center_y

    @property
    def inner(self) -> Tuple[slice, slice]:
        """Return the inner area of this room as a 2D array index."""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: RectangularRoom) -> bool:
        """Return True if this room overlaps with another RectangularRoom."""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )


def place_entities(
    room: RectangularRoom, dungeon: GameMap, maximum_monsters: int,
) -> None:
    number_of_monsters = random.randint(0, maximum_monsters)

    for i in range(number_of_monsters):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            if random.random() < 0.8:
                entity_factories.orc.spawn(dungeon, x, y)
            else:
                entity_factories.troll.spawn(dungeon, x, y)


def generate_interior_walls(
    room: RectangularRoom,
    dungeon: GameMap,
    protected_tiles: set[Tuple[int, int]] | None = None,
    min_segments: int = 2,
    max_segments: int = 4,
) -> None:
    """Add short random wall segments inside a room without crossing passage tiles."""
    protected_tiles = set() if protected_tiles is None else set(protected_tiles)
    protected_tiles.update(
        {
            room.center,
            (room.center[0] + 1, room.center[1]),
            (room.center[0] - 1, room.center[1]),
            (room.center[0], room.center[1] + 1),
            (room.center[0], room.center[1] - 1),
        }
    )

    inner_width = room.x2 - room.x1 - 2
    inner_height = room.y2 - room.y1 - 2
    wall_count = random.randint(min_segments, max_segments)

    for _ in range(wall_count):
        if random.random() < 0.5:
            if inner_width < 3:
                continue

            max_length = max(2, inner_width - 1)
            wall_length = random.randint(2, max_length)
            y = random.randint(room.y1 + 1, room.y2 - 2)
            x_start = random.randint(room.x1 + 1, room.x2 - wall_length - 1)

            for x in range(x_start, x_start + wall_length):
                if (x, y) in protected_tiles:
                    continue
                dungeon.tiles[x, y] = tile_types.wall
        else:
            if inner_height < 3:
                continue

            max_length = max(2, inner_height - 1)
            wall_length = random.randint(2, max_length)
            x = random.randint(room.x1 + 1, room.x2 - 2)
            y_start = random.randint(room.y1 + 1, room.y2 - wall_length - 1)

            for y in range(y_start, y_start + wall_length):
                if (x, y) in protected_tiles:
                    continue
                dungeon.tiles[x, y] = tile_types.wall


def tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int]
) -> Iterator[Tuple[int, int]]:
    """Return an L-shaped tunnel between these two points."""
    x1, y1 = start
    x2, y2 = end

    if random.random() < 0.5:  # 50% chance.
        # Move horizontally, then vertically.
        corner_x, corner_y = x2, y1
    else:
        # Move vertically, then horizontally.
        corner_x, corner_y = x1, y2

    # Generate the coordinates for this tunnel.
    for x, y in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
        yield x, y
    for x, y in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
        yield x, y


def generate_dungeon(max_rooms: int, room_min_size: int, room_max_size: int, map_width: int, map_height: int, max_monsters_per_room: int, engine: Engine) -> GameMap:
    """Generate a new dungeon map."""
    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, entities=[player])

    rooms: List[RectangularRoom] = []

    for r in range(max_rooms):
        room_width = random.randint(room_min_size, room_max_size)
        room_height = random.randint(room_min_size, room_max_size)

        x = random.randint(0, dungeon.width - room_width - 1)
        y = random.randint(0, dungeon.height - room_height - 1)

        new_room = RectangularRoom(x, y, room_width, room_height)

        if any(new_room.intersects(other_room) for other_room in rooms):
            continue  # This room intersects, so skip it.

        # Dig out this room's inner area.
        dungeon.tiles[new_room.inner] = tile_types.floor

        if len(rooms) == 0:
            # This is the first room, where the player starts.
            player.place(*new_room.center, dungeon)
            protected_tiles = set()
        else:
            # Connect this room to the previous room with a tunnel.
            protected_tiles = {
                (x, y)
                for x, y in tunnel_between(rooms[-1].center, new_room.center)
                if new_room.x1 < x < new_room.x2 and new_room.y1 < y < new_room.y2
            }
            for x, y in tunnel_between(rooms[-1].center, new_room.center):
                dungeon.tiles[x, y] = tile_types.floor

        generate_interior_walls(
            new_room,
            dungeon,
            protected_tiles=protected_tiles,
            min_segments=2,
            max_segments=5,
        )

        place_entities(new_room, dungeon, max_monsters_per_room)
        rooms.append(new_room)

    return dungeon