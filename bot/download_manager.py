"""
Gerenciador de download de imagens geradas pelo Adapta.org.
"""

from __future__ import annotations

import base64
import time
import urllib.request
from pathlib import Path
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

from utils.logger import logger


class DownloadManager:
    """Responsável por baixar e salvar as imagens geradas.

    Args:
        pasta_output: Diretório onde as imagens serão salvas.
        driver: Instância ativa do WebDriver.
    """

    def __init__(self, pasta_output: Path, driver: WebDriver) -> None:
        self.pasta_output = Path(pasta_output)
        self.pasta_output.mkdir(parents=True, exist_ok=True)
        self.driver = driver

    def baixar_de_url(self, url: str, nome_arquivo: str) -> Optional[Path]:
        """Baixa uma imagem diretamente de uma URL.

        Args:
            url: URL da imagem.
            nome_arquivo: Nome do arquivo de destino.

        Returns:
            Path do arquivo salvo ou None em caso de falha.
        """
        destino = self.pasta_output / nome_arquivo
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados = resp.read()
            destino.write_bytes(dados)
            logger.sucesso(f"Imagem baixada: {nome_arquivo} ({len(dados)//1024} KB)")
            return destino
        except Exception as exc:
            logger.erro(f"Falha ao baixar imagem de URL: {exc}")
            return None

    def baixar_de_elemento(
        self, seletor_img: str, nome_arquivo: str, tipo: str = "css"
    ) -> Optional[Path]:
        """Extrai e salva imagem de um elemento <img> na página.

        Args:
            seletor_img: Seletor CSS ou XPath do elemento <img>.
            nome_arquivo: Nome do arquivo de destino.
            tipo: 'css' ou 'xpath'.

        Returns:
            Path do arquivo salvo ou None em caso de falha.
        """
        destino = self.pasta_output / nome_arquivo
        try:
            by = By.CSS_SELECTOR if tipo == "css" else By.XPATH
            elementos = self.driver.find_elements(by, seletor_img)
            if not elementos:
                logger.erro(f"Elemento de imagem não encontrado: {seletor_img}")
                return None

            elem = elementos[-1]
            src = elem.get_attribute("src") or ""

            if src.startswith("data:image"):
                return self._salvar_base64(src, destino)
            elif src.startswith("http"):
                return self.baixar_de_url(src, nome_arquivo)
            else:
                logger.erro(f"Formato de imagem desconhecido: {src[:50]}")
                return None

        except Exception as exc:
            logger.erro(f"Erro ao extrair imagem do elemento: {exc}")
            return None

    def baixar_via_js(self, nome_arquivo: str) -> Optional[Path]:
        """Tenta obter a imagem via JavaScript executado no navegador.
        Procura a imagem gerada mais recente no canvas ou elementos visíveis.

        Args:
            nome_arquivo: Nome do arquivo de destino.

        Returns:
            Path do arquivo salvo ou None.
        """
        destino = self.pasta_output / nome_arquivo
        try:
            script = """
            // Tenta obter de canvas
            var canvases = document.querySelectorAll('canvas');
            if (canvases.length > 0) {
                return canvases[canvases.length - 1].toDataURL('image/jpeg', 0.95);
            }
            // Tenta de imagens
            var imgs = document.querySelectorAll('img[src^="http"], img[src^="data:image"]');
            var src = '';
            imgs.forEach(function(img) {
                if (img.naturalWidth > 200 && img.naturalHeight > 200) {
                    src = img.src;
                }
            });
            return src;
            """
            resultado = self.driver.execute_script(script)
            if resultado and resultado.startswith("data:image"):
                return self._salvar_base64(resultado, destino)
            elif resultado and resultado.startswith("http"):
                return self.baixar_de_url(resultado, nome_arquivo)
            return None
        except Exception as exc:
            logger.erro(f"Erro ao extrair imagem via JS: {exc}")
            return None

    def _salvar_base64(self, data_uri: str, destino: Path) -> Optional[Path]:
        """Decodifica e salva uma imagem em base64.

        Args:
            data_uri: Data URI com a imagem em base64.
            destino: Caminho de destino do arquivo.

        Returns:
            Path do arquivo salvo ou None.
        """
        try:
            if "," in data_uri:
                _, encoded = data_uri.split(",", 1)
            else:
                encoded = data_uri
            dados = base64.b64decode(encoded)
            destino.write_bytes(dados)
            logger.sucesso(f"Imagem salva: {destino.name} ({len(dados)//1024} KB)")
            return destino
        except Exception as exc:
            logger.erro(f"Erro ao salvar imagem base64: {exc}")
            return None

    def verificar_arquivo(self, caminho: Path, tamanho_minimo_bytes: int = 5000) -> bool:
        """Verifica se o arquivo de imagem é válido.

        Args:
            caminho: Caminho do arquivo a verificar.
            tamanho_minimo_bytes: Tamanho mínimo esperado em bytes.

        Returns:
            True se o arquivo for válido.
        """
        if not caminho or not caminho.exists():
            return False
        tamanho = caminho.stat().st_size
        if tamanho < tamanho_minimo_bytes:
            logger.aviso(f"Arquivo suspeito (muito pequeno: {tamanho} bytes): {caminho.name}")
            return False
        return True
