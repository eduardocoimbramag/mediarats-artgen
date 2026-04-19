"""
Configuração global de testes do Media Rats - Artgen.
Garante que o root do projeto esteja no sys.path para todos os testes.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
