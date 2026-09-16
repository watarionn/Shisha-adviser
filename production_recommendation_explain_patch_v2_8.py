from __future__ import annotations

from pathlib import Path

TARGET = Path('/app/shisha_recommender_v0_8.py')


def main():
    source = TARGET.read_text(encoding='utf-8')

    anchor = '\ndef recommend_pairs(dataset, prefs, limit=20, pool_size=30):\n'
    helper = r'''
def _mix_recommendation_reason(ev, prefs):
    """Return explanation-only metadata without changing ranking or scores."""
    p = normalize_preferences(prefs)
    active_axes = [a for a in AXES if p["weights"][a] > 0]
    if not active_axes:
        return {
            "reason_version": "mix-reason-v1",
            "top_match_axes": [],
            "uncertain_axes": [],
            "match_axes": [],
        }

    def contribution(axis):
        detail = ev["axis_detail"][axis]
        similarity = detail.get("similarity")
        similarity = 0.0 if similarity is None else float(similarity)
        return (
            float(p["weights"][axis])
            * float(detail.get("confidence", 0.0))
            * similarity
        )

    top_match_axes = sorted(
        active_axes,
        key=lambda axis: (contribution(axis), axis),
        reverse=True,
    )[:3]
    uncertain_axes = sorted(
        active_axes,
        key=lambda axis: (float(ev["axis_detail"][axis].get("confidence", 0.0)), axis),
    )[:2]

    match_axes = []
    for axis in top_match_axes:
        detail = ev["axis_detail"][axis]
        similarity = detail.get("similarity")
        match_axes.append({
            "axis": axis,
            "target": round(float(p["targets"][axis]), 2),
            "score": round(float(detail.get("score", 0.0)), 2),
            "confidence": round(float(detail.get("confidence", 0.0)), 4),
            "similarity": round(0.0 if similarity is None else float(similarity), 4),
            "weight": round(float(p["weights"][axis]), 4),
            "contribution": round(contribution(axis), 4),
        })

    return {
        "reason_version": "mix-reason-v1",
        "top_match_axes": top_match_axes,
        "uncertain_axes": uncertain_axes,
        "match_axes": match_axes,
    }

'''

    if '_mix_recommendation_reason' not in source:
        if anchor not in source:
            raise SystemExit('recommend_pairs anchor not found')
        source = source.replace(anchor, '\n' + helper + 'def recommend_pairs(dataset, prefs, limit=20, pool_size=30):\n', 1)

    needle = '                "uncertainty_penalty": round(ev["uncertainty_penalty"],4),\n            })'
    replacement = (
        '                "uncertainty_penalty": round(ev["uncertainty_penalty"],4),\n'
        '                **_mix_recommendation_reason(ev, prefs),\n'
        '            })'
    )
    count = source.count(needle)
    if count not in (0, 2):
        raise SystemExit(f'unexpected mix output patch count: {count}')
    if count == 2:
        source = source.replace(needle, replacement, 2)

    required = [
        'def _mix_recommendation_reason',
        '"reason_version": "mix-reason-v1"',
        '**_mix_recommendation_reason(ev, prefs)',
    ]
    missing = [item for item in required if item not in source]
    if missing:
        raise SystemExit(f'patch validation failed: {missing}')
    if source.count('**_mix_recommendation_reason(ev, prefs)') != 2:
        raise SystemExit('expected exactly two MIX/TRIPLE reason payload insertions')

    TARGET.write_text(source, encoding='utf-8')
    print('patched recommender explanation metadata for PAIR/TRIPLE')


if __name__ == '__main__':
    main()
