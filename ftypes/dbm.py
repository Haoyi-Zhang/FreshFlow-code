"""Exact bounded integer difference zones and replayable closure evidence."""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from itertools import product
from typing import Iterable, Iterator

INF = 10**60
MAX_VARS = 128
MAX_EDGES = 4096
MAX_ENUM = 2_000_000


class ZoneError(ValueError):
    """Malformed, infeasible, unbounded, or resource-exceeding zone."""


@dataclass(frozen=True)
class Edge:
    u: str
    v: str
    c: int


@dataclass
class Closure:
    variables: tuple[str, ...]
    edges: tuple[Edge, ...]
    dist: list[list[int]]
    paths: list[list[list[int]]]

    @cached_property
    def index(self) -> dict[str, int]:
        return {name: i for i, name in enumerate(self.variables)}

    def bound(self, u: str, v: str) -> int:
        idx = self.index
        return self.dist[idx[u]][idx[v]]

    def potential(self, source: str) -> dict[str, int]:
        idx = self.index
        row = self.dist[idx[source]]
        gauge = row[idx["zero"]]
        if gauge >= INF:
            raise ZoneError("source is disconnected from zero")
        return {v: row[i] - gauge for i, v in enumerate(self.variables)}

    def path_edges(self, u: str, v: str) -> list[int]:
        idx = self.index
        return list(self.paths[idx[u]][idx[v]])


@dataclass(frozen=True)
class Zone:
    variables: tuple[str, ...]
    bounds: dict[str, tuple[int, int]]
    constraints: tuple[Edge, ...]
    name: str = "zone"

    @staticmethod
    def from_spec(
        variables: Iterable[str], spec: dict, *, extra: Iterable[tuple[str, str, int]] = ()
    ) -> "Zone":
        vars_tuple = tuple(variables)
        if not vars_tuple or vars_tuple[0] != "zero" or len(set(vars_tuple)) != len(vars_tuple):
            raise ZoneError("variables must be unique and start with zero")
        if len(vars_tuple) > MAX_VARS:
            raise ZoneError("too many clock variables")
        raw_bounds = spec.get("bounds")
        if not isinstance(raw_bounds, dict):
            raise ZoneError("zone bounds must be an object")
        bounds: dict[str, tuple[int, int]] = {"zero": (0, 0)}
        for var in vars_tuple[1:]:
            pair = raw_bounds.get(var)
            if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int for x in pair):
                raise ZoneError(f"missing or malformed bound for {var}")
            lo, hi = pair
            if lo > hi:
                raise ZoneError(f"empty explicit bound for {var}")
            if max(abs(lo), abs(hi)).bit_length() > 128:
                raise ZoneError("input integer exceeds 128-bit magnitude limit")
            bounds[var] = (lo, hi)
        if set(raw_bounds) - set(vars_tuple[1:]):
            raise ZoneError("zone bounds name an unknown variable")
        edges: list[Edge] = []
        seen_edges: set[Edge] = set()
        raw_constraints = spec.get("constraints", [])
        if not isinstance(raw_constraints, list):
            raise ZoneError("constraints must be a list")
        names = set(vars_tuple)
        for item in [*raw_constraints, *[list(e) for e in extra]]:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise ZoneError("constraint must be [u,v,c]")
            u, v, c = item
            if u not in names or v not in names or type(c) is not int:
                raise ZoneError("constraint names or constant invalid")
            if abs(c).bit_length() > 128:
                raise ZoneError("constraint integer exceeds 128-bit magnitude limit")
            edge = Edge(u, v, c)
            if edge not in seen_edges:
                edges.append(edge)
                seen_edges.add(edge)
        if len(edges) + 2 * len(vars_tuple) > MAX_EDGES:
            raise ZoneError("too many zone constraints")
        zone = Zone(vars_tuple, bounds, tuple(edges), str(spec.get("name", "zone")))
        closure = zone.close()
        if any(closure.dist[i][i] < 0 for i in range(len(vars_tuple))):
            raise ZoneError("listed zone is infeasible")
        return zone

    @property
    def all_edges(self) -> tuple[Edge, ...]:
        edges = list(self.constraints)
        for var in self.variables[1:]:
            lo, hi = self.bounds[var]
            edges.append(Edge("zero", var, hi))
            edges.append(Edge(var, "zero", -lo))
        return tuple(edges)

    def close(self) -> Closure:
        n = len(self.variables)
        idx = {name: i for i, name in enumerate(self.variables)}
        edges = self.all_edges
        dist = [[INF] * n for _ in range(n)]
        paths: list[list[list[int]]] = [[[] for _ in range(n)] for _ in range(n)]
        for i in range(n):
            dist[i][i] = 0
        for edge_index, edge in enumerate(edges):
            u, v = idx[edge.u], idx[edge.v]
            if edge.c < dist[u][v]:
                dist[u][v] = edge.c
                paths[u][v] = [edge_index]
        for k in range(n):
            for i in range(n):
                if dist[i][k] >= INF:
                    continue
                dik = dist[i][k]
                for j in range(n):
                    if dist[k][j] >= INF:
                        continue
                    candidate = dik + dist[k][j]
                    if candidate < dist[i][j]:
                        dist[i][j] = candidate
                        paths[i][j] = paths[i][k] + paths[k][j]
        return Closure(self.variables, edges, dist, paths)

    def enumerate(self, *, cap: int = MAX_ENUM) -> Iterator[dict[str, int]]:
        vars_nonzero = self.variables[1:]
        volume = 1
        for v in vars_nonzero:
            lo, hi = self.bounds[v]
            volume *= hi - lo + 1
            if volume > cap:
                raise ZoneError(f"zone enumeration volume {volume} exceeds cap {cap}")
        ranges = [range(self.bounds[v][0], self.bounds[v][1] + 1) for v in vars_nonzero]
        edges = self.constraints
        emitted = 0
        for values in product(*ranges):
            valuation = {"zero": 0, **dict(zip(vars_nonzero, values))}
            if all(valuation[e.v] - valuation[e.u] <= e.c for e in edges):
                emitted += 1
                if emitted > cap:
                    raise ZoneError("feasible valuation count exceeds cap")
                yield valuation

    def with_constraints(self, additions: Iterable[tuple[str, str, int]], *, name: str | None = None) -> "Zone | None":
        constraints = [*[list((e.u, e.v, e.c)) for e in self.constraints], *[list(x) for x in additions]]
        spec = {
            "name": self.name if name is None else name,
            "bounds": {v: list(self.bounds[v]) for v in self.variables[1:]},
            "constraints": constraints,
        }
        try:
            return Zone.from_spec(self.variables, spec)
        except ZoneError as exc:
            if "infeasible" in str(exc) or "empty explicit bound" in str(exc):
                return None
            raise


