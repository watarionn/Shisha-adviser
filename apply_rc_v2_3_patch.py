from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
BASE=Path("/app")
EXPECTED_SCORES_SHA="c9436ef06490cab6114d45abc1357758e9165041b60eb2f01c6c5025f4284795"
EXPECTED_DATASET_FP="c2dd0663fd2b9aa0aa85ac71b1e9f08036a9b6a5438f1a266c0e26d9e9dc9fea"
SCORE_UPDATES={'RCV-SCR-000029': {'score_id': 'RCV-SCR-000029', 'variant_id': 'RCV-VAR-0005', 'flavor_id': 'RCV-FLV-0005', 'feature_code': 'sweetness', 'score_0_100': '68', 'confidence': '0.55', 'evidence_mode': 'COMPONENT_OR_DESCRIPTOR', 'evidence_id': 'RCV-AUD-EVD-0001', 'source_id': 'RCV-AUD-SRC-0001', 'provenance_batch': 'STRICT_PROVENANCE_AUDIT_V2_2', 'canonical_generation': 'RECOVERY_20260910', 'model_eligibility': 'ELIGIBLE_FLAVOR_LEVEL'}, 'RCV-SCR-000180': {'score_id': 'RCV-SCR-000180', 'variant_id': 'RCV-VAR-0026', 'flavor_id': 'RCV-FLV-0026', 'feature_code': 'creaminess', 'score_0_100': '12', 'confidence': '0.30', 'evidence_mode': 'LOW_CONFIDENCE_PRIOR', 'evidence_id': 'RCV-EVD-0026', 'source_id': 'RCV-SRC-0001', 'provenance_batch': 'STRICT_PROVENANCE_AUDIT_V2_2', 'canonical_generation': 'RECOVERY_20260910', 'model_eligibility': 'PRIOR_ONLY'}, 'RCV-SCR-000507': {'score_id': 'RCV-SCR-000507', 'variant_id': 'RCV-VAR-0073', 'flavor_id': 'RCV-FLV-0073', 'feature_code': 'body', 'score_0_100': '50', 'confidence': '0.22', 'evidence_mode': 'LOW_CONFIDENCE_PRIOR', 'evidence_id': 'RCV-EVD-0073', 'source_id': 'RCV-SRC-0002', 'provenance_batch': 'STRICT_PROVENANCE_AUDIT_V2_2', 'canonical_generation': 'RECOVERY_20260910', 'model_eligibility': 'PRIOR_ONLY'}, 'RCV-SCR-000962': {'score_id': 'RCV-SCR-000962', 'variant_id': 'RCV-VAR-0138', 'flavor_id': 'RCV-FLV-0138', 'feature_code': 'body', 'score_0_100': '50', 'confidence': '0.22', 'evidence_mode': 'LOW_CONFIDENCE_PRIOR', 'evidence_id': 'RCV-EVD-0138', 'source_id': 'RCV-SRC-0003', 'provenance_batch': 'STRICT_PROVENANCE_AUDIT_V2_2', 'canonical_generation': 'RECOVERY_20260910', 'model_eligibility': 'PRIOR_ONLY'}, 'RCV-SCR-000997': {'score_id': 'RCV-SCR-000997', 'variant_id': 'RCV-VAR-0143', 'flavor_id': 'RCV-FLV-0143', 'feature_code': 'body', 'score_0_100': '50', 'confidence': '0.22', 'evidence_mode': 'LOW_CONFIDENCE_PRIOR', 'evidence_id': 'RCV-EVD-0143', 'source_id': 'RCV-SRC-0003', 'provenance_batch': 'STRICT_PROVENANCE_AUDIT_V2_2', 'canonical_generation': 'RECOVERY_20260910', 'model_eligibility': 'PRIOR_ONLY'}, 'RCV-SCR-001158': {'score_id': 'RCV-SCR-001158', 'variant_id': 'RCV-VAR-0166', 'flavor_id': 'RCV-FLV-0166', 'feature_code': 'body', 'score_0_100': '50', 'confidence': '0.22', 'evidence_mode': 'LOW_CONFIDENCE_PRIOR', 'evidence_id': 'RCV-EVD-0166', 'source_id': 'RCV-SRC-0003', 'provenance_batch': 'STRICT_PROVENANCE_AUDIT_V2_2', 'canonical_generation': 'RECOVERY_20260910', 'model_eligibility': 'PRIOR_ONLY'}, 'RCV-SCR-001214': {'score_id': 'RCV-SCR-001214', 'variant_id': 'RCV-VAR-0174', 'flavor_id': 'RCV-FLV-0174', 'feature_code': 'body', 'score_0_100': '50', 'confidence': '0.22', 'evidence_mode': 'LOW_CONFIDENCE_PRIOR', 'evidence_id': 'RCV-EVD-0174', 'source_id': 'RCV-SRC-0003', 'provenance_batch': 'STRICT_PROVENANCE_AUDIT_V2_2', 'canonical_generation': 'RECOVERY_20260910', 'model_eligibility': 'PRIOR_ONLY'}}
INTERP_WRAPPER='\ndef interpret(text):\n    out = _interpret_legacy(text)\n    t = out["normalized_text"]\n    prefs = out["preferences"]\n    for a in AXES:\n        prefs["weights"][a] = 0.0\n\n    axis_matches = {a: [] for a in AXES}\n    flat = []\n    for axis, pattern, target, weight, hard_min, hard_max, rule_type in RULES:\n        m = re.search(pattern, t, flags=re.IGNORECASE)\n        if not m:\n            continue\n        item = {\n            "axis": axis, "axis_label_ja": AXIS_LABEL_JA[axis],\n            "matched_text": m.group(0), "rule_type": rule_type,\n            "target": target, "weight": weight,\n            "hard_min": hard_min, "hard_max": hard_max,\n        }\n        axis_matches[axis].append(item)\n        flat.append(item)\n\n    for axis, ms in axis_matches.items():\n        if not ms:\n            continue\n        hard = [m for m in ms if m["rule_type"] == "HARD_AVOID"]\n        directional = [m for m in ms if m["rule_type"] in {"STRONG_POS","LOW_PREF","POS"}]\n        chosen = hard[0] if hard else (directional[0] if directional else ms[0])\n        prefs["targets"][axis] = float(chosen["target"])\n        prefs["weights"][axis] = float(chosen["weight"])\n        mins = [float(m["hard_min"]) for m in ms if m.get("hard_min") is not None]\n        maxs = [float(m["hard_max"]) for m in ms if m.get("hard_max") is not None]\n        prefs["hard_constraints"][axis]["min"] = max(mins) if mins else None\n        prefs["hard_constraints"][axis]["max"] = min(maxs) if maxs else None\n\n    brand_matches = [m for m in out.get("matches", []) if m.get("rule_type") == "BRAND_EXCLUSION"]\n    out["matches"] = flat + brand_matches\n    out["active_axes"] = sorted(a for a in AXES if prefs["weights"][a] > 0)\n    out["interpretation_confidence"] = round(\n        min(0.98, 0.65 + 0.07 * len(out["matches"])) if out["matches"] else 0.0, 2\n    )\n    return out\n'
REC_WRAPPER='\ndef _has_constraint_or_exclusion(p):\n    return (\n        any(\n            p["hard_constraints"][a]["min"] is not None\n            or p["hard_constraints"][a]["max"] is not None\n            for a in AXES\n        )\n        or bool(p["exclude_brands"])\n        or bool(p["exclude_flavors"])\n    )\n\ndef _constraint_violations(vector, p):\n    violations = []\n    for a in AXES:\n        s = float(vector[a]["score"])\n        c = float(vector[a]["confidence"])\n        band = p["uncertainty_band_points"] * (1.0 - c)\n        lower, upper = s - band, s + band\n        amin = p["hard_constraints"][a]["min"]\n        amax = p["hard_constraints"][a]["max"]\n        if amin is not None and lower < amin:\n            violations.append(f"{a}: conservative lower {lower:.1f} < min {amin:.1f}")\n        if amax is not None and upper > amax:\n            violations.append(f"{a}: conservative upper {upper:.1f} > max {amax:.1f}")\n    return violations\n\ndef _evaluate_vector(vector, prefs):\n    p = normalize_preferences(prefs)\n    total_w = sum(p["weights"].values())\n    violations = _constraint_violations(vector, p)\n\n    if total_w <= 0:\n        if not _has_constraint_or_exclusion(p):\n            return {\n                "eligible": False, "violations": ["NO_ACTIVE_PREFERENCE"],\n                "base_fit": 0.0, "confidence_coverage": 0.0,\n                "uncertainty_penalty": 0.0, "final_score": 0.0,\n                "axis_detail": {\n                    a: {"score": float(vector[a]["score"]),\n                        "confidence": float(vector[a]["confidence"]),\n                        "target": p["targets"][a],\n                        "similarity": None, "effective_match": None}\n                    for a in AXES\n                },\n            }\n        return {\n            "eligible": not violations, "violations": violations,\n            "base_fit": 50.0, "confidence_coverage": 0.0,\n            "uncertainty_penalty": 0.0, "final_score": 50.0,\n            "axis_detail": {\n                a: {"score": float(vector[a]["score"]),\n                    "confidence": float(vector[a]["confidence"]),\n                    "target": p["targets"][a],\n                    "similarity": None, "effective_match": None}\n                for a in AXES\n            },\n        }\n\n    ev = _evaluate_vector_legacy(vector, p)\n    if violations:\n        ev["eligible"] = False\n        ev["violations"] = sorted(set(ev.get("violations", []) + violations))\n    return ev\n'
SERVICE_NEEDLE='        self.dataset = rec.load_dataset(\n            self.base_dir / "recommender_flavors_v0_8.csv",\n            self.base_dir / "recommender_variants_v0_8.csv",\n            self.base_dir / "recommender_scores_v0_8.csv",\n        )\n'
SERVICE_ADDITION='        self.dataset = rec.load_dataset(\n            self.base_dir / "recommender_flavors_v0_8.csv",\n            self.base_dir / "recommender_variants_v0_8.csv",\n            self.base_dir / "recommender_scores_v0_8.csv",\n        )\n        self.dataset_fingerprint = dataset_fingerprint(\n            self.base_dir / "recommender_flavors_v0_8.csv",\n            self.base_dir / "recommender_variants_v0_8.csv",\n            self.base_dir / "recommender_scores_v0_8.csv",\n        )\n'

