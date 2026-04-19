"""
Testes unitários para utils/config.py.
"""

import pytest
from utils.config import _parse_bool, Config, Settings


class TestParseBool:
    @pytest.mark.parametrize("valor", ["true", "True", "TRUE", "1", "yes", "on", "s", "sim"])
    def test_valores_verdadeiros(self, valor):
        assert _parse_bool(valor) is True

    @pytest.mark.parametrize("valor", ["false", "False", "FALSE", "0", "no", "off", "n"])
    def test_valores_falsos(self, valor):
        assert _parse_bool(valor) is False

    def test_vazio_retorna_padrao_false(self):
        assert _parse_bool("") is False

    def test_none_retorna_padrao_false(self):
        assert _parse_bool(None) is False

    def test_vazio_com_padrao_true(self):
        assert _parse_bool("", padrao=True) is True

    def test_string_com_espacos(self):
        assert _parse_bool("  true  ") is True


class TestConfigDefaults:
    def test_url_adapta_tem_valor(self):
        assert isinstance(Config.URL_ADAPTA, str)
        assert len(Config.URL_ADAPTA) > 0

    def test_url_adapta_default(self):
        import os
        if not os.getenv("URL_ADAPTA"):
            assert Config.URL_ADAPTA == "https://www.adapta.org"

    def test_timeout_e_inteiro_positivo(self):
        assert isinstance(Config.TIMEOUT_GERADOR, int)
        assert Config.TIMEOUT_GERADOR > 0

    def test_modo_headless_e_bool(self):
        assert isinstance(Config.MODO_HEADLESS, bool)

    def test_fechar_navegador_e_bool(self):
        assert isinstance(Config.FECHAR_NAVEGADOR_APOS_CONCLUSAO, bool)

    def test_caminho_planilha_tem_valor(self):
        assert isinstance(Config.CAMINHO_PLANILHA, str)
        assert len(Config.CAMINHO_PLANILHA) > 0

    def test_caminho_output_tem_valor(self):
        assert isinstance(Config.CAMINHO_OUTPUT, str)
        assert len(Config.CAMINHO_OUTPUT) > 0


class TestSettings:
    def test_get_chave_inexistente_retorna_padrao(self):
        s = Settings()
        assert s.get("chave_que_nao_existe") is None

    def test_get_com_padrao_customizado(self):
        s = Settings()
        assert s.get("chave_inexistente", 42) == 42

    def test_set_e_get(self):
        s = Settings()
        s.set("chave_teste", "valor_teste")
        assert s.get("chave_teste") == "valor_teste"

    def test_defaults_janela(self):
        s = Settings()
        assert isinstance(s.get("janela_largura"), int)
        assert isinstance(s.get("janela_altura"), int)
        assert s.get("janela_largura") > 0
        assert s.get("janela_altura") > 0
