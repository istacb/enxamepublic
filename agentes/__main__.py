"""Ponto de entrada do agente Enxame.
Usage: ENXAME_ROOT=/path ENXAME_CONFIG_DIR=/path/enxame NODE_ID=ag-1 python3 -m agentes
"""
import asyncio
import os
import sys
import logging

sys.path.insert(0, os.environ.get('ENXAME_ROOT', '..'))
logging.basicConfig(level=logging.INFO)
from agentes.service import DynamicAgentService

async def main():
    await DynamicAgentService().run_forever()

asyncio.run(main())
