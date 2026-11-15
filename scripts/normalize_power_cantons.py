"""Normalize canton names in the NASA POWER CSV to match geoBoundaries ADM2 names.

Only the first column is rewritten (underscores -> spaces); every other byte of
each line is kept as-is so no numeric value is reformatted. Idempotent.
"""
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "nasa_power_guanacaste_daily_2012_2025.csv"


def main() -> None:
    lines = PATH.read_text(encoding="utf-8").split("\n")
    out = [lines[0]]
    for line in lines[1:]:
        if not line:
            out.append(line)
            continue
        name, rest = line.split(",", 1)
        out.append(f"{name.replace('_', ' ')},{rest}")
    PATH.write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
