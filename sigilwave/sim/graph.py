"""SigilGraph: the parser's output, the compiler's input (design doc §4.1,
§4.2). Pure data — positions and topology, no sim state."""

from dataclasses import dataclass, field

import pygame


@dataclass
class GraphNode:
    node_id: int
    pos: pygame.Vector2
    degree: int = 0

    @property
    def is_terminal(self) -> bool:
        return self.degree == 1


@dataclass
class GraphEdge:
    node_a: int
    node_b: int
    polyline: list  # list[pygame.Vector2], world space, includes both ends
    ink_type: object

    @property
    def length(self) -> float:
        return sum((self.polyline[i + 1] - self.polyline[i]).length() for i in range(len(self.polyline) - 1))


@dataclass
class SigilGraph:
    nodes: dict = field(default_factory=dict)  # dict[int, GraphNode]
    edges: list = field(default_factory=list)  # list[GraphEdge]
