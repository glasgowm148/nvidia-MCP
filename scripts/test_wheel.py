"""Install the release wheel in a fresh venv and run the isolated local smoke check."""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--mcp-version", help="Exercise a specific supported MCP SDK (e.g. 1.28.*)")
    parser.add_argument(
        "--manager-zip", type=Path, help="Also verify this generated Manager add-on"
    )
    args = parser.parse_args()
    version = re.search(
        r'^__version__ = "([^"]+)"$', (ROOT / "src/nvidia_mcp/__init__.py").read_text(), re.M
    ).group(1)
    wheels = list(args.dist.glob("*-" + version + "-*.whl"))
    if len(wheels) != 1:
        raise ValueError("Build exactly one current-version wheel first")
    with tempfile.TemporaryDirectory() as directory:
        environment = Path(directory) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--quiet", str(wheels[0])], check=True)
        if args.mcp_version:
            subprocess.run(
                [str(python), "-m", "pip", "install", "--quiet", "mcp==" + args.mcp_version],
                check=True,
            )
        subprocess.run(
            [str(python), "-I", str(ROOT / "scripts/smoke_install.py")], cwd=directory, check=True
        )
        if args.manager_zip:
            subprocess.run(
                [
                    str(python),
                    "-I",
                    str(ROOT / "scripts/test_manager_interface.py"),
                    "--wheel",
                    str(wheels[0].resolve()),
                    "--manager-zip",
                    str(args.manager_zip.resolve()),
                ],
                cwd=directory,
                check=True,
            )


if __name__ == "__main__":
    main()
