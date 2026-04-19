"""
Mixin com toda a lógica de login automático no Adapta.org.

Extraído de ``adapta_generator.py`` para isolar as responsabilidades de
autenticação (detecção de tela de login, preenchimento de e-mail/senha,
navegação pós-login) do restante do gerador.
"""

from __future__ import annotations

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from bot.selectors import SELECTORS, SELECTORS_LOGIN
from utils.logger import logger


class AdaptaLoginMixin:
    """Mixin com métodos de login e navegação inicial para o AdaptaOne.

    Requer que a classe base defina:
    - ``self.handler`` (SeleniumHandler) com ``driver`` e ``navegar``
    - ``self.url_adapta`` (str)
    - ``self._aguardar(segundos)``
    - ``self._emitir_status(msg)``
    - ``self._digitar_naturalista(elem, texto, ...)``
    """

    def acessar_adapta(self, email: str = "", senha: str = "") -> bool:
        """Navega para o AdaptaOne e verifica/realiza login.

        Após login bem-sucedido, navega automaticamente para a seção
        "ADAPTA one" (Chat com IAs premium) para que o prompt field
        seja encontrado na etapa de geração.

        Lógica de login:
            1. Se não há tela de login → sessão ativa, prossegue.
            2. Se há tela de login E credenciais estão configuradas →
               tenta login automático primeiro.
            3. Se login automático falha → emite ``login_falhou``.
            4. Se credenciais não estão configuradas → emite
               ``login_necessario``.

        Args:
            email: E-mail de login (opcional).
            senha: Senha de login (opcional).

        Returns:
            True se autenticado e dentro da interface de chat.
            False se login manual for necessário (navegador permanece aberto).
        """
        logger.info("Acessando AdaptaOne...")
        ok = self.handler.navegar(self.url_adapta)
        if not ok:
            return False

        self._aguardar(3.0)

        if not self._detectar_tela_login():
            logger.sucesso("AdaptaOne carregado — sessão ativa.")
            self._navegar_para_adapta_one()
            return True

        tem_credenciais = bool(email and email.strip() and senha and senha.strip())

        if tem_credenciais:
            logger.info("Tela de login detectada. Login automático configurado — tentando...")
            resultado = self.tentar_login_automatico(email, senha)
            if resultado == "ok":
                logger.sucesso("Login automático realizado com sucesso.")
                self._navegar_para_adapta_one()
                return True
            if resultado == "campos_nao_encontrados":
                logger.aviso(
                    "Login automático falhou: campos do formulário não localizados "
                    "na página. A interface pode não ter carregado completamente — "
                    "verifique o seletor ou tente login manual."
                )
            else:
                logger.aviso(
                    "Login automático falhou: credenciais inválidas ou redirecionamento "
                    "inesperado. Verifique e-mail/senha em Configurações ou faça login manual."
                )
            self._emitir_status("login_falhou")
            return False

        logger.aviso(
            "Login manual necessário — credenciais de login automático não configuradas. "
            "Faça login no navegador e clique em 'Iniciar Geração' novamente."
        )
        self._emitir_status("login_necessario")
        return False

    def _esta_no_dashboard(self) -> bool:
        """Verifica se a página atual é o dashboard do AdaptaOne (não um chat).

        Usa dois sinais em ordem de confiabilidade:
        1. URL idêntica à raiz/dashboard (mais confiável).
        2. Presença visível de 'Acesso Rápido' — seção exclusiva do dashboard.
           Não usamos 'Chat com IAs' nem 'ADAPTAONE' pois podem aparecer no
           sidebar mesmo dentro da interface de chat.

        Returns:
            True se estiver no dashboard/menu inicial.
        """
        driver = self.handler.driver
        url_atual = driver.current_url.rstrip("/")
        base = self.url_adapta.rstrip("/")

        if url_atual == base or url_atual == base + "/dashboard":
            return True

        for texto in ("Acesso Rápido", "Acesso Rapido"):
            try:
                elems = driver.find_elements(
                    By.XPATH,
                    f".//*[contains(normalize-space(.), '{texto}')]"
                )
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                continue

        return False

    def _navegar_para_adapta_one(self) -> bool:
        """Clica no card 'ADAPTA one' no dashboard para entrar no chat.

        Só age se o dashboard estiver visível. Se já estiver dentro
        de uma página de chat, retorna True imediatamente sem clicar.

        Returns:
            True se a navegação foi bem-sucedida ou já estava no chat.
        """
        if not self._esta_no_dashboard():
            logger.info("[AdaptaOne] Já dentro da interface de chat.")
            return True

        driver = self.handler.driver
        logger.info("[AdaptaOne] Dashboard detectado. Clicando em 'ADAPTA one'...")

        xpaths_card = [
            ".//*[contains(normalize-space(text()), 'Chat com IAs')]",
            ".//*[contains(normalize-space(text()), 'Chat com IAs premium')]",
            ".//h2[contains(normalize-space(text()), 'one')]",
            ".//h3[contains(normalize-space(text()), 'one')]",
            ".//*[contains(@class, 'card')][contains(normalize-space(.), 'one')]",
            ".//*[contains(@class, 'item')][contains(normalize-space(.), 'one')]",
            ".//a[contains(normalize-space(.), 'one')]",
        ]

        for xpath in xpaths_card:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    if not elem.is_displayed():
                        continue
                    try:
                        clickable = elem
                        parent = elem.find_element(By.XPATH, "./ancestor-or-self::a | ./ancestor-or-self::button")
                        if parent and parent.is_displayed():
                            clickable = parent
                    except Exception:
                        pass
                    try:
                        driver.execute_script("arguments[0].click();", clickable)
                        self._aguardar(3.0)
                        if not self._esta_no_dashboard():
                            logger.sucesso("[AdaptaOne] Entrou na interface de chat com sucesso.")
                            return True
                    except Exception:
                        continue
            except Exception:
                continue

        logger.aviso(
            "[AdaptaOne] Não foi possível clicar no card 'ADAPTA one' automaticamente. "
            "Verifique se o layout da página mudou."
        )
        return False

    def tentar_login_automatico(self, email: str, senha: str) -> str:
        """Realiza login automático no Adapta One em duas etapas.

        Etapa 1 (/sign-in): preenche e-mail → clica Continuar.
        Etapa 2 (/sign-in/factor-one): preenche senha → clica Continuar.

        Args:
            email: E-mail de login.
            senha: Senha de login.

        Returns:
            'ok'                     se login bem-sucedido.
            'campos_nao_encontrados' se algum campo/etapa não foi localizado.
            'credenciais_invalidas'  se após submissão permanece na tela de login.
            'erro'                   se ocorreu exceção inesperada.
        """
        try:
            resultado = self._login_etapa_email(email)
            if resultado != "ok":
                return resultado

            resultado = self._aguardar_etapa_senha()
            if resultado != "ok":
                return resultado

            resultado = self._login_etapa_senha(senha)
            if resultado != "ok":
                return resultado

            logger.info("[Login] Aguardando confirmação de autenticação (até 5s)...")
            self._aguardar(3.0)
            if self._detectar_tela_login():
                logger.aviso("[Login] Tela de login ainda ativa após submissão da senha.")
                return "credenciais_invalidas"

            return "ok"

        except Exception as exc:
            logger.aviso(f"[Login] Erro inesperado durante login: {exc}")
            return "erro"

    def _login_etapa_email(self, email: str) -> str:
        """Etapa 1: localiza campo de e-mail, preenche e clica em Continuar.

        Args:
            email: E-mail de login (será mascarado nos logs).

        Returns:
            'ok' se e-mail enviado com sucesso.
            'campos_nao_encontrados' se o campo não apareceu em 10s.
        """
        driver = self.handler.driver
        email_mask = self._mascarar_email(email)
        logger.info("[Login Etapa 1] Aguardando campo de e-mail (até 10s)...")

        campo_email = None
        deadline = time.time() + 10
        while time.time() < deadline:
            for sel in SELECTORS_LOGIN["email"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed() and e.is_enabled():
                            campo_email = e
                            break
                except Exception:
                    continue
                if campo_email:
                    break
            if campo_email:
                break
            self._aguardar(0.8)

        if not campo_email:
            logger.aviso(
                "[Login Etapa 1] Campo de e-mail não localizado após 10s. "
                "A página de login pode não ter carregado ou o seletor mudou."
            )
            return "campos_nao_encontrados"

        logger.info(f"[Login Etapa 1] Campo localizado. Preenchendo '{email_mask}'...")
        campo_email.clear()
        self._digitar_naturalista(campo_email, email)
        time.sleep(0.3)

        logger.info("[Login Etapa 1] Clicando em 'Continuar'...")
        if self._clicar_botao_continuar():
            logger.sucesso("[Login Etapa 1] Botão clicado. Aguardando etapa de senha...")
        else:
            logger.info("[Login Etapa 1] Botão não encontrado — submetendo via Enter.")
            campo_email.send_keys(Keys.RETURN)
            logger.sucesso("[Login Etapa 1] Enter enviado. Aguardando etapa de senha...")
        return "ok"

    def _aguardar_etapa_senha(self, timeout: int = 15) -> str:
        """Aguarda a transição para a etapa de senha do login.

        Detecta a etapa 2 por três sinais alternativos (qualquer um basta):
          1. URL contém 'factor-one' ou 'factor_one'.
          2. Campo input[type='password'] visível e habilitado.
          3. Texto da página contém palavras-chave de etapa de senha.

        Args:
            timeout: Segundos máximos de espera.

        Returns:
            'ok' se etapa 2 detectada.
            'campos_nao_encontrados' se timeout atingido.
        """
        driver = self.handler.driver
        logger.info(f"[Login] Aguardando etapa de senha (até {timeout}s)...")
        deadline = time.time() + timeout

        while time.time() < deadline:
            url = driver.current_url.lower()

            if "factor-one" in url or "factor_one" in url:
                logger.info("[Login] Etapa 2 detectada via URL ('factor-one').")
                return "ok"

            for sel in SELECTORS_LOGIN["senha"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() and e.is_enabled() for e in elems):
                        logger.info("[Login] Etapa 2 detectada: campo de senha visível.")
                        return "ok"
                except Exception:
                    continue

            textos_etapa2 = [
                "insira sua senha", "enter your password",
                "digite sua senha", "your password",
            ]
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                for texto in textos_etapa2:
                    if texto in body_text:
                        logger.info(
                            f"[Login] Etapa 2 detectada via texto da página ('{texto}')."
                        )
                        return "ok"
            except Exception:
                pass

            self._aguardar(0.8)

        url_atual = driver.current_url
        logger.aviso(
            f"[Login] Timeout ({timeout}s) aguardando etapa de senha. "
            f"URL atual: {url_atual}. "
            "Causas prováveis: e-mail não foi enviado, página não redirecionou "
            "ou layout do Adapta One mudou."
        )
        return "campos_nao_encontrados"

    def _login_etapa_senha(self, senha: str) -> str:
        """Etapa 2: localiza campo de senha, preenche e clica em Continuar.

        Args:
            senha: Senha de login (nunca registrada em log).

        Returns:
            'ok' se senha enviada com sucesso.
            'campos_nao_encontrados' se o campo não apareceu em 10s.
        """
        driver = self.handler.driver
        logger.info("[Login Etapa 2] Aguardando campo de senha ficar disponível (até 10s)...")

        campo_senha = None
        deadline = time.time() + 10
        while time.time() < deadline:
            for sel in SELECTORS_LOGIN["senha"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed() and e.is_enabled():
                            campo_senha = e
                            break
                except Exception:
                    continue
                if campo_senha:
                    break
            if campo_senha:
                break
            self._aguardar(0.8)

        if not campo_senha:
            logger.aviso(
                "[Login Etapa 2] Campo de senha não localizado após 10s. "
                f"URL atual: {driver.current_url}. "
                "A transição para a etapa de senha pode não ter ocorrido."
            )
            return "campos_nao_encontrados"

        logger.info("[Login Etapa 2] Campo de senha localizado. Preenchendo...")
        campo_senha.clear()
        self._digitar_naturalista(campo_senha, senha)
        time.sleep(0.3)

        logger.info("[Login Etapa 2] Clicando em 'Continuar'...")
        if self._clicar_botao_continuar():
            logger.sucesso("[Login Etapa 2] Botão clicado. Verificando autenticação...")
        else:
            logger.info("[Login Etapa 2] Botão não encontrado — submetendo via Enter.")
            campo_senha.send_keys(Keys.RETURN)
            logger.sucesso("[Login Etapa 2] Enter enviado. Verificando autenticação...")
        return "ok"

    def _clicar_botao_continuar(self) -> bool:
        """Localiza e clica no botão submit/Continuar da etapa atual.

        Estratégia:
          1. Seletores CSS do SELECTORS_LOGIN['botao_continuar'].
          2. Fallback XPath por texto do botão (Continuar, Continue, etc.).

        Returns:
            True se o botão foi encontrado e clicado.
        """
        driver = self.handler.driver

        for sel in SELECTORS_LOGIN["botao_continuar"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        e.click()
                        return True
            except Exception:
                continue

        textos_botao = [
            "Continuar", "Continue", "Avançar", "Next",
            "Entrar", "Sign in", "Login",
        ]
        for texto in textos_botao:
            try:
                elems = driver.find_elements(
                    By.XPATH,
                    f".//button[contains(normalize-space(.), '{texto}')]",
                )
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        e.click()
                        return True
            except Exception:
                continue

        return False

    def _mascarar_email(self, email: str) -> str:
        """Retorna versão mascarada do e-mail para exibição segura em logs.

        Exemplo: 'usuario@exemplo.com' → 'us***@exemplo.com'

        Args:
            email: E-mail original.

        Returns:
            String mascarada.
        """
        if "@" not in email:
            return "***"
        local, domain = email.split("@", 1)
        visible = local[:2] if len(local) > 2 else local[:1]
        return f"{visible}***@{domain}"

    def _detectar_tela_login(self) -> bool:
        """Verifica se a página atual é de login.

        Returns:
            True se for tela de login.
        """
        for sel in SELECTORS["login_form"]:
            try:
                elems = self.handler.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    return True
            except Exception:
                continue
        url = self.handler.driver.current_url.lower()
        return "login" in url or "signin" in url or "entrar" in url
