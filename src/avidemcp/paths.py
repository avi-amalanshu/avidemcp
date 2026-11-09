"""Output path policy: explicit outputs are honoured, derived ones never clobber anything."""

from pathlib import Path


def source(path: str) -> Path:
    """Resolve an input path, failing early if it does not exist."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"no such file: {p}")
    return p


def target(src: Path, out: str | None, tag: str, ext: str | None = None) -> Path:
    """Output file for an op on src.

    out given:   that path (parent dirs created); it must differ from src.
    out omitted: <stem>.<tag><ext> beside src, numbered .2, .3, ... until unused.
    """
    if out:
        o = Path(out).expanduser().resolve()
        if o == src:
            raise ValueError("output must differ from the input")
        o.parent.mkdir(parents=True, exist_ok=True)
        return o
    ext = ext or src.suffix
    o, n = src.with_name(f"{src.stem}.{tag}{ext}"), 2
    while o.exists():
        o, n = src.with_name(f"{src.stem}.{tag}.{n}{ext}"), n + 1
    return o
