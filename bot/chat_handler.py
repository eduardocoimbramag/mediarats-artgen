"""
Mixin com a lógica de navegação de pastas, chats e posicionamento no Adapta.org.

Extraído de ``adapta_generator.py`` para isolar as responsabilidades de
gerenciamento de chats (resolução, criação, renomeação e busca na sidebar)
do restante do gerador.
"""

from __future__ import annotations

import time
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from bot.selectors import SELECTORS_PROJETO
from utils.logger import logger


class AdaptaChatMixin:
    """Mixin com métodos de navegação de chats e pastas no AdaptaOne.

    Requer que a classe base defina:
    - ``self.handler`` (SeleniumHandler) com ``driver``
    - ``self.url_adapta`` (str)
    - ``self._aguardar(segundos)``
    - ``self._digitar_naturalista(elem, texto, ...)``
    - ``self._aguardar_compositor(timeout_s)`` (de AdaptaImageMixin)
    - ``self._aguardar_fim_rename(timeout_s)`` (de AdaptaImageMixin)
    - ``self._detectar_tela_login()`` (de AdaptaLoginMixin)
    - ``self._esta_no_dashboard()`` (de AdaptaLoginMixin)
    """

    def resolver_chat_cliente(self, codigo_cliente: str, nome_cliente: str) -> bool:
        """Garante que o navegador está posicionado no chat canônico do cliente.

        Regra: 1 chat por cliente dentro da pasta NOME_PASTA_PROJETO.

        Fluxo determinístico:
            1. Consulta chat_mapping.json pelo código do cliente.
            2. Se URL registrada: navega para ela e valida.
            3. Se URL inválida (chat deletado): remove o vínculo e rebusca.
            4. Busca na lista de chats por título contendo código/nome.
            5. Se não encontrar: cria novo chat e persiste o vínculo.

        Proteção contra duplicatas:
            set_chat_url() usa first-write-wins — nunca sobrescreve um vínculo
            existente; forcar_chat_url() é usado apenas quando o original falhou.

        Args:
            codigo_cliente: Código único do cliente (ex: DUDE).
            nome_cliente: Nome legível para nomear/encontrar o chat.

        Returns:
            True se o chat foi resolvido com sucesso.
        """
        from bot.chat_mapping import chat_mapping

        titulo_esperado = self._titulo_chat_para_cliente(codigo_cliente, nome_cliente)
        logger.info(f"[Chat] Resolvendo chat: '{titulo_esperado}'...")

        self._navegar_pasta_projeto()

        url_existente = chat_mapping.get_chat_url(codigo_cliente)
        if url_existente:
            logger.info(f"[Chat] Vínculo registrado: {url_existente}")
            if self._navegar_para_chat(url_existente):
                logger.sucesso(f"[Chat] ✓ Chat do cliente '{codigo_cliente}' reutilizado.")
                return True
            logger.aviso("[Chat] URL registrada inválida. Removendo vínculo e rebuscando...")
            chat_mapping.remover(codigo_cliente)

        url_encontrada = self._buscar_chat_na_lista(codigo_cliente, nome_cliente)
        if url_encontrada:
            chat_mapping.forcar_chat_url(codigo_cliente, url_encontrada, titulo_esperado)
            logger.sucesso(f"[Chat] ✓ Chat encontrado na lista: {url_encontrada}")
            return True

        logger.info(f"[Chat] Criando novo chat para '{titulo_esperado}'...")
        url_novo = self._criar_novo_chat(codigo_cliente, nome_cliente)
        if url_novo:
            chat_mapping.set_chat_url(codigo_cliente, url_novo, titulo_esperado)
            logger.sucesso(f"[Chat] ✓ Novo chat criado: {url_novo}")
            return True

        logger.aviso(
            f"[Chat] ✗ Não foi possível resolver chat para '{codigo_cliente}'. "
            "Continuando na página atual."
        )
        return False

    def _navegar_pasta_projeto(self) -> bool:
        """Clica na pasta do projeto no sidebar para contextualizar os chats.

        Busca por texto exato de NOME_PASTA_PROJETO em elementos clicáveis
        do sidebar. Falha silenciosamente para não bloquear a geração.

        Returns:
            True se a pasta foi localizada e clicada.
        """
        from utils.config import Config
        nome_pasta = Config.NOME_PASTA_PROJETO
        driver = self.handler.driver

        logger.info(f"[Chat] Buscando pasta '{nome_pasta}' no sidebar...")

        xpaths = [
            f".//*[normalize-space(text())='{nome_pasta}']",
            f".//*[contains(normalize-space(text()), '{nome_pasta}')]",
            f".//*[contains(normalize-space(.), '{nome_pasta}')]",
        ]

        for xpath in xpaths:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    tag = elem.tag_name.lower()
                    if tag not in ("a", "button", "li", "div", "span", "p"):
                        continue
                    if not elem.is_displayed():
                        continue
                    try:
                        driver.execute_script("arguments[0].click();", elem)
                        self._aguardar(1.5)
                        logger.info(f"[Chat] Pasta '{nome_pasta}' acessada.")
                        return True
                    except Exception:
                        continue
            except Exception:
                continue

        logger.aviso(f"[Chat] Pasta '{nome_pasta}' não localizada no sidebar.")
        return False

    def _navegar_para_chat(self, url: str) -> bool:
        """Navega para a URL de um chat e verifica se chegou corretamente.

        Além de checar a URL, valida que a página possui um campo de prompt
        funcional (textarea/input). Se o chat foi deletado manualmente no
        Adapta, a página pode carregar mas sem compositor — isso é tratado
        como chat inválido.

        Args:
            url: URL completa do chat armazenada no mapeamento.

        Returns:
            True se a navegação resultou em uma página de chat válida
            com compositor funcional.
        """
        driver = self.handler.driver
        try:
            driver.get(url)
            self._aguardar(3.0)
        except Exception as exc:
            logger.aviso(f"[Chat] Falha ao navegar para {url}: {exc}")
            return False

        url_atual = driver.current_url

        if self._detectar_tela_login():
            logger.aviso("[Chat] Redirecionado para login — sessão expirou.")
            return False

        if url_atual.rstrip("/") in (self.url_adapta, self.url_adapta + "/"):
            logger.aviso("[Chat] Redirecionado para homepage — chat pode ter sido deletado.")
            return False

        if self._esta_no_dashboard():
            logger.aviso("[Chat] Redirecionado para dashboard — chat removido ou inacessível.")
            return False

        if not self._e_url_de_chat_valida(url_atual):
            logger.aviso(f"[Chat] URL resultante não é de chat: {url_atual}")
            return False

        if not self._verificar_compositor_presente():
            logger.aviso(
                "[Chat] Chat carregado mas sem campo de prompt funcional — "
                "chat removido ou inconsistente."
            )
            return False

        logger.info("[Chat] Chat validado — compositor funcional encontrado.")
        return True

    def _verificar_compositor_presente(self, tentativas: int = 2) -> bool:
        """Verifica se a página atual possui um campo de prompt funcional.

        Usa `_aguardar_compositor` com timeout baseado no número de tentativas.
        Detecta corretamente tanto textarea quanto div[contenteditable='true'].

        Args:
            tentativas: Quantidade de ciclos de 2s de espera (total = tentativas*2s).

        Returns:
            True se um compositor válido foi encontrado e está visível.
        """
        timeout_s = max(tentativas * 2, 4)
        campo = self._aguardar_compositor(timeout_s=timeout_s)
        if campo is not None:
            logger.info("[Chat] Compositor presente e validado na página.")
            return True
        logger.aviso("[Chat] Compositor não encontrado — chat removido ou inacessível.")
        return False

    def _e_url_de_chat_valida(self, url: str) -> bool:
        """Verifica heuristicamente se uma URL corresponde a um chat ativo.

        Args:
            url: URL a verificar.

        Returns:
            True se a URL parece ser de um chat (tem path além da raiz e não é login).
        """
        if not url:
            return False
        url_lower = url.lower()
        for palavra in ("login", "signin", "entrar", "register", "cadastro"):
            if palavra in url_lower:
                return False
        base = self.url_adapta.rstrip("/")
        path = url.rstrip("/")[len(base):].lstrip("/")
        return len(path) > 2

    def _buscar_chat_na_lista(self, codigo_cliente: str, nome_cliente: str) -> Optional[str]:
        """Procura na lista de chats do sidebar um chat cujo título contenha o cliente.

        Estratégia de busca em ordem de prioridade:
            1. Link contendo o código do cliente (mais específico)
            2. Link contendo o nome do cliente

        Args:
            codigo_cliente: Código do cliente (ex: DUDE).
            nome_cliente: Nome do cliente.

        Returns:
            URL do chat encontrado, ou None.
        """
        driver = self.handler.driver
        termos = [t for t in [codigo_cliente.strip(), nome_cliente.strip()] if t]

        for termo in termos:
            xpaths = [
                f"//a[contains(normalize-space(.), '{termo}')]",
                f"//*[contains(normalize-space(text()), '{termo}')]/ancestor-or-self::a",
                f"//*[contains(normalize-space(.), '{termo}')]/ancestor-or-self::a[@href]",
            ]
            for xpath in xpaths:
                try:
                    elems = driver.find_elements(By.XPATH, xpath)
                    for elem in elems:
                        if not elem.is_displayed():
                            continue
                        href = elem.get_attribute("href") or ""
                        if href and self._e_url_de_chat_valida(href):
                            logger.info(f"[Chat] Chat encontrado por '{termo}': {href}")
                            try:
                                driver.execute_script("arguments[0].click();", elem)
                                self._aguardar(2.0)
                                url_atual = driver.current_url
                                if self._e_url_de_chat_valida(url_atual):
                                    return url_atual
                            except Exception:
                                return href
                except Exception:
                    continue

        return None

    def _criar_novo_chat(self, codigo_cliente: str, nome_cliente: str) -> Optional[str]:
        """Cria um novo chat no Adapta.org e retorna sua URL.

        Clica no botão de novo chat, aguarda a navegação e tenta
        renomear o chat com o título padronizado do cliente.

        Args:
            codigo_cliente: Código do cliente.
            nome_cliente: Nome do cliente para o título do chat.

        Returns:
            URL do chat criado, ou None se a criação falhar.
        """
        driver = self.handler.driver
        url_antes = driver.current_url

        botao = self._localizar_botao_novo_chat()
        if botao is None:
            logger.aviso("[Chat] Botão 'novo chat' não encontrado.")
            return None

        try:
            driver.execute_script("arguments[0].click();", botao)
            self._aguardar(3.0)
        except Exception as exc:
            logger.aviso(f"[Chat] Falha ao clicar 'novo chat': {exc}")
            return None

        url_novo = driver.current_url
        if url_novo.rstrip("/") == url_antes.rstrip("/"):
            self._aguardar(2.0)
            url_novo = driver.current_url

        if not self._e_url_de_chat_valida(url_novo):
            logger.aviso(f"[Chat] URL após criar chat não é válida: {url_novo}")
            return None

        logger.info(f"[Chat] Novo chat aberto em: {url_novo}")
        titulo = self._titulo_chat_para_cliente(codigo_cliente, nome_cliente)
        self._renomear_chat(titulo)

        logger.info(
            "[Chat] Rename concluído. Aguardando input de rename desaparecer..."
        )
        self._aguardar_fim_rename(timeout_s=8)

        logger.info(
            "[Chat] Aguardando compositor ficar pronto para envio de prompt..."
        )
        campo = self._aguardar_compositor(timeout_s=12)
        if campo is not None:
            logger.sucesso("[Chat] Compositor pronto após criação do chat.")
        else:
            logger.aviso(
                "[Chat] Compositor não detectado após criação — "
                "_executar_geracao tentará localizar com timeout próprio."
            )

        return url_novo

    def _localizar_botao_novo_chat(self):
        """Localiza o botão de novo chat na interface do Adapta.org.

        Tenta múltiplos seletores CSS e XPath para cobrir variações de layout.

        Returns:
            WebElement do botão ou None se não encontrado.
        """
        driver = self.handler.driver

        for sel in SELECTORS_PROJETO["botao_novo_chat"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        return e
            except Exception:
                continue

        palavras_chave = ["novo chat", "new chat", "nova conversa", "new conversation",
                          "criar chat", "create chat"]
        for palavra in palavras_chave:
            xpath = (
                f"//button[contains(translate(normalize-space(.), "
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{palavra}')]"
                f" | //a[contains(translate(normalize-space(.), "
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{palavra}')]"
            )
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        return e
            except Exception:
                continue

        return None

    def _renomear_chat(self, titulo: str) -> bool:
        """Tenta renomear o chat atual com o título do cliente.

        Busca campos de título editáveis (input ou contenteditable) e
        digita o novo nome. Falha silenciosamente se não encontrar.

        Args:
            titulo: Novo título a aplicar ao chat.

        Returns:
            True se renomeado com sucesso.
        """
        driver = self.handler.driver

        for sel in SELECTORS_PROJETO["titulo_chat"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if not (elem.is_displayed() and elem.is_enabled()):
                        continue
                    try:
                        elem.click()
                        time.sleep(0.3)
                        elem.send_keys(Keys.CONTROL + "a")
                        time.sleep(0.2)
                        elem.clear()
                        time.sleep(0.2)
                        self._digitar_naturalista(elem, titulo, delay_min=0.02, delay_max=0.05)
                        time.sleep(0.3)
                        elem.send_keys(Keys.RETURN)
                        time.sleep(0.5)
                        logger.info(f"[Chat] Chat renomeado para '{titulo}'.")
                        return True
                    except Exception:
                        continue
            except Exception:
                continue

        logger.aviso(f"[Chat] Não foi possível renomear chat para '{titulo}'.")
        return False

    def _titulo_chat_para_cliente(self, codigo_cliente: str, nome_cliente: str) -> str:
        """Gera o título padronizado do chat para um cliente.

        Formato: '[CODIGO] - [Nome do Cliente]'
        Exemplo: 'DUDE - Dude Clothing'

        Este título é usado tanto para nomear novos chats quanto
        para encontrar chats existentes na lista do sidebar.

        Args:
            codigo_cliente: Código do cliente (ex: DUDE).
            nome_cliente: Nome legível do cliente.

        Returns:
            Título formatado.
        """
        codigo = codigo_cliente.strip().upper()
        nome = nome_cliente.strip()
        if nome and nome.upper() != codigo:
            return f"{codigo} - {nome}"
        return codigo
