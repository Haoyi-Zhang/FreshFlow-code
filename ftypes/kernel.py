"""Static certificate replay; deliberately does not import the producer or oracle."""
from __future__ import annotations

from .dbm import ZoneError, verify_closure_certificate
from .model import Case
from .terms import format_term, lineage


class CertificateError(ValueError):
    """A certificate is malformed or does not prove its claim."""


def replay_static(case: Case, certificate: dict) -> dict:
    try:
        if certificate.get("schema") != "freshness-static-certificate-1":
            raise CertificateError("unsupported static certificate schema")
        if certificate.get("case") != case.case_id:
            raise CertificateError("certificate names a different case")
        zone_certs = certificate.get("zones")
        if not isinstance(zone_certs, list) or len(zone_certs) != len(case.zones):
            raise CertificateError("zone certificate count mismatch")
        profile: dict[tuple[str, str], int] = {}
        for index, (zone, zone_cert) in enumerate(zip(case.zones, zone_certs)):
            if zone_cert.get("index") != index or zone_cert.get("name") != zone.name:
                raise CertificateError("zone identity mismatch")
            distance = verify_closure_certificate(zone, zone_cert.get("closure", {}))
            variable_index = {v: i for i, v in enumerate(zone.variables)}
            expected_zone_profile = {}
            for port in case.ports:
                for source in case.origins:
                    value = distance[variable_index[f"b_{source}"]][variable_index[f"r_{port.name}"]]
                    expected_zone_profile[f"{port.name}:{source}"] = value
                    key = (port.name, source)
                    profile[key] = max(profile.get(key, -10**60), value)
            if zone_cert.get("profile") != expected_zone_profile:
                raise CertificateError("zone profile mismatch")
        expected_profile = {
            f"{p.name}:{s}": profile[(p.name, s)] for p in case.ports for s in case.origins
        }
        if certificate.get("profile") != expected_profile:
            raise CertificateError("union profile mismatch")
        rows = certificate.get("rows")
        terms = certificate.get("terms")
        if not isinstance(rows, dict) or not isinstance(terms, dict):
            raise CertificateError("missing rows or terms")
        derived_terms = case.terms
        derived_rows: dict[str, dict[str, int]] = {}
        for port in case.ports:
            derived_rows[port.name] = {s: profile[(port.name, s)] for s in case.origins}
        for node in case.nodes:
            derived_rows[node.name] = {
                s: max(derived_rows[d.source][s] + d.upper for d in node.dependencies)
                for s in case.origins
            }
        if rows != derived_rows:
            raise CertificateError("propagated row mismatch")
        expected_terms = {name: format_term(term) for name, term in derived_terms.items()}
        if terms != expected_terms:
            raise CertificateError("constructor term mismatch")
        expected_outputs = []
        admitted = True
        for output in case.outputs:
            actual = derived_terms[output.node]
            age = max(derived_rows[output.node][s] for s in lineage(actual))
            term_ok = actual == output.term
            age_ok = age <= output.deadline
            admitted = admitted and term_ok and age_ok
            expected_outputs.append({
                "key": output.key,
                "node": output.node,
                "actual_term": format_term(actual),
                "expected_term": format_term(output.term),
                "term_ok": term_ok,
                "exact_worst_age": age,
                "deadline": output.deadline,
                "age_ok": age_ok,
            })
        if certificate.get("outputs") != expected_outputs or certificate.get("admitted") is not admitted:
            raise CertificateError("output obligation mismatch")
        return {"case": case.case_id, "admitted": admitted, "outputs": expected_outputs}
    except (KeyError, TypeError, ZoneError) as exc:
        if isinstance(exc, CertificateError):
            raise
        raise CertificateError(str(exc)) from exc
