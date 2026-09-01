from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="三项评测与提交物")
    parser.add_argument(
        "cmd",
        choices=("build", "draft", "adjudicate", "jd", "resume", "match", "deliver", "report"),
    )
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--coverage", type=float, default=None)
    args, extras = parser.parse_known_args(argv)

    if args.cmd == "build":
        from app.eval.gold import main as build

        return build()
    if args.cmd == "draft":
        from app.eval.draft import main as draft

        return draft()
    if args.cmd == "adjudicate":
        from app.eval.adjudicate import main as adjudicate

        return adjudicate(extras)
    if args.cmd == "deliver":
        from app.eval.deliver import main as dump

        return dump()
    from app.eval.run import PASS, eval_jd, eval_match, eval_resume, out_dir, write_summary

    if args.cmd == "jd":
        return int(eval_jd(mock=args.mock)["f1"] < PASS)
    if args.cmd == "resume":
        return int(eval_resume(mock=args.mock)["f1"] < PASS)
    if args.cmd == "match":
        return int(eval_match(mock=args.mock)["f1"] < PASS)
    results = {}
    errors = {}
    lows = {}
    for name, fn in (("jd", eval_jd), ("resume", eval_resume), ("match", eval_match)):
        try:
            results[name] = fn(mock=args.mock)
            if results[name]["f1"] < PASS:
                lows[name] = f"F1 {results[name]['f1']:.3f} < {PASS:.2f}"
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
            (out_dir() / f"{name}.json").unlink(missing_ok=True)
    dest = write_summary(coverage=args.coverage, mock=args.mock, results=results, errors=errors, lows=lows)
    print(dest.read_text(encoding="utf-8"))
    return 1 if errors or lows else 0


if __name__ == "__main__":
    raise SystemExit(main())
