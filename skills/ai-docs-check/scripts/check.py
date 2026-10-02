#!/usr/bin/env python3
"""Independent docctl entry point backed by this Skill's shared resources."""
from pathlib import Path
import runpy
import sys


def cli():
    tool = Path(__file__).resolve().parents[1] / "assets/templates/docs/_tools/docctl.py"
    if not tool.is_file():
        print("缺少公共资源；请恢复完整的 ai-docs-check Skill（含 assets/templates）", file=sys.stderr)
        return 2
    sys.dont_write_bytecode = True
    runpy.run_path(str(tool), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
