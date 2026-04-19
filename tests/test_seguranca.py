"""
Testes das melhorias de segurança e robustez (Seção 7).

Cobre:
- 7.2: SensitiveFilter (mascaramento de senhas em logs)
- 7.4: _sanitizar_celula (prevenção contra injeção de fórmulas Excel)
- 7.3: _backup_planilha / _limpar_backups_antigos
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import openpyxl
import pytest

from excel.writer import ExcelWriter, _sanitizar_celula
from utils.logger import SensitiveFilter


# ── 7.2: SensitiveFilter ─────────────────────────────────────────────────────

class TestSensitiveFilter:
    def _make_record(self, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="artgen", level=logging.INFO, pathname="", lineno=1,
            msg=msg, args=None, exc_info=None,
        )

    def test_mascara_adapta_senha(self):
        f = SensitiveFilter()
        rec = self._make_record("ADAPTA_SENHA=minhasenha123")
        f.filter(rec)
        assert "minhasenha123" not in rec.msg
        assert "***" in rec.msg

    def test_mascara_password_case_insensitive(self):
        f = SensitiveFilter()
        rec = self._make_record("PASSWORD: segredo")
        f.filter(rec)
        assert "segredo" not in rec.msg

    def test_mascara_senha_prefixo(self):
        f = SensitiveFilter()
        rec = self._make_record("senha=abc123")
        f.filter(rec)
        assert "abc123" not in rec.msg

    def test_mascara_token(self):
        f = SensitiveFilter()
        rec = self._make_record("token: eyJhbGciOiJ...")
        f.filter(rec)
        assert "eyJhbGciOiJ..." not in rec.msg

    def test_nao_modifica_mensagem_inocente(self):
        f = SensitiveFilter()
        rec = self._make_record("Download completo: arquivo.png")
        f.filter(rec)
        assert rec.msg == "Download completo: arquivo.png"

    def test_sempre_retorna_true(self):
        f = SensitiveFilter()
        rec = self._make_record("qualquer mensagem")
        assert f.filter(rec) is True


# ── 7.4: sanitização anti-injeção de fórmula Excel ──────────────────────────

class TestSanitizarCelula:
    @pytest.mark.parametrize("valor,esperado", [
        ("=CMD()", "'=CMD()"),
        ("=HYPERLINK(\"evil\")", "'=HYPERLINK(\"evil\")"),
        ("+1+1", "'+1+1"),
        ("-SUM(A1)", "'-SUM(A1)"),
        ("@risk", "'@risk"),
        ("\tinjeção", "'\tinjeção"),
        ("\rcarriage", "'\rcarriage"),
    ])
    def test_prefixa_valores_perigosos(self, valor, esperado):
        assert _sanitizar_celula(valor) == esperado

    @pytest.mark.parametrize("valor", [
        "texto normal",
        "DUDE#1",
        "Cliente XYZ",
        "2024-01-15",
        "#hashtag",
    ])
    def test_preserva_valores_seguros(self, valor):
        assert _sanitizar_celula(valor) == valor

    def test_preserva_nao_strings(self):
        assert _sanitizar_celula(42) == 42
        assert _sanitizar_celula(3.14) == 3.14
        assert _sanitizar_celula(None) is None
        assert _sanitizar_celula(True) is True

    def test_preserva_string_vazia(self):
        assert _sanitizar_celula("") == ""


# ── 7.3: backup antes de operações destrutivas ──────────────────────────────

class TestBackupPlanilha:
    def _criar_planilha_minima(self, caminho: Path) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "CONTEUDOS"
        ws.append(["PROTOCOLO", "CLIENTE", "STATUS"])
        ws.append(["TEST#1", "Cliente", "Planejado"])
        wb.save(caminho)
        wb.close()

    def test_cria_backup_com_timestamp(self, tmp_path):
        planilha = tmp_path / "teste.xlsx"
        self._criar_planilha_minima(planilha)
        writer = ExcelWriter(planilha)

        destino = writer._backup_planilha()
        assert destino is not None
        assert destino.exists()
        assert destino.name.startswith(".bak_")
        assert destino.name.endswith("_teste.xlsx")

    def test_retorna_none_se_planilha_inexistente(self, tmp_path):
        writer = ExcelWriter(tmp_path / "nao_existe.xlsx")
        assert writer._backup_planilha() is None

    def test_mantem_apenas_3_backups(self, tmp_path):
        planilha = tmp_path / "teste.xlsx"
        self._criar_planilha_minima(planilha)
        writer = ExcelWriter(planilha)

        import time
        for _ in range(6):
            writer._backup_planilha()
            time.sleep(1.05)  # garante timestamps distintos (precisão de segundos)

        backups = list(tmp_path.glob(".bak_*_teste.xlsx"))
        assert len(backups) == 3

    def test_remocao_dispara_backup(self, tmp_path):
        from excel.reader import Solicitacao
        planilha = tmp_path / "teste.xlsx"
        self._criar_planilha_minima(planilha)
        writer = ExcelWriter(planilha)

        sol = Solicitacao(
            linha_excel=2, codigo_cliente="TEST", cliente="Cliente",
            numero_solicitacao=1, protocolo="TEST#1", tema="",
        )
        writer.remover_solicitacao(sol)

        backups = list(tmp_path.glob(".bak_*_teste.xlsx"))
        assert len(backups) == 1
