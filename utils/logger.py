"""
Sistema de log do Media Rats - Artgen.
Registra mensagens no console, arquivo e emite sinais para a GUI.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "artgen.log"

_nivel_map = {
    "info": logging.INFO,
    "sucesso": logging.INFO,
    "aviso": logging.WARNING,
    "erro": logging.ERROR,
    "debug": logging.DEBUG,
}


def _setup_file_logger() -> logging.Logger:
    """Configura o logger de arquivo."""
    logger = logging.getLogger("artgen")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


_file_logger = _setup_file_logger()


class ArtgenLogger:
    """Logger principal do Artgen com suporte a callbacks de GUI.

    Attributes:
        _callback: Função chamada ao emitir cada mensagem (opcional).
    """

    def __init__(self) -> None:
        self._callback: Optional[Callable[[str, str], None]] = None

    def definir_callback(self, fn: Callable[[str, str], None]) -> None:
        """Define callback para envio de mensagens à GUI.

        Args:
            fn: Função que recebe (mensagem, tipo) onde tipo é
                'info'|'sucesso'|'aviso'|'erro'.
        """
        self._callback = fn

    def _emitir(self, mensagem: str, tipo: str) -> None:
        """Emite a mensagem para arquivo e callback de GUI.

        Args:
            mensagem: Texto da mensagem.
            tipo: Tipo da mensagem.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        linha = f"[{ts}] {mensagem}"
        nivel = _nivel_map.get(tipo, logging.INFO)
        _file_logger.log(nivel, mensagem)
        if self._callback:
            try:
                self._callback(linha, tipo)
            except Exception:
                pass

    def info(self, mensagem: str) -> None:
        """Log de informação.

        Args:
            mensagem: Texto informativo.
        """
        self._emitir(mensagem, "info")

    def sucesso(self, mensagem: str) -> None:
        """Log de sucesso.

        Args:
            mensagem: Texto de sucesso.
        """
        self._emitir(mensagem, "sucesso")

    def aviso(self, mensagem: str) -> None:
        """Log de aviso.

        Args:
            mensagem: Texto de aviso.
        """
        self._emitir(mensagem, "aviso")

    def erro(self, mensagem: str) -> None:
        """Log de erro.

        Args:
            mensagem: Texto de erro.
        """
        self._emitir(mensagem, "erro")

    def debug(self, mensagem: str) -> None:
        """Log de debug.

        Args:
            mensagem: Texto de debug.
        """
        self._emitir(mensagem, "info")


logger = ArtgenLogger()
