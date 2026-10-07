"""M7: the README tool table is generated from list_tools() and must be current."""

import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_tool_docs", ROOT / "scripts/gen_tool_docs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_tool_table_is_current():
    gen = load_generator()
    always = {t.name for t in asyncio.run(gen.listed_tools(writes=False))}
    tools = asyncio.run(gen.listed_tools())
    text = gen.README.read_text(encoding="utf-8")
    assert gen.render(text, gen.table(tools, always)) == text, (
        "README tool table is stale: run python scripts/gen_tool_docs.py"
    )
    assert f"lists {len(always)}\ntools" in text


def test_single_version_source():
    from nvidia_mcp import __version__

    pyproject = (ROOT / "pyproject.toml").read_text()
    assert (
        'dynamic = ["version"]' in pyproject and 'path = "src/nvidia_mcp/__init__.py"' in pyproject
    )
    assert __version__.count(".") == 2