def patch_interpreter():
    p=BASE/"shisha_preference_interpreter_v0_9.py"
    s=p.read_text(encoding="utf-8")
    s=s.replace('"weights": {a: 1.0 for a in AXES},','"weights": {a: 0.0 for a in AXES},')
    s=s.replace("def interpret(text):","def _interpret_legacy(text):",1)
    marker="\ndef preference_summary_ja"
    s=s.replace(marker,INTERP_WRAPPER+marker,1)
    p.write_text(s,encoding="utf-8")

def patch_feedback():
    p=BASE/"shisha_feedback_loop_v1_1.py"
    s=p.read_text(encoding="utf-8")
    s=s.replace('"targets":{a:50.0 for a in AXES},"weights":{a:1.0 for a in AXES},','"targets":{a:50.0 for a in AXES},"weights":{a:0.0 for a in AXES},')
    s=s.replace('"precedence":"CURRENT_EXPLICIT > CURRENT_SEMANTIC > READY_PROFILE > NEUTRAL",','"precedence":"CURRENT_EXPLICIT > CURRENT_SEMANTIC > READY_PROFILE > INACTIVE",')
    p.write_text(s,encoding="utf-8")

def patch_recommender():
    p=BASE/"shisha_recommender_v0_8.py"
    s=p.read_text(encoding="utf-8")
    s=s.replace('weights = {a: max(0.0, float(p.get("weights", {}).get(a, 1.0))) for a in AXES}','weights = {a: max(0.0, float(p.get("weights", {}).get(a, 0.0))) for a in AXES}')
    s=s.replace("def _evaluate_vector(vector, prefs):","def _evaluate_vector_legacy(vector, prefs):",1)
    marker="\ndef recommend_singles"
    s=s.replace(marker,REC_WRAPPER+marker,1)
    s=s.replace('def recommend_singles(dataset, prefs, limit=20):\n    p = normalize_preferences(prefs)\n    out = []','def recommend_singles(dataset, prefs, limit=20):\n    p = normalize_preferences(prefs)\n    if sum(p["weights"].values()) <= 0 and not _has_constraint_or_exclusion(p):\n        return []\n    out = []')
    s=s.replace('if row["flavor_name"] in p["exclude_flavors"]:\n            continue','if row["flavor_id"] in p["exclude_flavors"] or row["flavor_name"] in p["exclude_flavors"]:\n            continue')
    p.write_text(s,encoding="utf-8")

