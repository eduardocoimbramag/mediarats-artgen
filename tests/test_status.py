"""
Testes unitários para utils/status.py.
"""

import re
import pytest
from utils.status import STATUS_VALIDOS, STATUS_CORES_EXCEL, STATUS_CORES_GUI


class TestStatusValidos:
    def test_contem_status_essenciais(self):
        essenciais = {"Planejado", "Pendente", "Gerando", "Gerado", "Erro"}
        assert essenciais.issubset(STATUS_VALIDOS)

    def test_contem_cancelado(self):
        assert "Cancelado" in STATUS_VALIDOS

    def test_e_frozenset(self):
        assert isinstance(STATUS_VALIDOS, frozenset)


class TestCoresExcel:
    def test_cobre_todos_status_validos(self):
        for status in STATUS_VALIDOS:
            assert status in STATUS_CORES_EXCEL, f"Status '{status}' sem cor Excel"

    def test_cores_sao_hex_6_chars(self):
        for status, cor in STATUS_CORES_EXCEL.items():
            assert re.fullmatch(r"[0-9A-Fa-f]{6}", cor), (
                f"'{status}': '{cor}' não é HEX de 6 dígitos"
            )

    def test_e_dict(self):
        assert isinstance(STATUS_CORES_EXCEL, dict)


class TestCoresGUI:
    def test_cobre_todos_status_validos(self):
        for status in STATUS_VALIDOS:
            assert status.lower() in STATUS_CORES_GUI, (
                f"Status '{status.lower()}' sem cor GUI"
            )

    def test_cada_entrada_tem_dois_elementos(self):
        for status, cores in STATUS_CORES_GUI.items():
            assert len(cores) == 2, f"'{status}': deve ter (bg, fg)"

    def test_cores_comecam_com_hash(self):
        for status, (bg, fg) in STATUS_CORES_GUI.items():
            assert bg.startswith("#"), f"'{status}': bg '{bg}' deve começar com #"
            assert fg.startswith("#"), f"'{status}': fg '{fg}' deve começar com #"

    def test_chaves_sao_lowercase(self):
        for chave in STATUS_CORES_GUI:
            assert chave == chave.lower(), f"Chave '{chave}' deve estar em lowercase"

    def test_e_dict(self):
        assert isinstance(STATUS_CORES_GUI, dict)
