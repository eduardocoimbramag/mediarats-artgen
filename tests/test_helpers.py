"""
Testes unitários para utils/helpers.py.
"""

import pytest
from utils.helpers import (
    validar_protocolo,
    gerar_protocolo,
    nome_arquivo_arte,
    truncar_texto,
    backoff_espera,
    formatar_duracao,
)


class TestValidarProtocolo:
    def test_valido_dois_chars(self):
        assert validar_protocolo("MR#1") is True

    def test_valido_tres_chars(self):
        assert validar_protocolo("MRT#5") is True

    def test_valido_quatro_chars(self):
        assert validar_protocolo("DUDE#99") is True

    def test_valido_numero_grande(self):
        assert validar_protocolo("MR#100") is True

    def test_invalido_sem_hash(self):
        assert validar_protocolo("DUDE1") is False

    def test_invalido_codigo_um_char(self):
        assert validar_protocolo("D#1") is False

    def test_invalido_codigo_cinco_chars(self):
        assert validar_protocolo("MEDIARATS#1") is False

    def test_invalido_numero_ausente(self):
        assert validar_protocolo("DUDE#") is False

    def test_invalido_vazio(self):
        assert validar_protocolo("") is False

    def test_invalido_letras_no_numero(self):
        assert validar_protocolo("DUDE#1A") is False


class TestGerarProtocolo:
    def test_formata_corretamente(self):
        assert gerar_protocolo("dude", 1) == "DUDE#1"

    def test_uppercase_automatico(self):
        assert gerar_protocolo("mr", 12) == "MR#12"

    def test_numero_zero(self):
        assert gerar_protocolo("MR", 0) == "MR#0"


class TestNomeArquivoArte:
    def test_formato_padrao(self):
        assert nome_arquivo_arte("DUDE#1", 1) == "DUDE#1_001.jpg"

    def test_numero_dois_digitos(self):
        assert nome_arquivo_arte("MR#2", 10) == "MR#2_010.jpg"

    def test_numero_tres_digitos(self):
        assert nome_arquivo_arte("MR#3", 100) == "MR#3_100.jpg"

    def test_extensao_jpg(self):
        assert nome_arquivo_arte("DUDE#1", 1).endswith(".jpg")


class TestTruncarTexto:
    def test_sem_truncar_quando_curto(self):
        assert truncar_texto("abc", 10) == "abc"

    def test_trunca_com_reticencias(self):
        resultado = truncar_texto("abcdefghij", 5)
        assert resultado == "abcde..."

    def test_limite_exato_nao_trunca(self):
        assert truncar_texto("abcde", 5) == "abcde"

    def test_texto_vazio(self):
        assert truncar_texto("", 10) == ""

    def test_max_len_default_60(self):
        texto = "x" * 60
        assert truncar_texto(texto) == texto

    def test_max_len_default_trunca_acima_60(self):
        texto = "x" * 61
        resultado = truncar_texto(texto)
        assert resultado.endswith("...")
        assert len(resultado) == 63


class TestBackoffEspera:
    def test_aumenta_com_tentativas(self):
        assert backoff_espera(2) > backoff_espera(1)

    def test_respeita_maximo(self):
        assert backoff_espera(100, maximo=30.0) == 30.0

    def test_primeira_tentativa(self):
        assert backoff_espera(1, base=2.0) == 2.0

    def test_segunda_tentativa(self):
        assert backoff_espera(2, base=2.0) == 4.0


class TestFormatarDuracao:
    def test_apenas_segundos(self):
        assert formatar_duracao(45) == "45s"

    def test_zero_segundos(self):
        assert formatar_duracao(0) == "0s"

    def test_minutos_e_segundos(self):
        assert formatar_duracao(150) == "2m 30s"

    def test_exatos_60_segundos(self):
        assert formatar_duracao(60) == "1m 0s"

    def test_horas(self):
        assert formatar_duracao(3661) == "1h 1m 1s"

    def test_horas_sem_minutos(self):
        assert formatar_duracao(3600) == "1h 0m 0s"
