"""Chấm bước tóm tắt trên golden dataset, ba nhánh, cùng một bộ tiêu chí.

    python -m scripts.eval_summary_arms                 # cả ba nhánh
    python -m scripts.eval_summary_arms --arms rule     # chỉ nhánh không tốn tiền
    python -m scripts.eval_summary_arms --show          # in luôn bản tóm tắt

Ba nhánh, mỗi nhánh gọi ĐÚNG hàm production, không viết lại logic để chấm:

* rule   — `_mock_reduce`: nối evidence_quote kèm dòng nguồn. Không gọi LLM.
* llm    — cùng prompt của `_reduce_one` nhưng BỎ cổng `ground_candidate`.
* hybrid — bản đang chạy thật: LLM, trượt cổng `ground_candidate` thì rơi về
           rule; cụm toàn Jira đi thẳng rule.

Nhánh llm cố tình bỏ cổng chứ không phải "chưa làm": có vậy mới đo được cổng
đó cứu hay giết bao nhiêu case.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.agents.pipeline.nodes.reduce import (  # noqa: E402
    _grounding_evidence,
    _is_jira_only_cluster,
    _mock_reduce,
    _quote_lines,
    _system_prompt,
)
from src.guardrail.output import ground_candidate  # noqa: E402
from src.services.summary_scoring import CaseScore, aggregate, score_case  # noqa: E402

CASES_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "eval"
    / "golden_dataset"
    / "summary"
    / "summary_cases.json"
)


def _cluster(case: dict) -> dict:
    return {"cluster_key": case["id"], "title": case["title"], "items": case["items"]}


async def _run_llm_only(llm, case: dict) -> str:
    """Cùng prompt production, không qua cổng grounding."""
    cluster = _cluster(case)
    response = await llm.ainvoke(
        [
            {"role": "system", "content": _system_prompt(case.get("language", "vi"))},
            {
                "role": "user",
                "content": f"Tieu de: {cluster['title']}\nTrich dan:\n{_quote_lines(cluster)}",
            },
        ]
    )
    return response.content


async def run_round(cases: list[dict], arms: list[str]) -> dict[str, list[CaseScore]]:
    """Mot luot: goi LLM DUNG MOT LAN moi case, roi hau xu ly ra tung nhanh.

    Truoc day moi nhanh goi LLM rieng, nen chenh lech giua cac nhanh lan ca
    nhieu lay mau cua model. Dung chung mot ban sinh thi khac biet con lai
    dung la khac biet cua cong grounding — so sanh theo cap.
    """
    llm = None
    if arms != ["rule"]:
        from src.services.llm import get_llm

        llm = get_llm()

    scores: dict[str, list[CaseScore]] = {arm: [] for arm in arms}
    for case in cases:
        cluster = _cluster(case)
        rule_output = _mock_reduce(cluster)
        raw = ""
        if llm is not None and not _is_jira_only_cluster(cluster):
            try:
                raw = await _run_llm_only(llm, case)
            except Exception as error:  # noqa: BLE001 — het credit khong duoc giet ca luot cham
                print(f"  [{case['id']}] loi goi LLM: {error}", file=sys.stderr)
        elif llm is not None:
            # Cum toan Jira: production co y di duong rule, khong goi LLM.
            raw = rule_output

        evidence = _grounding_evidence(cluster)
        for arm in arms:
            if arm == "rule":
                output = rule_output
            elif arm == "llm":
                output = raw
            elif arm == "hybrid":
                gated = ground_candidate(raw, evidence, None).status == "grounded" if raw else False
                output = raw if gated else rule_output
            else:
                raise SystemExit(f"nhanh khong biet: {arm}")
            scores[arm].append(score_case(case, output))
    return scores


def _print_arm(arm: str, scores: list[CaseScore], show: bool) -> None:
    stats = aggregate(scores)
    print(f"\n=== {arm} ===")
    print(
        "  attribution {attribution:.2f}  coverage {coverage:.2f}  faithful {faithful:.2f}"
        "  language {language:.2f}  paraphrase {paraphrased:.2f}  => PASS {passed:.2f}".format(
            **stats
        )
    )
    for score in scores:
        if score.passed and not show:
            continue
        flags = "".join(
            [
                "" if score.attribution else "A",
                "" if score.coverage else "C",
                "" if score.faithful else "F",
                "" if score.language_ok else "L",
            ]
        )
        mark = "ok" if score.passed else f"FAIL[{flags}]"
        print(f"  {mark:12} {score.case_id}")
        if show:
            print(f"               {score.output[:220]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", nargs="*", default=["rule", "llm", "hybrid"])
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--json", dest="json_out", default="")
    # Cham lai tu output da luu: sua tieu chi cham khong phai tra tien goi
    # LLM lai, va ba nhanh van duoc cham tren dung mot bo output.
    parser.add_argument("--rescore", default="")
    # LLM khong tat dinh: mot luot 12 case dao dong du de dao nguoc thu hang.
    # Lap nhieu luot roi lay trung binh + do lech thi ket luan moi dung nghia.
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    print(f"{len(cases)} case tu {CASES_PATH.name}")

    # get_llm() doc setting luc goi; mock_llm bat se lam nhanh llm/hybrid vo nghia.
    if os.getenv("MOCK_LLM", "").lower() in {"1", "true"} and args.arms != ["rule"]:
        print("MOCK_LLM dang bat — tat de cham nhanh llm/hybrid that.", file=sys.stderr)
        sys.exit(2)

    results: dict[str, list[CaseScore]] = {}
    if args.rescore:
        by_id = {case["id"]: case for case in cases}
        saved = json.loads(pathlib.Path(args.rescore).read_text(encoding="utf-8"))
        for arm, data in saved.items():
            results[arm] = [
                score_case(by_id[row["id"]], row["output"]) for row in data["cases"]
            ]
            _print_arm(arm, results[arm], args.show)
    else:
        # Mot event loop cho ca ba nhanh: get_llm() bi lru_cache nen client HTTP
        # dinh vao loop tao ra no. Moi nhanh mot asyncio.run() thi loi ngay o
        # lan goi dau cua nhanh thu hai, va bi cham thanh diem kem.
        rounds: dict[str, list[list[CaseScore]]] = {arm: [] for arm in args.arms}

        async def run_all() -> None:
            for _ in range(args.repeat):
                round_scores = await run_round(cases, args.arms)
                for arm in args.arms:
                    rounds[arm].append(round_scores[arm])

        asyncio.run(run_all())
        for arm in args.arms:
            results[arm] = rounds[arm][-1]
            _print_arm(arm, results[arm], args.show)
            if args.repeat > 1:
                rates = [aggregate(r)["passed"] for r in rounds[arm]]
                spread = f"{min(rates):.2f}-{max(rates):.2f}"
                print(
                    f"  qua {args.repeat} luot: PASS trung binh "
                    f"{sum(rates) / len(rates):.2f}  (bien do {spread})"
                )
                # Case nao truot O MOI LUOT moi la loi that; truot rai rac la nhieu.
                always = [
                    score.case_id
                    for score in rounds[arm][0]
                    if all(
                        not next(s for s in r if s.case_id == score.case_id).passed
                        for r in rounds[arm]
                    )
                ]
                print(f"  truot moi luot: {', '.join(always) or 'khong co'}")

    print("\n--- tong ket ---")
    for arm, scores in results.items():
        stats = aggregate(scores)
        print(f"  {arm:8} PASS {stats['passed']:.2f}  ({sum(s.passed for s in scores)}/{len(scores)})")

    if args.json_out:
        pathlib.Path(args.json_out).write_text(
            json.dumps(
                {
                    arm: {
                        "aggregate": aggregate(scores),
                        "cases": [
                            {
                                "id": s.case_id,
                                "passed": s.passed,
                                "attribution": s.attribution,
                                "coverage": s.coverage,
                                "faithful": s.faithful,
                                "language": s.language_ok,
                                "paraphrased": s.paraphrased,
                                "output": s.output,
                            }
                            for s in scores
                        ],
                    }
                    for arm, scores in results.items()
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
