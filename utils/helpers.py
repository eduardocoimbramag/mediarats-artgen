"""
Funções utilitárias diversas para o Media Rats - Artgen.
"""

import re
import os
import time
import socket
import shutil
from pathlib import Path
from typing import Optional


def validar_protocolo(protocolo: str) -> bool:
    """Valida o formato do protocolo (ex: DUDE#1, MR#12).

    Args:
        protocolo: String do protocolo a validar.

    Returns:
        True se o formato for válido.
    """
    pattern = r"^[A-Za-z]{2,4}#\d+$"
    return bool(re.match(pattern, protocolo))


def gerar_protocolo(codigo_cliente: str, numero: int) -> str:
    """Gera um protocolo no formato CODIGO#NUMERO.

    Args:
        codigo_cliente: Código do cliente (2-4 letras).
        numero: Número sequencial da solicitação.

    Returns:
        Protocolo formatado (ex: DUDE#1).
    """
    return f"{codigo_cliente.upper()}#{numero}"


def criar_pasta_output(pasta_output_base: Path, protocolo: str) -> Path:
    """Cria a pasta de output para um protocolo específico.

    Args:
        pasta_output_base: Caminho base da pasta output.
        protocolo: Protocolo da solicitação (ex: DUDE#1).

    Returns:
        Path para a pasta criada.
    """
    nome_pasta = protocolo.replace("#", "_")
    pasta = pasta_output_base / nome_pasta
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def limpar_pasta(pasta: Path) -> None:
    """Remove todo o conteúdo de uma pasta mantendo a pasta em si.

    Args:
        pasta: Caminho da pasta a limpar.
    """
    for item in pasta.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def nome_arquivo_arte(protocolo: str, numero: int) -> str:
    """Gera o nome de arquivo para uma arte gerada.

    Args:
        protocolo: Protocolo da solicitação (ex: DUDE#1).
        numero: Número sequencial da arte (1-10).

    Returns:
        Nome do arquivo (ex: DUDE#1_001.jpg).
    """
    return f"{protocolo}_{numero:03d}.jpg"


def verificar_internet(host: str = "8.8.8.8", porta: int = 53, timeout: int = 5) -> bool:
    """Verifica se há conexão com a internet.

    Args:
        host: Host a testar (padrão: Google DNS).
        porta: Porta a usar.
        timeout: Tempo limite em segundos.

    Returns:
        True se houver conexão.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(timeout)
        s.connect((host, porta))
        return True
    except socket.error:
        return False
    finally:
        s.close()


def verificar_arquivo_aberto(caminho: Path) -> bool:
    """Tenta detectar se um arquivo Excel está aberto em outro processo.

    Args:
        caminho: Caminho do arquivo a verificar.

    Returns:
        True se o arquivo parecer estar em uso.
    """
    lock_path = caminho.parent / f"~${caminho.name}"
    return lock_path.exists()


def backoff_espera(tentativa: int, base: float = 2.0, maximo: float = 30.0) -> float:
    """Calcula o tempo de espera com backoff exponencial.

    Args:
        tentativa: Número da tentativa (começa em 1).
        base: Base do expoente.
        maximo: Tempo máximo de espera em segundos.

    Returns:
        Segundos a aguardar.
    """
    espera = min(base ** tentativa, maximo)
    return espera


def truncar_texto(texto: str, max_len: int = 60) -> str:
    """Trunca texto para exibição em logs.

    Args:
        texto: Texto original.
        max_len: Tamanho máximo.

    Returns:
        Texto truncado com '...' se necessário.
    """
    if len(texto) <= max_len:
        return texto
    return texto[:max_len] + "..."


def formatar_duracao(segundos: float) -> str:
    """Formata duração em segundos para string legível.

    Args:
        segundos: Tempo em segundos.

    Returns:
        String formatada (ex: '2m 30s').
    """
    s = int(segundos)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def obter_versao() -> str:
    """Lê a versão do programa a partir de version.txt.

    Returns:
        String com a versão (ex: '1.0.0').
    """
    versao_path = Path(__file__).resolve().parent.parent / "version.txt"
    try:
        return versao_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "1.0.0"
