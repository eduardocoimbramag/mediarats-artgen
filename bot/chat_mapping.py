"""
Persistência do mapeamento cliente -> URL do chat no Adapta.org.

Garante que cada cliente possua exatamente um chat canônico dentro do
projeto "Media Rats - ArtGen".

Critério de canonicidade:
    First-write-wins: o primeiro chat criado/vinculado para um cliente
    é preservado como canônico, pois contém o maior histórico acumulado.
    Para forçar substituição (ex: chat original deletado), use forcar_chat_url().

Persistência:
    Arquivo JSON local: <raiz_do_projeto>/chat_mapping.json
    Formato: { "CODIGO_CLIENTE": {"url": "...", "titulo": "...", "vinculado_em": "..."} }

Thread-safety:
    Todas as operações de leitura/escrita são protegidas por threading.Lock.
    Isso evita condições de corrida quando múltiplas threads tentam resolver
    o chat do mesmo cliente simultaneamente.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
MAPEAMENTO_PATH = BASE_DIR / "chat_mapping.json"

_lock = threading.Lock()


class ChatMapping:
    """Gerencia o mapeamento persistente código_cliente -> dados_do_chat.

    Args:
        caminho: Caminho do arquivo JSON de mapeamento.
                 Padrão: <raiz_do_projeto>/chat_mapping.json
    """

    def __init__(self, caminho: Path = MAPEAMENTO_PATH) -> None:
        self._caminho = caminho

    def _carregar(self) -> dict:
        """Lê o arquivo JSON de mapeamento.

        Returns:
            Dicionário com os vínculos atuais, ou {} se não existir/corrompido.
        """
        if not self._caminho.exists():
            return {}
        try:
            with open(self._caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if not isinstance(dados, dict):
                    return {}
                return dados
        except (json.JSONDecodeError, OSError):
            return {}

    def _salvar(self, dados: dict) -> None:
        """Persiste o dicionário de mapeamentos no arquivo JSON.

        Args:
            dados: Dicionário completo a salvar.
        """
        try:
            with open(self._caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get_chat_url(self, codigo_cliente: str) -> Optional[str]:
        """Retorna a URL do chat canônico vinculado ao cliente.

        Args:
            codigo_cliente: Código do cliente (ex: DUDE).

        Returns:
            URL do chat ou None se não houver vínculo.
        """
        with _lock:
            dados = self._carregar()
            entrada = dados.get(codigo_cliente.strip().upper())
            if isinstance(entrada, dict):
                return entrada.get("url")
            return None

    def get_titulo(self, codigo_cliente: str) -> Optional[str]:
        """Retorna o título do chat canônico do cliente.

        Args:
            codigo_cliente: Código do cliente.

        Returns:
            Título registrado ou None.
        """
        with _lock:
            dados = self._carregar()
            entrada = dados.get(codigo_cliente.strip().upper())
            if isinstance(entrada, dict):
                return entrada.get("titulo")
            return None

    def set_chat_url(self, codigo_cliente: str, chat_url: str, titulo: str = "") -> bool:
        """Persiste o vínculo cliente -> chat apenas se ainda não existir (first-write-wins).

        Evita sobrescrever chats antigos com histórico longo.
        Para forçar atualização, use forcar_chat_url().

        Args:
            codigo_cliente: Código do cliente.
            chat_url: URL completa do chat.
            titulo: Título do chat (para diagnóstico).

        Returns:
            True se o vínculo foi criado. False se já existia (não sobrescrito).
        """
        chave = codigo_cliente.strip().upper()
        with _lock:
            dados = self._carregar()
            if chave in dados:
                return False
            dados[chave] = {
                "url": chat_url,
                "titulo": titulo or chave,
                "vinculado_em": datetime.now().isoformat(),
                "atualizado_em": datetime.now().isoformat(),
            }
            self._salvar(dados)
            return True

    def forcar_chat_url(self, codigo_cliente: str, chat_url: str, titulo: str = "") -> None:
        """Força a atualização do vínculo cliente -> chat (sobrescreve o existente).

        Usar quando o chat canônico anterior foi deletado ou se tornou inválido.

        Args:
            codigo_cliente: Código do cliente.
            chat_url: Nova URL do chat canônico.
            titulo: Título do novo chat.
        """
        chave = codigo_cliente.strip().upper()
        with _lock:
            dados = self._carregar()
            entrada_anterior = dados.get(chave, {})
            dados[chave] = {
                "url": chat_url,
                "titulo": titulo or chave,
                "vinculado_em": entrada_anterior.get("vinculado_em", datetime.now().isoformat()),
                "atualizado_em": datetime.now().isoformat(),
                "url_anterior": entrada_anterior.get("url", ""),
            }
            self._salvar(dados)

    def remover(self, codigo_cliente: str) -> None:
        """Remove o vínculo de um cliente (ex: antes de criar novo após falha).

        Args:
            codigo_cliente: Código do cliente.
        """
        chave = codigo_cliente.strip().upper()
        with _lock:
            dados = self._carregar()
            dados.pop(chave, None)
            self._salvar(dados)

    def listar(self) -> dict:
        """Retorna cópia de todos os vínculos atuais.

        Returns:
            Dicionário {codigo_cliente: {url, titulo, vinculado_em, ...}}.
        """
        with _lock:
            return dict(self._carregar())

    def tem_vinculo(self, codigo_cliente: str) -> bool:
        """Verifica se existe vínculo para o cliente.

        Args:
            codigo_cliente: Código do cliente.

        Returns:
            True se existir vínculo registrado.
        """
        with _lock:
            dados = self._carregar()
            return codigo_cliente.strip().upper() in dados


chat_mapping = ChatMapping()
