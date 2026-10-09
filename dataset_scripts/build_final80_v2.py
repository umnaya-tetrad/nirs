"""Build the frozen final-80 v2 manifest and canonical GT.

The 20 replacement transcriptions below were entered after visual review of the
downloaded FERMAT photographs.  They deliberately preserve the notation that
is written on the image (including awkward variable choices), rather than
silently repairing it from FERMAT's text fields.

This script does not download data and does not call a model or CAS.  It only
materializes the reviewed data release from final-80 v1 plus the reviewed
replacement table.
"""
from __future__ import annotations

import json
import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V1_GT = ROOT / "dataset" / "final_gt.json"
V1_MANIFEST = ROOT / "dataset" / "manifests" / "fermat_final_80.json"
V2_GT = ROOT / "dataset" / "final_gt_v2.json"
V2_MANIFEST = ROOT / "dataset" / "manifests" / "fermat_final_80_v2.json"
REPLACEMENTS_OUT = ROOT / "dataset" / "final80_v2_replacements.json"
QC_OUT = ROOT / "dataset" / "qc" / "final80_v2_new_gt_qc.json"
V2_E2E_TEMPLATE = ROOT / "evaluator" / "manifests" / "final80_v2_e2e_template.json"
V2_CAS_TEMPLATE = ROOT / "evaluator" / "manifests" / "final80_v2_cas_supported_template.json"
V2_DOMAIN_TEMPLATE = ROOT / "dataset" / "annotations" / "math_domains_final80_v2_template.csv"
V2_DOMAIN_SIDECAR = ROOT / "dataset" / "annotations" / "math_domains_final80_v2.json"
PROVENANCE_OUT = ROOT / "dataset" / "provenance_fermat_final80_v2_new.json"
SOURCE_ROWS = ROOT / "data" / "final80_v2_source_rows.json"

# Prefer removing base problems which overlap dev by img_id.  Twenty removed
# records are v1 incorrect; the final two are v1 correct and are removed only
# because they still overlap dev at the base-problem level.
REMOVED_IDS = [
    "img_494_pert_3.1", "img_462_pert_3.1", "img_151_pert_3.2",
    "img_471_pert_3.2", "img_462_pert_2.5", "img_494_pert_2.5",
    "img_96_pert_1.4", "img_151_pert_4.3", "img_373_pert_2.3",
    "img_157_pert_2.4", "img_398_pert_2.4", "img_157_pert_1.5",
    "img_225_pert_1.5", "img_568_pert_3.1", "img_466_pert_3.1",
    "img_542_pert_3.1", "img_108_pert_3.1", "img_89_pert_3.1",
    "img_559_pert_3.1", "img_99_pert_3.1",
    "img_480_pert_5.1", "img_494_pert_5.1",
]


