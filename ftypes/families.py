"""Deterministic finite case families used by the validation campaigns."""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from .model import Case, case_from_spec


def _zone(name: str, constraints: list[list] | None = None, *, birth_lo: int = -2, ready_hi: int = 2,
          overrides: dict[str, list[int]] | None = None) -> dict:
    bounds = {
        "b_a": [birth_lo, 0],
        "b_b": [birth_lo, 0],
        "r_p": [0, ready_hi],
        "r_q": [0, ready_hi],
    }
    if overrides:
        bounds.update(overrides)
    return {"name": name, "bounds": bounds, "constraints": constraints or []}


def interface_zones(index: int, *, small: bool = False) -> list[dict]:
    lo = -1 if small else -2
    hi = 1 if small else 2
    if index == 0:
        return [_zone("independent", birth_lo=lo, ready_hi=hi)]
    if index == 1:
        return [_zone("birth-near", [["b_a", "b_b", 1], ["b_b", "b_a", 1]], birth_lo=lo, ready_hi=hi)]
    if index == 2:
        return [_zone("p-before-q", [["r_q", "r_p", 0]], birth_lo=lo, ready_hi=hi)]
    if index == 3:
        return [_zone("q-before-p", [["r_p", "r_q", 0]], birth_lo=lo, ready_hi=hi)]
    if index == 4:
        return [_zone("cross-a-q", [["b_a", "r_q", 2 if not small else 1]], birth_lo=lo, ready_hi=hi)]
    if index == 5:
        return [_zone("cross-b-p", [["b_b", "r_p", 2 if not small else 1]], birth_lo=lo, ready_hi=hi)]
    if index == 6:
        return [
            _zone("union-p-zero", birth_lo=lo, ready_hi=hi, overrides={"r_p": [0, 0]}),
            _zone("union-q-high", birth_lo=lo, ready_hi=hi, overrides={"r_q": [hi, hi]}),
        ]
    if index == 7:
        return [_zone("locked-readiness", [["r_p", "r_q", 0], ["r_q", "r_p", 0],
                                            ["b_a", "b_b", 1], ["b_b", "b_a", 1]],
                      birth_lo=lo, ready_hi=hi)]
    raise ValueError("interface family index must be 0..7")


def _d(lo: int, hi: int) -> list[int]:
    return [lo, hi]


def graph_shape(index: int, width: int) -> tuple[list[dict], str, str]:
    d = _d(0, width)
    if index == 0:
        nodes = [{"name": "x", "op": "copy", "data": ["p"], "gates": [], "delays": {"p": d}}]
        return nodes, "x", "src(a)"
    if index == 1:
        nodes = [{"name": "x", "op": "copy", "data": ["p"], "gates": ["q"], "delays": {"p": d, "q": d}}]
        return nodes, "x", "src(a)"
    if index == 2:
        nodes = [{"name": "x", "op": "pair", "data": ["p", "q"], "gates": [], "delays": {"p": d, "q": d}}]
        return nodes, "x", "pair(src(a),src(b))"
    if index == 3:
        nodes = [
            {"name": "bar", "op": "barrier", "data": [], "gates": ["p", "q"], "delays": {"p": d, "q": d}},
            {"name": "x", "op": "copy", "data": ["p"], "gates": ["bar"], "delays": {"p": d, "bar": d}},
        ]
        return nodes, "x", "src(a)"
    if index == 4:
        nodes = [
            {"name": "u", "op": "copy", "data": ["p"], "gates": [], "delays": {"p": d}},
            {"name": "x", "op": "copy", "data": ["u"], "gates": ["q"], "delays": {"u": d, "q": d}},
        ]
        return nodes, "x", "src(a)"
    if index == 5:
        nodes = [
            {"name": "u", "op": "copy", "data": ["p"], "gates": [], "delays": {"p": d}},
            {"name": "v", "op": "copy", "data": ["q"], "gates": [], "delays": {"q": d}},
            {"name": "x", "op": "pair", "data": ["u", "v"], "gates": [], "delays": {"u": d, "v": d}},
        ]
        return nodes, "x", "pair(src(a),src(b))"
    if index == 6:
        nodes = [
            {"name": "bar", "op": "barrier", "data": [], "gates": ["p", "q"], "delays": {"p": d, "q": d}},
            {"name": "x", "op": "pair", "data": ["p", "q"], "gates": ["bar"], "delays": {"p": d, "q": d, "bar": d}},
        ]
        return nodes, "x", "pair(src(a),src(b))"
    if index == 7:
        nodes = [
            {"name": "u", "op": "copy", "data": ["q"], "gates": ["p"], "delays": {"q": d, "p": d}},
            {"name": "x", "op": "copy", "data": ["u"], "gates": [], "delays": {"u": d}},
        ]
        return nodes, "x", "src(b)"
    raise ValueError("graph shape index must be 0..7")


