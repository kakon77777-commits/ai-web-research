"""Thin CLI wrapper around crawler.research.diverge() for cross-process use
from IPMCS (unbounded-axiom/scripts/ipmcs/). Reuses the real, tested
divergence implementation directly -- not a reimplementation. Reads LLM
config from .env (LLM_PROVIDER + provider-specific keys/credentials),
already configured in this repo.

Usage: python diverge_cli.py "<seed query>"
Output: one JSON object on stdout: {"seed": ..., "branches": {category: [queries]}}
"""
import asyncio
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from crawler.llm import default_config_from_env
from crawler.research import diverge


async def main():
    if len(sys.argv) < 2:
        print("usage: python diverge_cli.py \"<seed query>\"", file=sys.stderr)
        sys.exit(1)
    seed = sys.argv[1]
    llm_config = default_config_from_env()
    result = await diverge(seed, llm_config)
    print(json.dumps({"seed": result.seed, "branches": result.branches}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