# (FERMAT img_id, FERMAT domain/subdomain, photo file suffix, visible lines)
# Each list is the observed mathematical sequence, excluding prose.  Do not
# normalize variables or add an idealized missing derivation.
NEW = [
    ("img_476_pert_5.1", "476", "alg/lin", ".jpg", [
        r"-5 \leq \frac{5-3y}{2} \leq 8",
        r"-10 \leq 5-3y \leq 16",
        r"5 \geq y \geq -\frac{11}{3}",
        r"-\frac{11}{3} \leq y \leq 5",
    ]),
    ("img_579_pert_5.1", "579", "alg/pyn", ".jpg", [
        r"2y^2-5y+3=2y^2-2y-3y+3",
        r"=2y(y-1)-3(y-1)=(2y-3)(y-1)",
        r"(2y-3)(y-1)=0",
        r"2y-3=0\ \text{or}\ y-1=0",
        r"y=\frac{3}{2}\ \text{or}\ y=1",
    ]),
    ("img_578_pert_5.1", "578", "alg/pyn", ".jpg", [
        r"px^2+qx+r=0,\quad p=2,\ q=-4,\ r=3",
        r"q^2-4pr=(-4)^2-(4\times2\times3)=16-24=-8<0",
    ]),
    ("img_489_pert_5.1", "489", "alg/leq", ".jpg", [
        r"3y+11=32",
        r"3y=32-11=21",
        r"y=\frac{21}{3}=7",
    ]),
    ("img_490_pert_5.1", "490", "alg/leq", ".jpg", [
        r"3x+5=44",
        r"3x=44-5=39",
        r"x=13",
    ]),
    ("img_483_pert_5.1", "483", "alg/leq", ".jpg", [
        r"\frac{z}{4}-7=3",
        r"\frac{z}{4}=3+7=10",
        r"z=10\times4=40",
    ]),
    ("img_592_pert_5.1", "592", "alg/pyn", ".png", [
        r"y^2+7y+10=(y+2)(y+5)",
        r"y+2=0\ \text{or}\ y+5=0,\quad y=-2\ \text{or}\ y=-5",
        r"-2+(-5)=-7=-\frac{7}{1}",
        r"(-2)(-5)=10=\frac{10}{1}",
    ]),
    ("img_456_pert_5.1", "456", "alg/mat", ".jpg", [
        r"P=\begin{bmatrix}0&-1\\0&2\end{bmatrix},\quad Q=\begin{bmatrix}3&5\\0&0\end{bmatrix}",
        r"PQ=\begin{bmatrix}0&-1\\0&2\end{bmatrix}\begin{bmatrix}3&5\\0&0\end{bmatrix}=\begin{bmatrix}0&0\\0&0\end{bmatrix}",
    ]),
    ("img_455_pert_5.1", "455", "alg/mat", ".jpg", [
        r"2A-B=2\begin{bmatrix}1&2&3\\2&3&1\end{bmatrix}-\begin{bmatrix}3&-1&3\\-1&0&2\end{bmatrix}",
        r"=X\begin{bmatrix}1&2&3\\2&3&1\end{bmatrix}+\begin{bmatrix}-3&1&-3\\1&0&-2\end{bmatrix}",
        r"=\begin{bmatrix}a-3&4+1&6-3\\4+1&6+0&2-2\end{bmatrix}",
        r"=\begin{bmatrix}-1&5&3\\5&6&0\end{bmatrix}",
    ]),
    ("img_458_pert_5.1", "458", "alg/mat", ".jpg", [
        r"a_{ij}=\frac{1}{2}|i-3j|,\quad i=1,2,3,\ j=1,2",
        r"a_{11}=\frac{1}{2}|1-3\times1|=1,\quad a_{21}=\frac{1}{2}|2-3\times1|=\frac{1}{2},\quad a_{31}=\frac{1}{2}|3-3\times1|=0",
        r"a_{12}=\frac{1}{2}|1-3\times2|=\frac{5}{2},\quad a_{22}=\frac{1}{2}|2-3\times2|=2,\quad a_{32}=\frac{1}{2}|3-3\times2|=\frac{3}{2}",
        r"B=\begin{bmatrix}1&\frac{5}{2}\\\frac{1}{2}&2\\0&\frac{3}{2}\end{bmatrix}",
    ]),
    ("img_566_pert_5.1", "566", "alg/cpx", ".jpg", [
        r"\frac{5+\sqrt{2}j}{1-\sqrt{2}j}=\frac{5+\sqrt{2}j}{1-\sqrt{2}j}\times\frac{1+\sqrt{2}j}{1+\sqrt{2}j}",
        r"=\frac{3+6\sqrt{2}j}{1+2}=\frac{3(1+2\sqrt{2}j)}{3}=1+2\sqrt{2}j",
        r"j^{-35}=\frac{1}{j^{35}}=\frac{1}{(j^2)^{17}j}=\frac{1\times j}{-j}=\frac{j}{-(-1)}=j",
    ]),
    ("img_572_pert_5.1", "572", "alg/cpx", ".jpg", [
        r"4a+i(3a-b)=3+i(-6)",
        r"4a=3,\quad 3a-b=-6",
        r"a=\frac{3}{4},\quad b=\frac{33}{4}",
    ]),
    ("img_65_pert_5.1", "65", "mgm/3dg", ".jpg", [
        r"\sqrt{(u-3)^2+(v-4)^2+(w+5)^2}=\sqrt{(u+2)^2+(v-1)^2+(w-4)^2}",
        r"(u-3)^2+(v-4)^2+(w+5)^2=(u+2)^2+(v-1)^2+(w-4)^2",
        r"10u+6v-18w-29=0",
    ]),
    ("img_27_pert_5.1", "27", "mgm/lns", ".jpg", [
        r"v-3=-4(u+2)",
        r"4u+v+5=0",
    ]),
    ("img_14_pert_5.1", "14", "mgm/lns", ".jpg", [
        r"(a-7)^2+(b-1)^2=(a-3)^2+(b-5)^2",
        r"a^2-14a+49+b^2-2b+1=a^2-6a+9+b^2-10b+25",
        r"-14a+49-2b+1=-6a+9-10b+25",
        r"-8a+10b+15=0",
    ]),
    ("img_49_pert_5.1", "49", "mgm/plg", ".jpg", [
        r"\operatorname{Area}=\frac{1}{2}d_3d_4=240",
        r"\frac{1}{2}\cdot16\cdot d_4=240",
        r"8d_4=240",
        r"d_4=\frac{240}{8}=30",
    ]),
    ("img_77_pert_5.1", "77", "mgm/sfa", ".jpg", [
        r"R=\frac{9.8}{2}=4.9",
        r"\pi R^2=\frac{22}{7}(4.9)^2=\frac{22}{7}\times4.9\times4.9=75.46",
    ]),
    ("img_78_pert_5.1", "78", "mgm/sfa", ".jpg", [
        r"4\pi a^2=4\times\frac{22}{7}\times a\times a=616",
    ]),
    ("img_37_pert_5.1", "37", "mgm/vol", ".jpg", [
        r"\operatorname{Required\ Volume}=\frac{4}{3}\pi a^3",
        r"=\frac{4}{3}\times\frac{22}{7}\times b\times b\times b=5887.32",
    ]),
    ("img_20_pert_5.1", "20", "mgm/lns", ".jpg", [
        r"\left(\frac{-m+5}{m+1},\frac{-4m-6}{m+1}\right)",
        r"\frac{-m+5}{m+1}=0",
        r"-m+5=0\Rightarrow m=5",
        r"(0,-\frac{13}{3})",
    ]),
    ("img_492_pert_5.1", "492", "alg/leq", ".jpg", [
        r"P=\begin{bmatrix}2&5\\3&2\end{bmatrix},\quad Q=\begin{bmatrix}x\\y\end{bmatrix},\quad R=\begin{bmatrix}1\\7\end{bmatrix}",
        r"|P|=-11\ne0",
        r"P^{-1}=-\frac{1}{11}\begin{bmatrix}2&-5\\-3&2\end{bmatrix}",
        r"Q=P^{-1}R=-\frac{1}{11}\begin{bmatrix}2&-5\\-3&2\end{bmatrix}\begin{bmatrix}1\\7\end{bmatrix}",
        r"\begin{bmatrix}x\\y\end{bmatrix}=-\frac{1}{11}\begin{bmatrix}-33\\3\end{bmatrix}",
        r"x=3,\quad y=1",
    ]),
    ("img_488_pert_5.1", "488", "alg/leq", ".jpg", [
        r"z+2y=3",
        r"z=3-2y",
        r"7(3-2y)-15y=2",
        r"21-14y-15y=2",
        r"21-29y=2",
        r"-29y=-19",
        r"y=\frac{19}{29}",
        r"z=3-2\left(\frac{19}{29}\right)=\frac{49}{29}",
        r"z=\frac{49}{29},\quad y=\frac{19}{29}",
    ]),
]


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_domain_template(cases: list[dict]) -> None:
    V2_DOMAIN_TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    with V2_DOMAIN_TEMPLATE.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["solution_id", "image_path", "domain", "features", "notes"])
        writer.writeheader()
        for case in cases:
            writer.writerow({"solution_id": case["id"], "image_path": case["image"], "domain": "", "features": "", "notes": ""})


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_provenance() -> None:
    """Write review-safe provenance without copying FERMAT answer text."""
    if not SOURCE_ROWS.is_file():
        raise FileNotFoundError(f"required local source metadata is missing: {SOURCE_ROWS}")
    source = {f"img_{row['img_id']}_pert_{row['new_pert_id']}": row for row in read(SOURCE_ROWS)}
    records = []
    for identifier, _, _, suffix, _ in NEW:
        row = source.get(identifier)
        if row is None:
            raise ValueError(f"source metadata has no row for {identifier}")
        image = ROOT / "data" / "images" / "final_v2" / f"{identifier}{suffix}"
        records.append({
            "id": identifier, "img_id": row["img_id"], "grade": row["grade"],
            "domain_code": row["domain_code"], "subdomain_code": row["subdomain_code"],
            "has_error": row["has_error"], "handwriting_style": row["handwriting_style"],
            "image_filename": image.name,
            "orig_q_sha256": sha256_text(row["orig_q"]), "orig_a_sha256": sha256_text(row["orig_a"]),
            "pert_a_sha256": sha256_text(row["pert_a"]),
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        })
    write(PROVENANCE_OUT, {
        "provenance_version": "1.0", "dataset": "ai4bharat/FERMAT",
        "revision": "80ff9934c38615bb8d3a33c24252db02e21774f0",
        "selection_rules": [
            "has_error=false", "handwriting_style=true", "new img_id relative to v1+dev",
            "candidate domains selected before CAS", "two additional correct rows replace v1 correct rows only to eliminate dev base-problem overlap",
        ],
        "records": sorted(records, key=lambda record: record["id"]),
    })


