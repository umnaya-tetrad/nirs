"""Write the independently curated domain sidecar for final-80 v2.

The mapping was prepared from canonical GT steps and, for the 22 replacement
rows, the original FERMAT question plus its domain/subdomain metadata.  It
deliberately never reads model predictions, CAS results, or evaluator metrics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluator.domains import validate


MANIFEST = ROOT / "dataset/manifests/fermat_final_80_v2.json"
DESTINATION = ROOT / "dataset/annotations/math_domains_final80_v2.json"

# domain, features, concise task description.  Domains and feature tokens are
# constrained by evaluator.domains; task type remains explanatory metadata.
ANNOTATIONS = {
    "img_400_pert_5.1": ("calculus", ["powers", "logarithms", "derivatives"], "derivative of an exponential"),
    "img_374_pert_5.1": ("calculus", ["fractions", "trigonometric_functions", "integrals"], "definite integral"),
    "img_19_pert_5.1": ("geometry", ["fractions"], "section formula / coordinate geometry"),
    "img_559_pert_5.1": ("algebraic_expression", ["polynomials"], "polynomial subtraction"),
    "img_464_pert_5.1": ("linear_algebra", ["other"], "2x2 determinant"),
    "img_387_pert_5.1": ("calculus", ["powers", "trigonometric_functions", "derivatives"], "second derivative"),
    "img_22_pert_5.1": ("geometry", ["fractions"], "midpoint coordinate equation"),
    "img_568_pert_5.2": ("algebraic_expression", ["powers"], "complex-number powers"),
    "img_482_pert_5.2": ("equation", ["other"], "linear equations in standard form"),
    "img_559_pert_5.2": ("algebraic_expression", ["polynomials"], "polynomial expression"),
    "img_448_pert_5.2": ("linear_algebra", ["matrices"], "matrix distributivity"),
    "img_173_pert_5.3": ("arithmetic", ["fractions"], "fraction simplification"),
    "img_165_pert_5.3": ("equation", ["powers"], "quadratic equation / substitution"),
    "img_193_pert_5.3": ("arithmetic", ["fractions"], "multiplication of fractions"),
    "img_375_pert_5.3": ("calculus", ["absolute_value", "polynomials", "integrals"], "definite integral with absolute value"),
    "img_233_pert_3.2": ("arithmetic", ["fractions", "powers"], "powers of fractions"),
    "img_190_pert_3.2": ("arithmetic", ["fractions"], "decimal arithmetic"),
    "img_559_pert_3.2": ("algebraic_expression", ["polynomials"], "polynomial subtraction"),
    "img_172_pert_3.2": ("arithmetic", ["fractions"], "equivalent fractions"),
    "img_586_pert_3.2": ("algebraic_expression", ["powers", "polynomials"], "binomial cube expansion"),
    "img_448_pert_3.2": ("linear_algebra", ["matrices"], "matrix distributivity"),
    "img_173_pert_2.5": ("arithmetic", ["fractions"], "fraction simplification"),
    "img_35_pert_2.5": ("geometry", ["powers", "radicals", "word_problem"], "right cone volume"),
    "img_375_pert_2.5": ("calculus", ["absolute_value", "polynomials", "integrals"], "definite integral with absolute value"),
    "img_574_pert_2.5": ("equation", ["fractions", "powers", "polynomials"], "cubic roots and Vieta relations"),
    "img_395_pert_2.5": ("calculus", ["fractions", "trigonometric_functions", "derivatives"], "parametric derivative"),
    "img_68_pert_2.5": ("geometry", ["fractions", "radicals"], "angle between vectors"),
    "img_111_pert_1.3": ("trigonometry", ["radicals", "trigonometric_functions"], "inverse-trigonometric identity"),
    "img_463_pert_1.3": ("linear_algebra", ["radicals", "other"], "determinant equation"),
    "img_465_pert_1.3": ("linear_algebra", ["matrices"], "matrix inverse via polynomial identity"),
    "img_108_pert_1.4": ("trigonometry", ["radicals", "trigonometric_functions"], "trigonometric value reduction"),
    "img_427_pert_1.4": ("calculus", ["fractions", "powers", "radicals", "derivatives"], "limits"),
    "img_472_pert_1.4": ("geometry", ["other"], "coordinate-geometry determinants"),
    "img_503_pert_1.4": ("function", ["other"], "composition of functions"),
    "img_466_pert_1.4": ("linear_algebra", ["matrices"], "cofactors / determinant"),
    "img_111_pert_2.1": ("trigonometry", ["radicals", "trigonometric_functions"], "inverse-trigonometric identity"),
    "img_98_pert_2.1": ("trigonometry", ["fractions", "powers", "trigonometric_functions"], "trigonometric identities"),
    "img_372_pert_2.1": ("calculus", ["radicals", "trigonometric_functions", "integrals"], "definite integral"),
    "img_109_pert_2.1": ("trigonometry", ["fractions", "trigonometric_functions"], "degree-to-radian conversion"),
    "img_223_pert_2.2": ("algebraic_expression", ["fractions", "powers"], "laws of exponents"),
    "img_465_pert_2.2": ("linear_algebra", ["matrices"], "matrix inverse"),
    "img_529_pert_2.2": ("equation", ["other"], "linear equations"),
    "img_573_pert_2.2": ("algebraic_expression", ["radicals", "powers"], "complex-number expression"),
    "img_226_pert_2.2": ("algebraic_expression", ["fractions", "powers"], "laws of exponents"),
    "img_176_pert_4.3": ("arithmetic", ["fractions"], "multiplication of fractions"),
    "img_92_pert_4.3": ("geometry", ["fractions", "trigonometric_functions", "word_problem"], "arc length"),
    "img_91_pert_2.3": ("trigonometry", ["fractions", "powers", "radicals", "trigonometric_functions"], "trigonometric ratios"),
    "img_112_pert_4.4": ("trigonometry", ["fractions", "trigonometric_functions"], "inverse-trigonometric identity"),
    "img_115_pert_4.4": ("trigonometry", ["radicals", "trigonometric_functions"], "special trigonometric value"),
    "img_529_pert_4.5": ("equation", ["other"], "linear system"),
    "img_160_pert_2.4": ("arithmetic", ["radicals"], "square root simplification"),
    "img_560_pert_1.5": ("algebraic_expression", ["powers", "polynomials"], "algebraic substitution"),
    "img_465_pert_1.5": ("linear_algebra", ["matrices"], "matrix inverse"),
    "img_540_pert_1.5": ("geometry", ["fractions", "trigonometric_functions"], "angle between vectors"),
    "img_153_pert_1.5": ("arithmetic", ["radicals"], "radical multiplication"),
    "img_194_pert_1.5": ("arithmetic", ["fractions", "word_problem"], "factorial equation"),
    "img_220_pert_1.5": ("algebraic_expression", ["fractions", "powers"], "negative exponents"),
    "img_220_pert_4.6": ("algebraic_expression", ["fractions", "powers"], "negative exponents"),
    "img_476_pert_5.1": ("inequality", ["fractions"], "compound linear inequality"),
    "img_579_pert_5.1": ("equation", ["fractions", "polynomials"], "quadratic factorisation"),
    "img_578_pert_5.1": ("equation", ["powers", "polynomials"], "quadratic discriminant"),
    "img_489_pert_5.1": ("equation", ["word_problem"], "linear word problem"),
    "img_490_pert_5.1": ("equation", ["word_problem"], "linear age word problem"),
    "img_483_pert_5.1": ("equation", ["fractions", "word_problem"], "linear word problem"),
    "img_592_pert_5.1": ("equation", ["polynomials"], "quadratic zeroes and coefficients"),
    "img_456_pert_5.1": ("linear_algebra", ["matrices"], "matrix multiplication"),
    "img_455_pert_5.1": ("linear_algebra", ["matrices"], "matrix linear combination"),
    "img_458_pert_5.1": ("linear_algebra", ["fractions", "absolute_value", "matrices"], "matrix entries"),
    "img_566_pert_5.1": ("algebraic_expression", ["fractions", "radicals", "powers"], "complex numbers"),
    "img_572_pert_5.1": ("equation", ["fractions"], "complex-number coefficient comparison"),
    "img_65_pert_5.1": ("geometry", ["powers", "radicals"], "3D coordinate locus"),
    "img_27_pert_5.1": ("geometry", ["other"], "line through point with slope"),
    "img_14_pert_5.1": ("geometry", ["powers"], "equidistant points locus"),
    "img_49_pert_5.1": ("geometry", ["fractions", "word_problem"], "rhombus area"),
    "img_77_pert_5.1": ("geometry", ["powers", "word_problem"], "circle area"),
    "img_78_pert_5.1": ("geometry", ["powers", "word_problem"], "sphere surface area"),
    "img_37_pert_5.1": ("geometry", ["powers", "word_problem"], "sphere volume"),
    "img_20_pert_5.1": ("geometry", ["fractions"], "section formula / coordinate geometry"),
    "img_492_pert_5.1": ("linear_algebra", ["fractions", "matrices", "systems"], "linear system using inverse matrix"),
    "img_488_pert_5.1": ("equation", ["fractions", "systems"], "linear system by substitution"),
}

FERMAT_REPLACEMENT_IDS = {
    "img_476_pert_5.1", "img_579_pert_5.1", "img_578_pert_5.1", "img_489_pert_5.1", "img_490_pert_5.1",
    "img_483_pert_5.1", "img_592_pert_5.1", "img_456_pert_5.1", "img_455_pert_5.1", "img_458_pert_5.1",
    "img_566_pert_5.1", "img_572_pert_5.1", "img_65_pert_5.1", "img_27_pert_5.1", "img_14_pert_5.1",
    "img_49_pert_5.1", "img_77_pert_5.1", "img_78_pert_5.1", "img_37_pert_5.1", "img_20_pert_5.1",
    "img_492_pert_5.1", "img_488_pert_5.1",
}

# Immutable provenance copied from the FERMAT rows used during v2 construction.
# Keep this compact map in source so regeneration does not depend on an ignored
# local HF download cache.
FERMAT_CODES = {
    "img_65_pert_5.1": ("mgm", "3dg"), "img_456_pert_5.1": ("alg", "mat"),
    "img_49_pert_5.1": ("mgm", "plg"), "img_27_pert_5.1": ("mgm", "lns"),
    "img_77_pert_5.1": ("mgm", "sfa"), "img_578_pert_5.1": ("alg", "pyn"),
    "img_14_pert_5.1": ("mgm", "lns"), "img_566_pert_5.1": ("alg", "cpx"),
    "img_572_pert_5.1": ("alg", "cpx"), "img_476_pert_5.1": ("alg", "lin"),
    "img_20_pert_5.1": ("mgm", "lns"), "img_579_pert_5.1": ("alg", "pyn"),
    "img_490_pert_5.1": ("alg", "leq"), "img_489_pert_5.1": ("alg", "leq"),
    "img_78_pert_5.1": ("mgm", "sfa"), "img_37_pert_5.1": ("mgm", "vol"),
    "img_592_pert_5.1": ("alg", "pyn"), "img_458_pert_5.1": ("alg", "mat"),
    "img_455_pert_5.1": ("alg", "mat"), "img_483_pert_5.1": ("alg", "leq"),
    "img_492_pert_5.1": ("alg", "leq"), "img_488_pert_5.1": ("alg", "leq"),
}

# Directly viewed during this post-hoc audit.  The other records are source-
# checked against canonical GT (and FERMAT metadata for replacement records),
# rather than falsely claiming an image-by-image visual audit.
VISUALLY_CONFIRMED = {"img_65_pert_5.1", "img_374_pert_5.1", "img_465_pert_1.3"}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    if FERMAT_REPLACEMENT_IDS != set(FERMAT_CODES):
        raise ValueError("FERMAT provenance map must cover exactly the replacement IDs")
    ids = [case["id"] for case in manifest]
    if set(ids) != set(ANNOTATIONS):
        raise ValueError(f"annotation/manifest ID mismatch: missing={set(ids)-set(ANNOTATIONS)}, extra={set(ANNOTATIONS)-set(ids)}")
    records = []
    for identifier in ids:
        domain, features, task_type = ANNOTATIONS[identifier]
        replacement = identifier in FERMAT_REPLACEMENT_IDS
        source_metadata = ({} if not replacement else {
            "dataset": "ai4bharat/FERMAT",
            "domain_code": FERMAT_CODES[identifier][0],
            "subdomain_code": FERMAT_CODES[identifier][1],
            "orig_q_available": True,
        })
        records.append({
            "solution_id": identifier,
            "domain": domain,
            "features": features,
            "task_type": task_type,
            "annotation_source": "canonical_gt_steps + FERMAT orig_q/domain/subdomain" if replacement else "canonical_gt_steps",
            "source_metadata": source_metadata,
            "review_status": "visual_confirmed" if identifier in VISUALLY_CONFIRMED else "source_checked_not_visually_audited",
            "uncertain": False,
            "notes": "Primary domain selected by mathematical object/operation; word_problem is a feature, not a domain.",
        })
    payload = {
        "annotation_version": "1.1",
        "purpose": "Independent post-hoc descriptive annotation; never sent to VLMs or CAS and not used to select final-80 v2.",
        "taxonomy": {
            "domain": "Primary mathematical area from the canonical solution/task.",
            "task_type": "Human-readable problem type; not a scoring category.",
            "features": "Allowed notation/construction features from evaluator.domains.FEATURES.",
        },
        "records": records,
    }
    DESTINATION.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validate(DESTINATION, MANIFEST, require_complete=True), ensure_ascii=False))


if __name__ == "__main__":
    main()
