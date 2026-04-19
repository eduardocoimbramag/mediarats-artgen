"""
Testes unitários para utils/prompt_composer.py.
"""

import pytest
from utils.prompt_composer import (
    compor_prompt_arte,
    PerfilCliente,
    _normalizar_texto,
    _limpar_variacoes,
)


class TestNormalizarTexto:
    def test_remove_espacos_duplos(self):
        assert _normalizar_texto("texto  com  espacos") == "texto com espacos"

    def test_strip_bordas(self):
        assert _normalizar_texto("  abc  ") == "abc"

    def test_vazio_retorna_vazio(self):
        assert _normalizar_texto("") == ""

    def test_preserva_texto_normal(self):
        assert _normalizar_texto("arte minimalista") == "arte minimalista"


class TestLimparVariacoes:
    def test_deduplica_case_insensitive(self):
        resultado = _limpar_variacoes(["Arte", "arte", "outro"])
        assert resultado == ["Arte", "outro"]

    def test_remove_vazios(self):
        resultado = _limpar_variacoes(["a", "", "  ", "b"])
        assert resultado == ["a", "b"]

    def test_exclui_por_indice(self):
        resultado = _limpar_variacoes(["a", "b", "c"], excluir_indice=1)
        assert "b" not in resultado
        assert "a" in resultado
        assert "c" in resultado

    def test_limita_a_max_variacoes(self):
        variacoes = [f"item{i}" for i in range(20)]
        resultado = _limpar_variacoes(variacoes)
        assert len(resultado) <= 10

    def test_lista_vazia(self):
        assert _limpar_variacoes([]) == []


class TestPerfilCliente:
    def test_vazio_quando_padrao(self):
        assert PerfilCliente().vazio is True

    def test_nao_vazio_com_nicho(self):
        assert PerfilCliente(nicho="Moda").vazio is False

    def test_nao_vazio_com_estilo_visual(self):
        assert PerfilCliente(estilo_visual="Minimalista").vazio is False

    def test_nao_vazio_com_cor(self):
        assert PerfilCliente(cor_primaria="#FF0000").vazio is False

    def test_nome_nao_afeta_vazio(self):
        assert PerfilCliente(nome="João", codigo="MR").vazio is True


class TestComporPromptArte:
    def test_prompt_simples_presente(self):
        resultado = compor_prompt_arte(prompt_principal="Crie uma arte minimalista")
        assert "Crie uma arte minimalista" in resultado

    def test_sem_dados_retorna_fallback(self):
        resultado = compor_prompt_arte()
        assert resultado == "(prompt vazio)"

    def test_tema_incluido(self):
        resultado = compor_prompt_arte(
            prompt_principal="Arte abstrata",
            tema="Verão 2025",
        )
        assert "Verão 2025" in resultado
        assert "Arte abstrata" in resultado

    def test_perfil_presente_no_resultado(self):
        perfil = PerfilCliente(nome="Marca X", nicho="Moda")
        resultado = compor_prompt_arte(
            perfil=perfil,
            prompt_principal="Arte minimalista",
        )
        assert "Marca X" in resultado
        assert "Moda" in resultado

    def test_numero_arte_no_cabecalho(self):
        resultado = compor_prompt_arte(
            prompt_principal="Arte",
            numero_arte=2,
            total_artes=5,
        )
        assert "2/5" in resultado

    def test_prompt_principal_nao_duplicado_nas_variacoes(self):
        resultado = compor_prompt_arte(
            prompt_principal="Arte principal",
            variacoes=["v1", "v2", "Arte principal"],
            indice_prompt_principal=2,
        )
        assert resultado.count("Arte principal") == 1

    def test_tema_sozinho_retorna_tema(self):
        resultado = compor_prompt_arte(tema="Carnaval 2025")
        assert "Carnaval 2025" in resultado

    def test_perfil_vazio_nao_gera_secao_perfil(self):
        resultado = compor_prompt_arte(
            perfil=PerfilCliente(),
            prompt_principal="Arte",
        )
        assert "PERFIL DO CLIENTE" not in resultado

    def test_variacoes_aparecem_na_secao_correta(self):
        resultado = compor_prompt_arte(
            prompt_principal="Arte principal",
            variacoes=["Variação 1", "Variação 2"],
        )
        assert "Variação 1" in resultado
        assert "Variação 2" in resultado

    def test_retorna_string_nao_vazia(self):
        resultado = compor_prompt_arte(prompt_principal="Teste")
        assert isinstance(resultado, str)
        assert len(resultado) > 0
