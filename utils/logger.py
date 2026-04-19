"""
Sistema de log do Media Rats - Artgen.
Registra mensagens no console, arquivo e emite sinais para a GUI.
"""

import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

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


class SensitiveFilter(logging.Filter):
    """Filtro que mascara credenciais sensíveis em mensagens de log.

    Evita que senhas ou tokens vazem para o arquivo de log ou console,
    mesmo se algum traceback ou mensagem de debug acabar incluindo os
    dados acidentalmente.
    """

    _PATTERNS = [
        (re.compile(r"(ADAPTA_SENHA\s*=\s*)\S+", re.I), r"\1***"),
        (re.compile(r"(password\s*[:=]\s*)\S+", re.I), r"\1***"),
        (re.compile(r"(senha\s*[:=]\s*)\S+", re.I), r"\1***"),
        (re.compile(r"(token\s*[:=]\s*)\S+", re.I), r"\1***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            for pat, repl in self._PATTERNS:
                msg = pat.sub(repl, msg)
            record.msg = msg
            record.args = ()
        except Exception:
            pass
        return True


def _setup_file_logger() -> logging.Logger:
    """Configura o logger de arquivo."""
    lg = logging.getLogger("artgen")
    if lg.handlers:
        return lg
    lg.setLevel(logging.DEBUG)
    fh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    fh.addFilter(SensitiveFilter())
    lg.addHandler(fh)
    lg.addFilter(SensitiveFilter())
    return lg


_file_logger = _setup_file_logger()


class ArtgenLogger(QObject):
    """Logger principal do Artgen baseado em sinais Qt.

    Emite ``mensagem_emitida(str, str)`` para cada mensagem de log.
    Conecte esse sinal ao painel de log da GUI via
    ``logger.mensagem_emitida.connect(self._log_panel.adicionar_mensagem)``.

    A ligação cross-thread é garantida pelo mecanismo de filas do Qt,
    eliminando o risco de chamadas diretas entre threads.
    """

    mensagem_emitida = pyqtSignal(str, str)

    def _emitir(self, mensagem: str, tipo: str) -> None:
        """Emite a mensagem para arquivo e sinal Qt.

        Args:
            mensagem: Texto da mensagem.
            tipo: Tipo da mensagem ('info'|'sucesso'|'aviso'|'erro').
        """
        ts = datetime.now().strftime("%H:%M:%S")
        linha = f"[{ts}] {mensagem}"
        nivel = _nivel_map.get(tipo, logging.INFO)
        _file_logger.log(nivel, mensagem)
        try:
            self.mensagem_emitida.emit(linha, tipo)
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