def patch_scores():
    p=BASE/"recommender_scores_v0_8.csv"
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f)); fields=list(rows[0].keys())
    seen=set()
    for r in rows:
        if r["score_id"] in SCORE_UPDATES:
            r.update(SCORE_UPDATES[r["score_id"]]); seen.add(r["score_id"])
    assert seen==set(SCORE_UPDATES)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    assert hashlib.sha256(p.read_bytes()).hexdigest()==EXPECTED_SCORES_SHA

def patch_service():
    p=BASE/"shisha_hardened_service_v1_7.py"
    s=p.read_text(encoding="utf-8")
    s=s.replace('SERVICE_VERSION = "v1.7"','SERVICE_VERSION = "v2.3-rc"')
    s=s.replace('from shisha_advisor_app_v1_3 import load_modules','from shisha_advisor_app_v1_3 import load_modules, dataset_fingerprint')
    assert SERVICE_NEEDLE in s
    s=s.replace(SERVICE_NEEDLE,SERVICE_ADDITION)
    s=s.replace('"auth_mode": self.auth_mode,\n                    "uptime_seconds":','"auth_mode": self.auth_mode,\n                    "dataset_fingerprint": self.dataset_fingerprint,\n                    "uptime_seconds":')
    s=s.replace('"database_schema": 2,\n                    "auth_mode": self.auth_mode,','"database_schema": 2,\n                    "auth_mode": self.auth_mode,\n                    "dataset_fingerprint": self.dataset_fingerprint,')
    p.write_text(s,encoding="utf-8")

def dataset_fingerprint():
    h=hashlib.sha256()
    for name in ["recommender_flavors_v0_8.csv","recommender_variants_v0_8.csv","recommender_scores_v0_8.csv"]:
        p=BASE/name
        h.update(p.name.encode()); h.update(b"\0")
        h.update(bytes.fromhex(hashlib.sha256(p.read_bytes()).hexdigest()))
    return h.hexdigest()

def main():
    patch_interpreter(); patch_feedback(); patch_recommender(); patch_scores(); patch_service()
    fp=dataset_fingerprint(); assert fp==EXPECTED_DATASET_FP,(fp,EXPECTED_DATASET_FP)
    manifest={"runtime_version":"v2.3-rc","data_version":"v2.2-audited","dataset_fingerprint":fp,"scores_sha256":EXPECTED_SCORES_SHA,"sparse_preferences":True,"inactive_axis_weight":0.0,"hard_constraints_apply_at_weight_zero":True,"same_axis_composition":True}
    (BASE/"rc_runtime_manifest_v2_3.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"rc_patch":"APPLIED",**manifest},ensure_ascii=False))
if __name__=="__main__": main()
