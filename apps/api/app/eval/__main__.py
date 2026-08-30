from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="三项评测与提交物")
    parser.add_argument(
        "cmd",
        choices=("build", "jd", "resume", "match", "deliver", "report"),
    )
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--coverage", type=float, default=None)
    args = parser.parse_args(argv)

    if args.cmd == "build":
        from app.eval.gold import main as build

        return build()
    if args.cmd == "deliver":
        from app.eval.deliver import main as dump

        return dump()
    from app.eval.run import eval_jd, eval_match, eval_resume, write_summary

    if args.cmd == "jd":
        eval_jd(mock=args.mock)
        return 0
    if args.cmd == "resume":
        eval_resume(mock=args.mock)
        return 0
    if args.cmd == "match":
        eval_match(mock=args.mock)
        return 0
    eval_jd(mock=args.mock)
    eval_resume(mock=args.mock)
    eval_match(mock=args.mock)
    dest = write_summary(coverage=args.coverage, mock=args.mock)
    print(dest.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