def closure_certificate(zone: Zone) -> dict:
    closure = zone.close()
    variables = list(closure.variables)
    potentials = {}
    for u in variables:
        values = closure.potential(u)
        potentials[u] = [values[v] for v in variables]
    return {
        "variables": variables,
        "edges": [[e.u, e.v, e.c] for e in closure.edges],
        "distance": closure.dist,
        "paths": closure.paths,
        "potentials": potentials,
    }


def verify_closure_certificate(zone: Zone, certificate: dict) -> list[list[int]]:
    """Replay all-pairs upper and lower witnesses without running a closure algorithm."""
    variables = list(zone.variables)
    edges = zone.all_edges
    if certificate.get("variables") != variables:
        raise ZoneError("closure variable order mismatch")
    if certificate.get("edges") != [[e.u, e.v, e.c] for e in edges]:
        raise ZoneError("closure edge list mismatch")
    distance = certificate.get("distance")
    paths = certificate.get("paths")
    potentials = certificate.get("potentials")
    n = len(variables)
    if not isinstance(distance, list) or len(distance) != n:
        raise ZoneError("closure distance shape mismatch")
    if not isinstance(paths, list) or len(paths) != n or not isinstance(potentials, dict):
        raise ZoneError("closure evidence shape mismatch")
    index = {v: i for i, v in enumerate(variables)}
    for i, u in enumerate(variables):
        if len(distance[i]) != n or len(paths[i]) != n:
            raise ZoneError("closure row shape mismatch")
        potential = potentials.get(u)
        if not isinstance(potential, list) or len(potential) != n or any(type(x) is not int for x in potential):
            raise ZoneError("missing potential")
        if potential[index["zero"]] != 0:
            raise ZoneError("potential gauge is not zero")
        for edge in edges:
            if potential[index[edge.v]] - potential[index[edge.u]] > edge.c:
                raise ZoneError("potential violates an original edge")
        for j, v in enumerate(variables):
            d = distance[i][j]
            if type(d) is not int or d.bit_length() > 256:
                raise ZoneError("invalid closure distance")
            path = paths[i][j]
            if not isinstance(path, list) or len(path) > n:
                raise ZoneError("invalid closure path")
            at = u
            total = 0
            for edge_index in path:
                if type(edge_index) is not int or not 0 <= edge_index < len(edges):
                    raise ZoneError("closure path edge index invalid")
                edge = edges[edge_index]
                if edge.u != at:
                    raise ZoneError("closure path is disconnected")
                at = edge.v
                total += edge.c
            if at != v or total != d:
                raise ZoneError("closure path does not prove its distance")
            if potential[j] - potential[i] != d:
                raise ZoneError("potential does not attain closure distance")
    return distance


def projected_support(closure: Closure, variables: Iterable[str]) -> dict[tuple[str, str], int]:
    chosen = tuple(variables)
    return {(u, v): closure.bound(u, v) for u in chosen for v in chosen}