def make_gt(identifier: str, latex_lines: list[str]) -> dict:
    steps = []
    for index, latex in enumerate(latex_lines, 1):
        step = {"step_id": f"s{index}", "kind": "initial" if index == 1 else ("answer" if index == len(latex_lines) else "step"), "latex": latex}
        if index == 1:
            step["derives_from"] = []
        else:
            step["derives_from"] = [f"s{index - 1}"]
            step["transformation"] = {"type": "algebraic", "rule_hint": "ручная транскрипция следующей видимой математической строки"}
        steps.append(step)
    return {
        "schema_version": "1.0", "id": identifier, "steps": steps,
        "verdict": "correct", "is_correct": True, "first_error_step": None,
        "findings": [],
        "steps_reviewed": [{"step_id": step["step_id"], "verdict": "correct"} for step in steps],
        "summary": "Рукописное решение визуально сверено с фотографией FERMAT; математические строки сохранены без исправления записи автора.",
        "meta": {"run_id": "ground-truth-final80-v2", "approach": "llm_end_to_end", "stage": "report"},
    }


def main() -> None:
    v1_gt = read(V1_GT)
    v1_manifest = read(V1_MANIFEST)
    v1_by_id = {row["id"]: row for row in v1_gt}
    manifest_by_id = {row["id"]: row for row in v1_manifest["cases"]}
    if len(v1_gt) != 80 or len(v1_manifest["cases"]) != 80:
        raise ValueError("final-80 v1 must contain exactly 80 cases")
    if set(v1_by_id) != set(manifest_by_id):
        raise ValueError("v1 GT and manifest IDs differ")
    if len(REMOVED_IDS) != 22 or len(set(REMOVED_IDS)) != 22:
        raise ValueError("replacement list must have 22 unique old IDs")
    if not set(REMOVED_IDS) <= set(v1_by_id):
        raise ValueError("an old replacement ID is not in final v1")
    if any(v1_by_id[item]["verdict"] != "incorrect" for item in REMOVED_IDS[:20]):
        raise ValueError("the first 20 removed cases must be v1 incorrect")
    if any(v1_by_id[item]["verdict"] != "correct" for item in REMOVED_IDS[20:]):
        raise ValueError("the two dev-overlap removals must be v1 correct")
    new_ids = [item[0] for item in NEW]
    if len(NEW) != 22 or len(set(new_ids)) != 22 or set(new_ids) & set(v1_by_id):
        raise ValueError("new reviewed IDs must be 22 unique IDs outside v1")

    new_gt = []
    new_manifest_cases = []
    qc = []
    for identifier, img_id, domain, suffix, lines in NEW:
        image = ROOT / "data" / "images" / "final_v2" / f"{identifier}{suffix}"
        if not image.is_file():
            raise FileNotFoundError(image)
        new_gt.append(make_gt(identifier, lines))
        new_manifest_cases.append({
            "id": identifier,
            "image": f"../../data/images/final_v2/{identifier}{suffix}",
            "mime_type": "image/png" if suffix == ".png" else "image/jpeg",
        })
        qc.append({
            "id": identifier, "img_id": img_id, "fermat_domain": domain,
            "image_review": "reviewed_visually", "needs_manual_review": False,
            "review_scope": "all visible mathematical lines transcribed in reading order",
            "note": "The canonical GT preserves the written notation; no idealized correction was inserted.",
        })

    retained_gt = [row for row in v1_gt if row["id"] not in REMOVED_IDS]
    retained_cases = [row for row in v1_manifest["cases"] if row["id"] not in REMOVED_IDS]
    final_gt = retained_gt + new_gt
    final_manifest = {"cases": retained_cases + new_manifest_cases}
    if len(final_gt) != 80 or len(final_manifest["cases"]) != 80:
        raise AssertionError("v2 must contain 80 cases")
    if [row["id"] for row in final_gt] != [row["id"] for row in final_manifest["cases"]]:
        raise AssertionError("v2 GT and manifest order must be identical")
    correct = sum(row["verdict"] == "correct" for row in final_gt)
    if correct != 39:
        raise AssertionError(f"expected 39 correct records, got {correct}")

    write(V2_GT, final_gt)
    write(V2_MANIFEST, final_manifest)
    write(REPLACEMENTS_OUT, {
        "release": "final-80-v2", "base_release": "final-80-v1",
        "selection_policy": "20 v1 incorrect cases plus 2 dev-overlap v1 correct cases replaced by reviewed FERMAT correct handwritten cases; no CAS outcome was used for selection.",
        "removed_ids": REMOVED_IDS,
        "added_ids": new_ids,
        "pairs": [{"removed_id": old, "added_id": new} for old, new in zip(REMOVED_IDS, new_ids)],
    })
    write(QC_OUT, {
        "release": "final-80-v2", "records": qc,
        "summary": {"added": len(qc), "reviewed_visually": len(qc), "needs_manual_review": 0},
    })
    write_provenance()
    # Separate evaluator manifests make it impossible to mix v1 VLM outputs
    # with v2 IDs accidentally.  Prompts/contracts remain exactly unchanged.
    e2e = read(ROOT / "evaluator" / "manifests" / "final80_e2e_template.json")
    e2e["experiment_id"] = "final80_v2_e2e"
    e2e["dataset"]["split"] = "final-80-v2"
    e2e["dataset"]["gt_paths"] = ["dataset/final_gt_v2.json"]
    e2e["dataset"]["ids"] = [row["id"] for row in final_gt]
    e2e["dataset"]["domain_annotations"] = {"path": "dataset/annotations/math_domains_final80_v2.json"}
    for run in e2e["runs"]:
        run["source"]["path"] = run["source"]["path"].replace("outputs/final80/", "outputs/final80_v2/")
    write(V2_E2E_TEMPLATE, e2e)
    cas = read(ROOT / "evaluator" / "manifests" / "final80_cas_supported_template.json")
    cas["experiment_id"] = "final80_v2_cas_supported"
    cas["dataset"]["split"] = "final-80-v2-cas-supported"
    cas["dataset"]["gt_paths"] = ["dataset/final_gt_v2.json"]
    cas["dataset"]["ids_file"] = "dataset/subsets/cas_supported_final_80_v2.json"
    cas["dataset"]["cas_on_gt"] = {"path": "reports/cas_gt_final80_v2_frozen/predictions.json"}
    cas["dataset"]["domain_annotations"] = {"path": "dataset/annotations/math_domains_final80_v2.json"}
    for run in cas["runs"]:
        run["source"]["path"] = run["source"]["path"].replace("outputs/final80", "outputs/final80_v2")
        if "extraction_artifacts" in run:
            run["extraction_artifacts"]["path"] = run["extraction_artifacts"]["path"].replace("outputs/final80", "outputs/final80_v2")
    write(V2_CAS_TEMPLATE, cas)
    write_domain_template(final_manifest["cases"])
    write(V2_DOMAIN_SIDECAR, {
        "annotation_version": "1.0",
        "purpose": "Independent manual descriptive annotation; never sent to VLMs or CAS.",
        "records": [],
    })
    print(f"wrote final-80 v2: {len(final_gt)} cases; {correct} correct / {len(final_gt)-correct} incorrect")


if __name__ == "__main__":
    main()
