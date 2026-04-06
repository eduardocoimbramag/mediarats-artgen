"""
Módulo de escrita/atualização da planilha Excel do Media Rats - Artgen.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from excel.reader import Solicitacao


STATUS_CORES = {
    "Planejado": "FFF9C4",
    "Pendente": "FFE0B2",
    "Gerando": "BBDEFB",
    "Gerado": "C8E6C9",
    "Erro": "FFCDD2",
}


class ExcelWriter:
    """Atualiza a planilha Excel após geração de artes.

    Args:
        caminho: Caminho absoluto para o arquivo .xlsx.
    """

    ABA_CONTEUDOS = "CONTEUDOS"
    ABA_AVALIACAO = "AVALIACAO_DETALHADA"

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)

    def _encontrar_aba(self, wb, nome: str):
        """Busca aba pelo nome (case-insensitive).

        Args:
            wb: Workbook aberto.
            nome: Nome da aba.

        Returns:
            Worksheet ou None.
        """
        for sn in wb.sheetnames:
            if sn.upper() == nome.upper():
                return wb[sn]
        return None

    def _garantir_aba_avaliacao(self, wb) -> object:
        """Cria aba AVALIACAO_DETALHADA se não existir.

        Args:
            wb: Workbook aberto.

        Returns:
            Worksheet da aba de avaliação.
        """
        ws = self._encontrar_aba(wb, self.ABA_AVALIACAO)
        if ws is not None:
            return ws

        ws = wb.create_sheet(title=self.ABA_AVALIACAO)
        cabecalho = [
            "Protocolo", "Cliente", "Tema", "Numero_Arte",
            "Prompt_Utilizado", "Imagem", "Qualidade",
            "Comentarios", "Usar?", "Data_Revisao",
            "Proximas_Acoes",
        ]
        ws.append(cabecalho)
        header_fill = PatternFill(start_color="1A237E", end_color="1A237E", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for col_idx, _ in enumerate(cabecalho, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        return ws

    def _encontrar_coluna(self, ws, nome: str) -> Optional[int]:
        """Localiza o índice (1-based) de uma coluna pelo nome.

        Args:
            ws: Worksheet.
            nome: Nome da coluna a localizar.

        Returns:
            Índice 1-based ou None se não encontrar.
        """
        for cell in ws[1]:
            if cell.value and str(cell.value).strip().upper() == nome.upper():
                return cell.column
        return None

    def _garantir_coluna(self, ws, nome: str) -> int:
        """Garante que a coluna exista, criando-a se necessário.

        Args:
            ws: Worksheet.
            nome: Nome da coluna.

        Returns:
            Índice 1-based da coluna.
        """
        col_idx = self._encontrar_coluna(ws, nome)
        if col_idx is not None:
            return col_idx
        max_col = ws.max_column or 1
        nova_col = max_col + 1
        header_cell = ws.cell(row=1, column=nova_col)
        header_cell.value = nome
        header_cell.font = Font(bold=True)
        return nova_col

    def atualizar_status(
        self,
        solicitacao: Solicitacao,
        novo_status: str,
        adicionar_data: bool = True,
    ) -> None:
        """Atualiza o status de uma solicitação na aba CONTEUDOS.

        Args:
            solicitacao: Objeto com dados da solicitação (incluindo linha_excel).
            novo_status: Novo valor de status (ex: 'Gerado').
            adicionar_data: Se True, atualiza/cria coluna 'Data_Geracao'.
        """
        wb = openpyxl.load_workbook(self.caminho)
        ws = self._encontrar_aba(wb, self.ABA_CONTEUDOS)
        if ws is None:
            wb.close()
            return

        col_status = self._encontrar_coluna(ws, "STATUS")
        if col_status:
            cell = ws.cell(row=solicitacao.linha_excel, column=col_status)
            cell.value = novo_status
            cor = STATUS_CORES.get(novo_status, "FFFFFF")
            cell.fill = PatternFill(start_color=cor, end_color=cor, fill_type="solid")

        if adicionar_data:
            col_data = self._garantir_coluna(ws, "DATA_GERACAO")
            ws.cell(
                row=solicitacao.linha_excel, column=col_data
            ).value = datetime.now().strftime("%d/%m/%Y %H:%M")

        wb.save(self.caminho)
        wb.close()

    def registrar_avaliacao(
        self,
        solicitacao: Solicitacao,
        caminhos_imagens: List[str],
    ) -> None:
        """Cria/atualiza linhas de avaliação para os arquivos gerados.

        Args:
            solicitacao: Objeto com dados da solicitação.
            caminhos_imagens: Lista de caminhos relativos das imagens geradas.
        """
        wb = openpyxl.load_workbook(self.caminho)
        ws_aval = self._garantir_aba_avaliacao(wb)

        hoje = date.today().strftime("%d/%m/%Y")

        for i, caminho_img in enumerate(caminhos_imagens, start=1):
            prompt = solicitacao.prompts[i - 1] if i - 1 < len(solicitacao.prompts) else ""
            linha = [
                solicitacao.protocolo,
                solicitacao.cliente,
                solicitacao.tema,
                i,
                prompt,
                caminho_img,
                "",
                "",
                "",
                hoje,
                "",
            ]
            ws_aval.append(linha)

        wb.save(self.caminho)
        wb.close()

    def listar_clientes(self) -> list:
        """Retorna todos os clientes da aba CLIENTES como lista de dicts.

        Returns:
            Lista de dicts com 'codigo' e 'nome'.
        """
        wb = openpyxl.load_workbook(self.caminho)
        ws = self._encontrar_aba(wb, "CLIENTES")
        clientes = []
        if ws:
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0]:
                    codigo = str(row[0]).strip().upper()
                    nome = str(row[1]).strip() if len(row) > 1 and row[1] else codigo
                    clientes.append({"codigo": codigo, "nome": nome})
        wb.close()
        return clientes

    def adicionar_cliente(self, codigo: str, nome: str) -> None:
        """Adiciona um novo cliente na aba CLIENTES.

        Args:
            codigo: Código único do cliente (2-4 letras).
            nome: Nome do cliente.

        Raises:
            ValueError: Se o código já existir.
        """
        wb = openpyxl.load_workbook(self.caminho)
        ws = self._encontrar_aba(wb, "CLIENTES")
        if ws is None:
            ws = wb.create_sheet("CLIENTES")
            ws.append(["CODIGO_CLIENTE", "NOME"])

        codigo = codigo.strip().upper()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0] and str(row[0]).strip().upper() == codigo:
                wb.close()
                raise ValueError(f"Cliente com código '{codigo}' já existe.")

        ws.append([codigo, nome.strip()])
        wb.save(self.caminho)
        wb.close()

    def atualizar_cliente(self, codigo_original: str, novo_codigo: str, novo_nome: str) -> None:
        """Atualiza os dados de um cliente existente.

        Args:
            codigo_original: Código atual do cliente.
            novo_codigo: Novo código (pode ser igual ao original).
            novo_nome: Novo nome do cliente.

        Raises:
            ValueError: Se o cliente não for encontrado.
        """
        wb = openpyxl.load_workbook(self.caminho)
        ws = self._encontrar_aba(wb, "CLIENTES")
        if ws is None:
            wb.close()
            raise ValueError("Aba CLIENTES não encontrada.")

        codigo_original = codigo_original.strip().upper()
        novo_codigo = novo_codigo.strip().upper()

        for row in ws.iter_rows(min_row=2):
            if row[0].value and str(row[0].value).strip().upper() == codigo_original:
                row[0].value = novo_codigo
                if len(row) > 1:
                    row[1].value = novo_nome.strip()
                wb.save(self.caminho)
                wb.close()
                return

        wb.close()
        raise ValueError(f"Cliente '{codigo_original}' não encontrado.")

    def remover_cliente(self, codigo: str) -> None:
        """Remove um cliente da aba CLIENTES.

        Args:
            codigo: Código do cliente a remover.

        Raises:
            ValueError: Se o cliente não for encontrado.
        """
        wb = openpyxl.load_workbook(self.caminho)
        ws = self._encontrar_aba(wb, "CLIENTES")
        if ws is None:
            wb.close()
            raise ValueError("Aba CLIENTES não encontrada.")

        codigo = codigo.strip().upper()
        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=1)
            if cell.value and str(cell.value).strip().upper() == codigo:
                ws.delete_rows(row_idx)
                wb.save(self.caminho)
                wb.close()
                return

        wb.close()
        raise ValueError(f"Cliente '{codigo}' não encontrado.")

    def criar_estrutura_planilha(self) -> None:
        """Cria as abas e cabeçalhos mínimos se a planilha estiver vazia.
        Não sobrescreve dados existentes.
        """
        wb = openpyxl.load_workbook(self.caminho)
        abas_existentes = [s.upper() for s in wb.sheetnames]

        if "CLIENTES" not in abas_existentes:
            ws_cli = wb.create_sheet("CLIENTES")
            ws_cli.append(["CODIGO_CLIENTE", "NOME"])

        if self.ABA_CONTEUDOS.upper() not in abas_existentes:
            ws_cont = wb.create_sheet(self.ABA_CONTEUDOS)
            cabecalho_cont = (
                ["PROTOCOLO", "CODIGO_CLIENTE", "CLIENTE", "NUMERO_SOLICITACAO", "TEMA", "STATUS",
                 "DATA_PLANEJADA"]
                + [f"PROMPT {i}" for i in range(1, 11)]
            )
            ws_cont.append(cabecalho_cont)

        self._garantir_aba_avaliacao(wb)
        wb.save(self.caminho)
        wb.close()
