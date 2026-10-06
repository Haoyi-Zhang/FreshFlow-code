"""Replay adaptive closure and row-cover evidence without inference algorithms."""
from __future__ import annotations

from .dbm import ZoneError, verify_closure_certificate
from .model import Case
from .terms import format_term, lineage


class AdaptiveCertificateError(ValueError):
    """Malformed or invalid adaptive certificate."""


def _metadata(left: Case, right: Case) -> None:
    if len(left.zones) != 1 or len(right.zones) != 1:
        raise AdaptiveCertificateError("one zone required")
    if left.origins != right.origins:
        raise AdaptiveCertificateError("origin mismatch")
    if [(p.name, format_term(p.term)) for p in left.ports] != [(p.name, format_term(p.term)) for p in right.ports]:
        raise AdaptiveCertificateError("port metadata mismatch")
    if not any(lineage(p.term) for p in left.ports):
        raise AdaptiveCertificateError("at least one data-bearing port is required")


def replay_refinement(left: Case, right: Case, certificate: dict) -> dict:
    try:
        _metadata(left, right)
        if certificate.get("schema") != "freshness-adaptive-certificate-1":
            raise AdaptiveCertificateError("unsupported schema")
        if certificate.get("left") != left.case_id or certificate.get("right") != right.case_id:
            raise AdaptiveCertificateError("query identity mismatch")
        dl = verify_closure_certificate(left.zones[0], certificate.get("left_closure", {}))
        dr = verify_closure_certificate(right.zones[0], certificate.get("right_closure", {}))
        il = {v: i for i, v in enumerate(left.zones[0].variables)}
        ir = {v: i for i, v in enumerate(right.zones[0].variables)}
        ready = ("zero",) + tuple(f"r_{p.name}" for p in left.ports)

        support_ok = all(dl[il[i]][il[j]] <= dr[ir[i]][ir[j]] for i in ready for j in ready)
        covers: dict[str, dict[str, str]] = {}
        row_ok = True
        for port in left.ports:
            sources = sorted(lineage(port.term))
            if not sources:
                continue
            covers[port.name] = {}
            for source in sources:
                chosen = None
                for target in sources:
                    if all(dl[il[f"b_{source}"]][il[i]] <= dr[ir[f"b_{target}"]][ir[i]] for i in ready):
                        chosen = target
                        break
                if chosen is None:
                    row_ok = False
                else:
                    covers[port.name][source] = chosen
        truth = support_ok and row_ok
        if certificate.get("accepted") is not truth:
            raise AdaptiveCertificateError("accepted flag disagrees with replay")
        if truth:
            supplied = certificate.get("covers")
            if not isinstance(supplied, dict) or set(supplied) != set(covers):
                raise AdaptiveCertificateError("row-cover map mismatch")
            for port_name, source_map in supplied.items():
                sources = lineage(left.port_map[port_name].term)
                if not isinstance(source_map, dict) or set(source_map) != set(sources):
                    raise AdaptiveCertificateError("row-cover source map mismatch")
                for source, target in source_map.items():
                    if not isinstance(target, str) or target not in sources:
                        raise AdaptiveCertificateError("cover target is outside the payload")
                    if any(dl[il[f"b_{source}"]][il[i]] > dr[ir[f"b_{target}"]][ir[i]] for i in ready):
                        raise AdaptiveCertificateError("supplied row does not cover the source")
            pairs = [[i, j, dl[il[i]][il[j]], dr[ir[i]][ir[j]]] for i in ready for j in ready]
            if certificate.get("readiness_pairs") != pairs:
                raise AdaptiveCertificateError("readiness comparison mismatch")
            return {"accepted": True, "covers": supplied}

        reason = certificate.get("reason")
        witness = certificate.get("witness")
        if not isinstance(witness, dict):
            raise AdaptiveCertificateError("missing rejection witness")
        observed = witness.get("readiness")
        if not isinstance(observed, dict) or set(observed) != set(ready) or any(type(v) is not int for v in observed.values()):
            raise AdaptiveCertificateError("witness readiness must be a complete integer vector")
        if reason == "support":
            i, j = witness.get("i"), witness.get("j")
            if i not in ready or j not in ready:
                raise AdaptiveCertificateError("bad support witness variables")
            if not dl[il[i]][il[j]] > dr[ir[i]][ir[j]]:
                raise AdaptiveCertificateError("support witness is not separating")
            if any(type(witness.get(field)) is not int for field in ("left_bound", "right_bound")) or witness.get("left_bound") != dl[il[i]][il[j]] or witness.get("right_bound") != dr[ir[i]][ir[j]]:
                raise AdaptiveCertificateError("reported support bounds mismatch")
            potential = certificate["left_closure"]["potentials"][i]
            readiness = {v: potential[il[v]] for v in ready}
            if witness.get("readiness") != readiness:
                raise AdaptiveCertificateError("support witness potential mismatch")
            if readiness[j] - readiness[i] <= dr[ir[i]][ir[j]]:
                raise AdaptiveCertificateError("support witness does not violate right support")
        elif reason == "row-cover":
            if not support_ok:
                raise AdaptiveCertificateError("row rejection requires support inclusion")
            port_name = witness.get("port")
            source = witness.get("left_origin")
            if port_name not in left.port_map or source not in lineage(left.port_map[port_name].term):
                raise AdaptiveCertificateError("bad row-cover witness metadata")
            columns = witness.get("separating_columns")
            if not isinstance(columns, dict) or set(columns) != set(lineage(left.port_map[port_name].term)):
                raise AdaptiveCertificateError("missing separating columns")
            for target in sorted(lineage(left.port_map[port_name].term)):
                column = columns.get(target)
                if column not in ready:
                    raise AdaptiveCertificateError("bad separating column")
                if not dl[il[f"b_{source}"]][il[column]] > dr[ir[f"b_{target}"]][ir[column]]:
                    raise AdaptiveCertificateError("column does not separate rows")
            potential = certificate["left_closure"]["potentials"][f"b_{source}"]
            readiness = {v: potential[il[v]] for v in ready}
            if witness.get("readiness") != readiness:
                raise AdaptiveCertificateError("row witness potential mismatch")
            def k(case: Case, matrix, index, port: str) -> int:
                return max(min(matrix[index[f"b_{s}"]][index[i]] - readiness[i] for i in ready)
                           for s in sorted(lineage(case.port_map[port].term)))
            left_k = k(left, dl, il, port_name)
            right_k = k(right, dr, ir, port_name)
            if witness.get("left_k") != left_k or witness.get("right_k") != right_k or not left_k > right_k:
                raise AdaptiveCertificateError("row witness does not separate envelopes")
        else:
            raise AdaptiveCertificateError("unknown rejection reason")
        separator = certificate.get("separator")
        fields = {"port", "readiness", "deadline", "special_wait", "left_special_age", "right_special_age",
                  "branch_observable", "special_reachable_right", "left_valuation", "payload_term", "emission_time"}
        if not isinstance(separator, dict) or set(separator) != fields:
            raise AdaptiveCertificateError("separator fields incomplete or unknown")
        port_name = separator["port"]
        if port_name not in left.port_map or not lineage(left.port_map[port_name].term):
            raise AdaptiveCertificateError("separator payload is not data-bearing")
        if reason == "row-cover" and port_name != witness["port"]:
            raise AdaptiveCertificateError("separator selects the wrong witnessed payload")
        if not isinstance(separator["readiness"], dict) or any(type(v) is not int for v in separator["readiness"].values()) or separator["readiness"] != readiness:
            raise AdaptiveCertificateError("separator readiness differs from witness")
        if separator["branch_observable"] is not True or separator["special_reachable_right"] is not (reason == "row-cover"):
            raise AdaptiveCertificateError("separator branch metadata mismatch")
        sources = lineage(left.port_map[port_name].term)
        def payload_k(matrix, index):
            return max(min(matrix[index[f"b_{s}"]][index[v]] - readiness[v] for v in ready) for s in sources)
        left_k = payload_k(dl, il)
        right_k = payload_k(dr, ir) if reason == "row-cover" else None
        baseline = 1 + max(dr[ir[f"b_{s}"]][ir[f"r_{q.name}"]] for q in right.ports for s in sources)
        time = max(readiness[f"r_{p.name}"] for p in left.ports)
        wait = max(0, baseline - time - left_k + 1) if reason == "support" else baseline - time - right_k
        expected = {"deadline": baseline, "special_wait": wait, "left_special_age": time + wait + left_k,
                    "emission_time": time + wait, "payload_term": format_term(left.port_map[port_name].term),
                    "right_special_age": None if right_k is None else time + wait + right_k}
        for field, value in expected.items():
            if separator[field] != value or (type(value) is int and type(separator[field]) is not int):
                raise AdaptiveCertificateError(f"separator {field} does not follow from input clocks")
        if wait < 0 or expected["left_special_age"] <= baseline:
            raise AdaptiveCertificateError("separator not a stale nonnegative-wait left execution")
        valuation = separator["left_valuation"]
        if not isinstance(valuation, dict) or set(valuation) != set(left.variables) or any(type(x) is not int for x in valuation.values()):
            raise AdaptiveCertificateError("separator needs complete integer birth/readiness valuation")
        if valuation["zero"] != 0 or any(valuation[v] != readiness[v] for v in ready):
            raise AdaptiveCertificateError("separator valuation readiness/gauge mismatch")
        if any(valuation[e.v] - valuation[e.u] > e.c for e in left.zones[0].all_edges):
            raise AdaptiveCertificateError("separator valuation violates original left zone")
        age = time + wait - min(valuation[f"b_{s}"] for s in sources)
        if age != expected["left_special_age"]:
            raise AdaptiveCertificateError("separator full witness does not attain the reported age")
        # Ordinary right branches have age <= B-1 by the exact closed-cell
        # maximum; exceptional right branches have age <= T+D+K == B.
        if right_k is not None and expected["right_special_age"] > baseline:
            raise AdaptiveCertificateError("separator exceptional right branch is stale")
        return {"accepted": False, "reason": reason, "witness": witness,
                "separator_checked": True, "right_ordinary_age_bound": baseline - 1}
    except (KeyError, TypeError, ZoneError) as exc:
        if isinstance(exc, AdaptiveCertificateError):
            raise
        raise AdaptiveCertificateError(str(exc)) from exc
