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
            if certificate.get("covers") != covers:
                raise AdaptiveCertificateError("row-cover map mismatch")
            pairs = [[i, j, dl[il[i]][il[j]], dr[ir[i]][ir[j]]] for i in ready for j in ready]
            if certificate.get("readiness_pairs") != pairs:
                raise AdaptiveCertificateError("readiness comparison mismatch")
            return {"accepted": True, "covers": covers}

        reason = certificate.get("reason")
        witness = certificate.get("witness")
        if reason == "support":
            i, j = witness.get("i"), witness.get("j")
            if i not in ready or j not in ready:
                raise AdaptiveCertificateError("bad support witness variables")
            if not dl[il[i]][il[j]] > dr[ir[i]][ir[j]]:
                raise AdaptiveCertificateError("support witness is not separating")
            potential = certificate["left_closure"]["potentials"][i]
            readiness = {v: potential[il[v]] for v in ready}
            if witness.get("readiness") != readiness:
                raise AdaptiveCertificateError("support witness potential mismatch")
            if readiness[j] - readiness[i] <= dr[ir[i]][ir[j]]:
                raise AdaptiveCertificateError("support witness does not violate right support")
        elif reason == "row-cover":
            port_name = witness.get("port")
            source = witness.get("left_origin")
            if port_name not in left.port_map or source not in lineage(left.port_map[port_name].term):
                raise AdaptiveCertificateError("bad row-cover witness metadata")
            columns = witness.get("separating_columns")
            if not isinstance(columns, dict):
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
        if not isinstance(separator, dict) or separator.get("left_special_age", 0) <= separator.get("deadline", 0):
            raise AdaptiveCertificateError("separator does not make the left side stale")
        if reason == "row-cover" and separator.get("right_special_age", 10**30) > separator.get("deadline"):
            raise AdaptiveCertificateError("separator is stale on the right")
        return {"accepted": False, "reason": reason, "witness": witness}
    except (KeyError, TypeError, ZoneError) as exc:
        if isinstance(exc, AdaptiveCertificateError):
            raise
        raise AdaptiveCertificateError(str(exc)) from exc
