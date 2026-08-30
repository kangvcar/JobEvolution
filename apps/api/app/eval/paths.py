from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "CONTEXT.md").exists() and (parent / "data").is_dir():
            return parent
    return Path.cwd()


def eval_dir() -> Path:
    return repo_root() / "data" / "eval"


def out_dir() -> Path:
    path = eval_dir() / "out"
    path.mkdir(parents=True, exist_ok=True)
    return path
