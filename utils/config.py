"""
Módulo de configuração do Media Rats - Artgen.
Carrega variáveis de ambiente (.env) e preferências (settings.json).
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

_env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=_env_path)

_SETTINGS_PATH = BASE_DIR / "settings.json"


def _parse_bool(valor: str, padrao: bool = False) -> bool:
    """Converte string de variável de ambiente para bool de forma robusta.

    Valores considerados True: 'true', '1', 'yes', 'on', 's', 'sim'.
    Tudo mais (incluindo 'false', '0', 'no', 'off') é False.
    Isso evita o bug clássico de 'false' (string não-vazia) ser truthy em Python.

    Args:
        valor: String lida do env (ou "" se variável não definida).
        padrao: Valor usado quando ``valor`` é vazio/None.

    Returns:
        bool resultante.
    """
    if not valor:
        return padrao
    return valor.strip().lower() in ("true", "1", "yes", "on", "s", "sim")


class Config:
    """Acessa as configurações do projeto a partir do .env e settings.json."""

    URL_ADAPTA: str = os.getenv("URL_ADAPTA", "https://www.adapta.org")
    CAMINHO_PLANILHA: str = os.getenv(
        "CAMINHO_PLANILHA", "./planilha/planilha-artgenmediarats.xlsx"
    )
    CAMINHO_OUTPUT: str = os.getenv("CAMINHO_OUTPUT", "./output")
    TIMEOUT_GERADOR: int = int(os.getenv("TIMEOUT_GERADOR", "60"))
    MODO_HEADLESS: bool = _parse_bool(os.getenv("MODO_HEADLESS", ""), padrao=False)
    FECHAR_NAVEGADOR_APOS_CONCLUSAO: bool = _parse_bool(
        os.getenv("FECHAR_NAVEGADOR_APOS_CONCLUSAO", ""), padrao=False
    )
    IDIOMA_LOG: str = os.getenv("IDIOMA_LOG", "pt-BR")
    ADAPTA_EMAIL: str = os.getenv("ADAPTA_EMAIL", "")
    ADAPTA_SENHA: str = os.getenv("ADAPTA_SENHA", "")
    NOME_PASTA_PROJETO: str = os.getenv("NOME_PASTA_PROJETO", "Media Rats - ArtGen")

    @classmethod
    def caminho_planilha_abs(cls) -> Path:
        """Retorna o caminho absoluto da planilha."""
        p = Path(cls.CAMINHO_PLANILHA)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p.resolve()

    @classmethod
    def caminho_output_abs(cls) -> Path:
        """Retorna o caminho absoluto da pasta de output."""
        p = Path(cls.CAMINHO_OUTPUT)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    @classmethod
    def recarregar(cls) -> None:
        """Recarrega as variáveis de ambiente do arquivo .env."""
        load_dotenv(dotenv_path=_env_path, override=True)
        cls.URL_ADAPTA = os.getenv("URL_ADAPTA", "https://www.adapta.org")
        cls.CAMINHO_PLANILHA = os.getenv(
            "CAMINHO_PLANILHA", "./planilha/planilha-artgenmediarats.xlsx"
        )
        cls.CAMINHO_OUTPUT = os.getenv("CAMINHO_OUTPUT", "./output")
        cls.TIMEOUT_GERADOR = int(os.getenv("TIMEOUT_GERADOR", "60"))
        cls.MODO_HEADLESS = _parse_bool(os.getenv("MODO_HEADLESS", ""), padrao=False)
        cls.FECHAR_NAVEGADOR_APOS_CONCLUSAO = _parse_bool(
            os.getenv("FECHAR_NAVEGADOR_APOS_CONCLUSAO", ""), padrao=False
        )
        cls.IDIOMA_LOG = os.getenv("IDIOMA_LOG", "pt-BR")
        cls.ADAPTA_EMAIL = os.getenv("ADAPTA_EMAIL", "")
        cls.ADAPTA_SENHA = os.getenv("ADAPTA_SENHA", "")
        cls.NOME_PASTA_PROJETO = os.getenv("NOME_PASTA_PROJETO", "Media Rats - ArtGen")

    @classmethod
    def salvar_env(cls, dados: dict) -> None:
        """Persiste as configurações no arquivo .env, preservando chaves não fornecidas.

        Args:
            dados: Dicionário com chaves/valores a gravar (merge com existentes).
        """
        existentes: dict = {}
        if _env_path.exists():
            with open(_env_path, "r", encoding="utf-8") as f:
                for linha in f:
                    linha = linha.strip()
                    if "=" in linha and not linha.startswith("#"):
                        k, _, v = linha.partition("=")
                        existentes[k.strip()] = v.strip()
        existentes.update(dados)
        linhas = [f"{k}={v}\n" for k, v in existentes.items()]
        with open(_env_path, "w", encoding="utf-8") as f:
            f.writelines(linhas)
        cls.recarregar()


class Settings:
    """Gerencia preferências persistidas em settings.json."""

    _defaults: dict = {
        "ultima_solicitacao": None,
        "janela_largura": 1280,
        "janela_altura": 800,
        "janela_x": 100,
        "janela_y": 100,
        "splitter_posicao": [600, 400],
    }

    def __init__(self) -> None:
        self._dados: dict = dict(self._defaults)
        self._carregar()

    def _carregar(self) -> None:
        """Carrega preferências do arquivo settings.json."""
        if _SETTINGS_PATH.exists():
            try:
                with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    self._dados.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                self._dados = dict(self._defaults)

    def salvar(self) -> None:
        """Persiste as preferências no arquivo settings.json."""
        try:
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._dados, f, indent=4, ensure_ascii=False)
        except OSError:
            pass

    def get(self, chave: str, padrao=None):
        """Retorna um valor de preferência.

        Args:
            chave: Nome da chave.
            padrao: Valor padrão se não encontrado.
        """
        return self._dados.get(chave, padrao)

    def set(self, chave: str, valor) -> None:
        """Define um valor de preferência.

        Args:
            chave: Nome da chave.
            valor: Valor a persistir.
        """
        self._dados[chave] = valor


settings = Settings()
