from __future__ import annotations

import asyncio
import logging

from agentes.service import DynamicAgentService


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    service = DynamicAgentService()
    await service.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
