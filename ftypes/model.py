"""Validated syntax for finite stream interfaces, graphs, and output policies."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .dbm import Zone, ZoneError
from .terms import Term, format_term, lineage, parse_term

MAX_ITEMS = 128


class ModelError(ValueError):
    """Malformed finite stream model."""


@dataclass(frozen=True)
class Port:
    name: str
    term: Term


@dataclass(frozen=True)
class Dependency:
    source: str
    role: str
    lower: int
    upper: int
    edge_id: str


@dataclass(frozen=True)
class Node:
    name: str
    op: str
    data: tuple[str, ...]
    gates: tuple[str, ...]
    dependencies: tuple[Dependency, ...]
    location: str
    epoch: int


@dataclass(frozen=True)
class Output:
    key: str
    node: str
    term: Term
    deadline: int


@dataclass
class Case:
    case_id: str
    origins: tuple[str, ...]
    ports: tuple[Port, ...]
    zones: tuple[Zone, ...]
    nodes: tuple[Node, ...]
    outputs: tuple[Output, ...]
    metadata: dict[str, Any]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.ports) + tuple(n.name for n in self.nodes)

    @property
    def port_map(self) -> dict[str, Port]:
        return {p.name: p for p in self.ports}

    @property
    def node_map(self) -> dict[str, Node]:
        return {n.name: n for n in self.nodes}

    @property
    def output_map(self) -> dict[str, Output]:
        return {o.key: o for o in self.outputs}

    @property
    def variables(self) -> tuple[str, ...]:
        return ("zero",) + tuple(f"b_{s}" for s in self.origins) + tuple(f"r_{p.name}" for p in self.ports)

    @property
    def terms(self) -> dict[str, Term]:
        out = {p.name: p.term for p in self.ports}
        for node in self.nodes:
            if node.op == "copy":
                out[node.name] = out[node.data[0]]
            elif node.op == "pair":
                out[node.name] = ("pair", out[node.data[0]], out[node.data[1]])
            elif node.op == "barrier":
                out[node.name] = ("unit",)
            else:  # validated earlier
                raise ModelError("unknown operation")
        return out

    def to_spec(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "origins": list(self.origins),
            "ports": [{"name": p.name, "term": format_term(p.term)} for p in self.ports],
            "zones": [
                {
                    "name": z.name,
                    "bounds": {v: list(z.bounds[v]) for v in z.variables[1:]},
                    "constraints": [[e.u, e.v, e.c] for e in z.constraints],
                }
                for z in self.zones
            ],
            "nodes": [
                {
                    "name": n.name,
                    "op": n.op,
                    "data": list(n.data),
                    "gates": list(n.gates),
                    "delays": {d.source: [d.lower, d.upper] for d in n.dependencies},
                    "location": n.location,
                    "epoch": n.epoch,
                }
                for n in self.nodes
            ],
            "outputs": [
                {"key": o.key, "node": o.node, "term": format_term(o.term), "deadline": o.deadline}
                for o in self.outputs
            ],
            "metadata": self.metadata,
        }


def _name(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ModelError(f"{what} must be a nonempty short string")
    if not value[0].isalpha() or any(not (c.isalnum() or c == "-") for c in value):
        raise ModelError(f"{what} has invalid characters")
    return value


def case_from_spec(spec: dict[str, Any]) -> Case:
    if not isinstance(spec, dict):
        raise ModelError("case must be a JSON object")
    allowed = {"id", "origins", "ports", "zones", "nodes", "outputs", "metadata"}
    extra_keys = set(spec) - allowed
    if extra_keys:
        raise ModelError(f"unknown top-level fields: {sorted(extra_keys)}")
    case_id = _name(spec.get("id", "case"), "case id")
    origins_raw = spec.get("origins")
    if not isinstance(origins_raw, list) or not origins_raw or len(origins_raw) > MAX_ITEMS:
        raise ModelError("origins must be a nonempty bounded list")
    origins = tuple(_name(x, "origin") for x in origins_raw)
    if len(set(origins)) != len(origins):
        raise ModelError("duplicate origin")

    ports_raw = spec.get("ports")
    if not isinstance(ports_raw, list) or not ports_raw or len(ports_raw) > MAX_ITEMS:
        raise ModelError("ports must be a nonempty bounded list")
    ports: list[Port] = []
    for item in ports_raw:
        if not isinstance(item, dict) or set(item) != {"name", "term"}:
            raise ModelError("port must contain exactly name and term")
        port = Port(_name(item["name"], "port"), parse_term(item["term"]))
        if not lineage(port.term) <= set(origins):
            raise ModelError("port term names an unknown origin")
        ports.append(port)
    if len({p.name for p in ports}) != len(ports):
        raise ModelError("duplicate port")

    variables = ("zero",) + tuple(f"b_{s}" for s in origins) + tuple(f"r_{p.name}" for p in ports)
    causality: list[tuple[str, str, int]] = []
    for p in ports:
        # Readiness is relative to the current boundary, not a birth clock.
        causality.append((f"r_{p.name}", "zero", 0))
        for s in sorted(lineage(p.term)):
            # b_s <= r_p  is b_s-r_p <= 0.
            causality.append((f"r_{p.name}", f"b_{s}", 0))
    zones_raw = spec.get("zones")
    if not isinstance(zones_raw, list) or not zones_raw or len(zones_raw) > MAX_ITEMS:
        raise ModelError("zones must be a nonempty bounded list")
    zones: list[Zone] = []
    try:
        for item in zones_raw:
            zones.append(Zone.from_spec(variables, item, extra=causality))
    except ZoneError as exc:
        raise ModelError(str(exc)) from exc

    nodes_raw = spec.get("nodes", [])
    if not isinstance(nodes_raw, list) or len(nodes_raw) > MAX_ITEMS:
        raise ModelError("nodes must be a bounded list")
    known = {p.name for p in ports}
    nodes: list[Node] = []
    for item in nodes_raw:
        if not isinstance(item, dict):
            raise ModelError("node must be an object")
        required = {"name", "op", "data", "gates", "delays"}
        if not required <= set(item) or set(item) - (required | {"location", "epoch"}):
            raise ModelError("node fields are incomplete or unknown")
        name = _name(item["name"], "node")
        if name in known:
            raise ModelError("duplicate graph name")
        op = item["op"]
        if op not in {"copy", "pair", "barrier"}:
            raise ModelError("unknown operation")
        data = item["data"]
        gates = item["gates"]
        if not isinstance(data, list) or not isinstance(gates, list):
            raise ModelError("data and gates must be lists")
        data_names = tuple(_name(x, "dependency") for x in data)
        gate_names = tuple(_name(x, "dependency") for x in gates)
        if len(set(data_names + gate_names)) != len(data_names) + len(gate_names):
            raise ModelError("duplicate or dual-role dependency")
        if any(x not in known for x in data_names + gate_names):
            raise ModelError("dependency is missing or cyclic")
        if (op == "copy" and len(data_names) != 1) or (op == "pair" and len(data_names) != 2) or (op == "barrier" and data_names):
            raise ModelError("operation has wrong data arity")
        if not data_names and not gate_names:
            raise ModelError("non-port needs at least one dependency")
        delays = item["delays"]
        if not isinstance(delays, dict) or set(delays) != set(data_names + gate_names):
            raise ModelError("delays must cover each dependency exactly")
        dependencies: list[Dependency] = []
        for source in data_names + gate_names:
            pair = delays[source]
            if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int for x in pair):
                raise ModelError("delay interval malformed")
            lo, hi = pair
            if not 0 <= lo <= hi or max(lo, hi).bit_length() > 128:
                raise ModelError("delay interval must be finite and nonnegative")
            role = "data" if source in data_names else "gate"
            dependencies.append(Dependency(source, role, lo, hi, f"{source}->{name}"))
        location = _name(item.get("location", "logical"), "location")
        epoch = item.get("epoch", 0)
        if type(epoch) is not int or epoch < 0:
            raise ModelError("epoch must be a nonnegative integer")
        nodes.append(Node(name, op, data_names, gate_names, tuple(dependencies), location, epoch))
        known.add(name)

    terms: dict[str, Term] = {p.name: p.term for p in ports}
    for node in nodes:
        if node.op == "copy":
            terms[node.name] = terms[node.data[0]]
        elif node.op == "pair":
            terms[node.name] = ("pair", terms[node.data[0]], terms[node.data[1]])
        else:
            terms[node.name] = ("unit",)

    outputs_raw = spec.get("outputs")
    if not isinstance(outputs_raw, list) or len(outputs_raw) > MAX_ITEMS:
        raise ModelError("outputs must be a bounded list (possibly empty)")
    outputs: list[Output] = []
    for item in outputs_raw:
        if not isinstance(item, dict) or set(item) != {"key", "node", "term", "deadline"}:
            raise ModelError("output fields malformed")
        key = _name(item["key"], "output key")
        node_name = _name(item["node"], "output node")
        if node_name not in known:
            raise ModelError("output names an unknown graph vertex")
        term = parse_term(item["term"])
        deadline = item["deadline"]
        if type(deadline) is not int or deadline < 0:
            raise ModelError("deadline must be a nonnegative integer")
        if not lineage(terms[node_name]):
            raise ModelError("output must have nonempty data lineage")
        outputs.append(Output(key, node_name, term, deadline))
    if len({o.key for o in outputs}) != len(outputs):
        raise ModelError("duplicate output key")
    metadata = spec.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ModelError("metadata must be an object")
    return Case(case_id, origins, tuple(ports), tuple(zones), tuple(nodes), tuple(outputs), metadata)


def load_case(path: str | Path) -> Case:
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelError(f"cannot load case: {exc}") from exc
    return case_from_spec(spec)