def make_case(interface: int, shape: int, width: int, *, small: bool = False, case_id: str | None = None) -> Case:
    nodes, output_node, term = graph_shape(shape, width)
    spec = {
        "id": case_id or f"static-i{interface}-g{shape}-w{width}",
        "origins": ["a", "b"],
        "ports": [{"name": "p", "term": "src(a)"}, {"name": "q", "term": "src(b)"}],
        "zones": interface_zones(interface, small=small),
        "nodes": nodes,
        "outputs": [{"key": "result", "node": output_node, "term": term, "deadline": 128}],
        "metadata": {"interface": interface, "shape": shape, "width": width, "small": small},
    }
    return case_from_spec(spec)


def static_cases() -> Iterable[Case]:
    for interface in range(8):
        for shape in range(8):
            for width in range(2):
                yield make_case(interface, shape, width)


def cut_cases() -> Iterable[Case]:
    number = 0
    for interface in range(4):
        for shape in range(8):
            number += 1
            yield make_case(interface, shape, 1, small=True, case_id=f"cut-{number:02d}-i{interface}-g{shape}")


def adaptive_interface(group: int, index: int) -> Case:
    if not 0 <= group < 3 or not 0 <= index < 16:
        raise ValueError("adaptive family coordinates out of range")
    bits = [(index >> k) & 1 for k in range(4)]
    constraints: list[list] = []
    if bits[0]:
        constraints.append(["zero", "r_p", 1])
    if bits[1]:
        constraints.append(["zero", "r_q", 1])
    if bits[2]:
        constraints.append(["r_p", "r_q", 0])  # r_q <= r_p
    if bits[3]:
        constraints.append(["b_a", "b_b", 0])  # b_b <= b_a
    # Numeric perturbations distinguish rows even when support happens to match.
    constraints.append(["b_a", "r_p", 2 - bits[1]])
    constraints.append(["b_b", "r_q", 2 - bits[0]])
    if group == 0:
        ports = [{"name": "p", "term": "src(a)"}, {"name": "q", "term": "src(b)"}]
        output_term = "src(a)"
    elif group == 1:
        ports = [{"name": "p", "term": "pair(src(a),src(b))"}, {"name": "q", "term": "unit"}]
        output_term = "pair(src(a),src(b))"
    else:
        ports = [{"name": "p", "term": "pair(src(a),src(b))"}, {"name": "q", "term": "src(a)"}]
        output_term = "pair(src(a),src(b))"
    zone = _zone(f"adaptive-{group}-{index}", constraints)
    spec = {
        "id": f"adaptive-g{group}-n{index:02d}",
        "origins": ["a", "b"],
        "ports": ports,
        "zones": [zone],
        "nodes": [],
        "outputs": [{"key": "payload", "node": "p", "term": output_term, "deadline": 128}],
        "metadata": {"group": group, "index": index, "bits": bits},
    }
    return case_from_spec(spec)


def adaptive_interfaces() -> list[Case]:
    return [adaptive_interface(group, index) for group in range(3) for index in range(16)]


def matrix_interface(matrix: tuple[tuple[int, int], tuple[int, int]], name: str) -> Case:
    constraints = [
        ["b_a", "r_p", matrix[0][0]],
        ["b_b", "r_p", matrix[0][1]],
        ["b_a", "r_q", matrix[1][0]],
        ["b_b", "r_q", matrix[1][1]],
    ]
    spec = {
        "id": name,
        "origins": ["a", "b"],
        "ports": [{"name": "p", "term": "src(a)"}, {"name": "q", "term": "src(b)"}],
        "zones": [_zone(name, constraints, birth_lo=-2, ready_hi=2)],
        "nodes": [],
        "outputs": [{"key": "out", "node": "p", "term": "src(a)", "deadline": 128}],
        "metadata": {"matrix": matrix},
    }
    return case_from_spec(spec)
