"""
Mixin com a lógica de compositor de prompt, detecção e download de imagens.

Extraído de ``adapta_generator.py`` para isolar as responsabilidades de
interação com o campo de entrada (inserção, envio, confirmação), detecção
de imagens geradas e download do restante do gerador.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException

from bot.selectors import SELECTORS, XPATHS
from utils.logger import logger


class AdaptaImageMixin:
    """Mixin com métodos de compositor, prompt e download de imagens.

    Requer que a classe base defina:
    - ``self.handler`` (SeleniumHandler) com ``driver``
    - ``self.url_adapta`` (str)
    - ``self.timeout`` (int)
    - ``self._cancelado`` (bool)
    - ``self._aguardar(segundos)``
    - ``self._e_url_de_chat_valida(url)`` (de AdaptaChatMixin)
    """

    def _inserir_prompt_compositor(self, campo, texto: str) -> bool:
        """Insere o texto completo no compositor de forma atômica.

        Para div[contenteditable]: usa ``document.execCommand('insertText')``
        que insere o texto inteiro — incluindo quebras de linha — SEM disparar
        teclas Enter e portanto SEM fragmentar em múltiplas mensagens.

        Estratégia em cascata:
            1. ``execCommand('insertText')`` — sem efeito colateral de Enter.
            2. Manipulação direta do DOM + InputEvent — para SPAs que ignoram execCommand.
            3. ``send_keys`` com ``Shift+Enter`` para preservar \\n — somente como último recurso.

        Args:
            campo: WebElement do compositor (contenteditable, textarea ou input).
            texto: Texto completo a inserir.

        Returns:
            True se inserção foi validada, False se falhou completamente.
        """
        driver = self.handler.driver
        tag = campo.tag_name.lower()
        ce = campo.get_attribute("contenteditable") or ""
        metodo = "desconhecido"

        if ce == "true" or tag not in ("textarea", "input"):
            # --- Tentativa 1: execCommand (React/Vue disparam eventos sintéticos) ---
            try:
                resultado = driver.execute_script(
                    """
                    var el = arguments[0];
                    var txt = arguments[1];
                    el.focus();
                    document.execCommand('selectAll', false, null);
                    document.execCommand('delete', false, null);
                    return document.execCommand('insertText', false, txt);
                    """,
                    campo, texto,
                )
                if resultado:
                    metodo = "execCommand(insertText)"
                else:
                    raise RuntimeError("execCommand retornou false")
            except Exception as e1:
                logger.aviso(
                    f"[Composer] execCommand falhou ({e1}) "
                    f"— tentando DOM+InputEvent"
                )
                # --- Tentativa 2: DOM direto + InputEvent ---
                try:
                    driver.execute_script(
                        """
                        var el = arguments[0];
                        var txt = arguments[1];
                        el.innerHTML = '';
                        el.focus();
                        var tn = document.createTextNode(txt);
                        el.appendChild(tn);
                        el.dispatchEvent(new InputEvent('input', {
                            inputType: 'insertText',
                            data: txt,
                            bubbles: true,
                            cancelable: false
                        }));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        """,
                        campo, texto,
                    )
                    metodo = "DOM+InputEvent"
                except Exception as e2:
                    logger.aviso(
                        f"[Composer] DOM+InputEvent falhou ({e2}) "
                        f"— usando send_keys com Shift+Enter para multiline"
                    )
                    # --- Tentativa 3: send_keys com Shift+Enter (sem fragmentar) ---
                    try:
                        self._limpar_campo_compositor(campo)
                        linhas = texto.split("\n")
                        for i, linha in enumerate(linhas):
                            if i > 0:
                                campo.send_keys(Keys.SHIFT + Keys.RETURN)
                            campo.send_keys(linha)
                        metodo = "send_keys+Shift+Enter"
                    except Exception as e3:
                        logger.erro(
                            f"[Composer] Todas as tentativas de inserção falharam: {e3}"
                        )
                        return False
        else:
            # textarea / input: setter nativo React + disparar eventos
            try:
                driver.execute_script(
                    """
                    var el = arguments[0];
                    var v = arguments[1];
                    var tag = el.tagName.toLowerCase();
                    var proto = tag === 'textarea'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    var setter = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (setter && setter.set) {
                        setter.set.call(el, v);
                    } else {
                        el.value = v;
                    }
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    """,
                    campo, texto,
                )
                metodo = "JS-nativeSetter"
            except Exception as exc:
                logger.aviso(f"[Composer] JS setter falhou ({exc}) — send_keys")
                try:
                    campo.send_keys(Keys.CONTROL + "a")
                    campo.clear()
                    campo.send_keys(texto)
                    metodo = "send_keys"
                except Exception as exc2:
                    logger.erro(f"[Composer] send_keys falhou: {exc2}")
                    return False

        # Validação pós-inserção
        try:
            if ce == "true" or tag not in ("textarea", "input"):
                conteudo = driver.execute_script(
                    "return (arguments[0].innerText "
                    "|| arguments[0].textContent || '').trim();",
                    campo,
                ) or ""
            else:
                conteudo = (campo.get_attribute("value") or "").strip()

            c_esp = len(texto.strip())
            c_obt = len(conteudo)
            logger.info(
                f"[Composer] Inserção '{metodo}': "
                f"{c_obt}/{c_esp} chars no campo."
            )
            return c_obt >= int(c_esp * 0.85)
        except Exception:
            logger.info(f"[Composer] Inserção '{metodo}': validação indisponível — assumindo OK.")
            return True

    def _contar_mensagens_usuario(self) -> int:
        """Conta os elementos de mensagem do usuário visíveis no DOM do chat.

        Tenta vários seletores comuns em SPAs de chat. Retorna o maior
        valor encontrado entre os seletores — evita subcontagem.

        Returns:
            Número inteiro de mensagens do usuário (0 se nenhuma/erro).
        """
        driver = self.handler.driver
        seletores = [
            "[data-role='user']",
            "[data-message-role='user']",
            "[data-author-role='user']",
            ".user-message",
            ".human-message",
            "[class*='user-message' i]",
            "[class*='human-message' i]",
            "[class*='user-bubble' i]",
            "[class*='outgoing' i]",
        ]
        maximo = 0
        for sel in seletores:
            try:
                n = len(driver.find_elements(By.CSS_SELECTOR, sel))
                if n > maximo:
                    maximo = n
            except Exception:
                continue
        return maximo

    def _confirmar_envio_real(
        self,
        campo,
        texto_inserido: str,
        timeout_s: float = 5.0,
        arte_label: str = "Arte",
    ) -> bool:
        """Confirma que o prompt foi realmente enviado ao chat.

        Verifica três sinais independentes, em polling até ``timeout_s``:

        - **Sinal A (primário)**: campo do compositor está vazio/limpo.
          Em quase todos os SPAs de chat, o campo é zerado imediatamente
          após o envio bem-sucedido.
        - **Sinal B (secundário)**: indicador de loading/geração apareceu,
          o que implica que a resposta foi acionada.
        - **Sinal C (terciário)**: a contagem de mensagens do usuário no
          DOM aumentou — nova mensagem ficou visível no histórico.

        Retorna ``True`` assim que qualquer sinal for confirmado, sem
        esperar os outros. Retorna ``False`` apenas se o timeout expirar
        sem nenhum sinal positivo E o texto ainda estiver no campo.

        Args:
            campo: WebElement do compositor.
            texto_inserido: Texto enviado (para log de diagnóstico).
            timeout_s: Tempo máximo de espera em segundos.
            arte_label: Rótulo para log (ex: 'Arte 2/3').

        Returns:
            True se envio confirmado, False caso contrário.
        """
        driver = self.handler.driver
        n_msgs_antes = self._contar_mensagens_usuario()
        inicio = time.time()

        while time.time() - inicio < timeout_s:
            # ── Sinal A: campo vazio ──
            try:
                conteudo = driver.execute_script(
                    "var e = arguments[0];"
                    "return (e.innerText || e.textContent || e.value || '').trim();",
                    campo,
                ) or ""
                if len(conteudo) < 5:
                    logger.info(
                        f"[Envio] {arte_label}: ✓ campo vazio após envio "
                        f"(sinal A — primário)."
                    )
                    return True
            except StaleElementReferenceException:
                logger.info(
                    f"[Envio] {arte_label}: ✓ campo substituído pelo SPA "
                    f"(StaleElement — sinal A implícito)."
                )
                return True
            except Exception:
                pass

            # ── Sinal B: loading/geração iniciou ──
            for sel in SELECTORS["indicador_carregando"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        logger.info(
                            f"[Envio] {arte_label}: ✓ loading detectado "
                            f"(sinal B — secundário)."
                        )
                        return True
                except Exception:
                    continue

            # ── Sinal C: nova mensagem do usuário no DOM ──
            n_msgs_agora = self._contar_mensagens_usuario()
            if n_msgs_agora > n_msgs_antes:
                logger.info(
                    f"[Envio] {arte_label}: ✓ nova mensagem do usuário detectada "
                    f"({n_msgs_antes} → {n_msgs_agora}) (sinal C — terciário)."
                )
                return True

            time.sleep(0.4)

        # ── Avaliação final ──
        try:
            conteudo_final = driver.execute_script(
                "var e = arguments[0];"
                "return (e.innerText || e.textContent || e.value || '').trim();",
                campo,
            ) or ""
        except StaleElementReferenceException:
            logger.info(
                f"[Envio] {arte_label}: ✓ campo destruído após timeout "
                f"(StaleElement — confirmação final)."
            )
            return True
        except Exception:
            conteudo_final = ""

        texto_no_campo = len(conteudo_final) > 5
        logger.aviso(
            f"[Envio] {arte_label}: texto ainda no campo após {timeout_s:.0f}s? "
            f"{'SIM' if texto_no_campo else 'não'} "
            f"({len(conteudo_final)} chars). "
            f"Envio {'NÃO confirmado' if texto_no_campo else 'provavelmente OK (campo vazio)'}."
        )
        return not texto_no_campo

    def _enviar_via_enter_confirmado(
        self,
        campo,
        texto_inserido: str,
        arte_label: str,
        max_tentativas: int = 3,
    ) -> bool:
        """Tenta enviar via Enter com validação de foco e confirmação real.

        Para cada tentativa:
        1. Verifica se o campo ainda é o ``activeElement``.
        2. Se não, refoca via click + JS focus.
        3. Verifica se o texto ainda está no campo (pode já ter sido enviado).
        4. Envia ``Keys.RETURN``.
        5. Chama ``_confirmar_envio_real`` — só retorna True com prova.

        Args:
            campo: WebElement do compositor.
            texto_inserido: Texto a verificar no campo.
            arte_label: Rótulo para log.
            max_tentativas: Número máximo de tentativas de Enter.

        Returns:
            True se envio confirmado em alguma tentativa, False caso contrário.
        """
        driver = self.handler.driver

        for tentativa in range(1, max_tentativas + 1):
            # ── Verificar se campo ainda é o elemento ativo ──
            try:
                eh_ativo = driver.execute_script(
                    "return document.activeElement === arguments[0];", campo
                )
            except StaleElementReferenceException:
                logger.info(
                    f"[Envio] {arte_label}: campo substituído pelo SPA antes do Enter "
                    f"(tentativa {tentativa}) — assumindo envio OK."
                )
                return True
            except Exception:
                eh_ativo = False

            logger.info(
                f"[Envio] {arte_label}: composer focado? "
                f"{'sim' if eh_ativo else 'não'} "
                f"(tentativa Enter {tentativa}/{max_tentativas})."
            )

            if not eh_ativo:
                logger.info(
                    f"[Envio] {arte_label}: recuperando foco antes do Enter..."
                )
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});"
                        "arguments[0].click();"
                        "arguments[0].focus();",
                        campo,
                    )
                    time.sleep(0.3)
                    eh_ativo = driver.execute_script(
                        "return document.activeElement === arguments[0];", campo
                    )
                    logger.info(
                        f"[Envio] {arte_label}: foco recuperado? "
                        f"{'sim' if eh_ativo else 'NÃO'}."
                    )
                except StaleElementReferenceException:
                    logger.info(
                        f"[Envio] {arte_label}: StaleElement ao refocusar — "
                        f"SPA recriou o campo, assumindo envio já ocorreu."
                    )
                    return True
                except Exception as exc:
                    logger.aviso(
                        f"[Envio] {arte_label}: falha ao recuperar foco: {exc}"
                    )

            # ── Verificar se texto ainda está no campo ──
            try:
                conteudo = driver.execute_script(
                    "var e = arguments[0];"
                    "return (e.innerText || e.textContent || e.value || '').trim();",
                    campo,
                ) or ""
                texto_no_campo = len(conteudo) > 5
            except StaleElementReferenceException:
                logger.info(
                    f"[Envio] {arte_label}: StaleElement ao verificar conteúdo — "
                    f"campo destruído, envio provavelmente ocorreu."
                )
                return True
            except Exception:
                texto_no_campo = True
                conteudo = ""

            logger.info(
                f"[Envio] {arte_label}: texto no campo? "
                f"{'sim' if texto_no_campo else 'não'} "
                f"({len(conteudo)} chars)."
            )

            if not texto_no_campo:
                logger.info(
                    f"[Envio] {arte_label}: campo já vazio antes do Enter "
                    f"— envio ocorreu em tentativa anterior."
                )
                return True

            # ── Enviar Enter ──
            logger.info(
                f"[Envio] {arte_label}: enviando Enter "
                f"(tentativa {tentativa}/{max_tentativas})..."
            )
            try:
                campo.send_keys(Keys.RETURN)
            except StaleElementReferenceException:
                logger.info(
                    f"[Envio] {arte_label}: StaleElement no send_keys — "
                    f"campo recriado após Enter, provável envio bem-sucedido."
                )
                return True
            except Exception as exc:
                logger.aviso(
                    f"[Envio] {arte_label}: send_keys(Enter) falhou ({exc}) "
                    f"— tentando KeyboardEvent via JS."
                )
                try:
                    driver.execute_script(
                        "arguments[0].dispatchEvent(new KeyboardEvent('keydown',{"
                        "key:'Enter',code:'Enter',keyCode:13,which:13,"
                        "bubbles:true,cancelable:true}));",
                        campo,
                    )
                except Exception:
                    pass

            logger.info(
                f"[Envio] {arte_label}: Enter enviado. Aguardando confirmação..."
            )
            confirmado = self._confirmar_envio_real(
                campo, texto_inserido, timeout_s=5.0, arte_label=arte_label
            )
            if confirmado:
                return True

            logger.aviso(
                f"[Envio] {arte_label}: tentativa {tentativa}/{max_tentativas} "
                f"de Enter não confirmou envio."
            )
            if tentativa < max_tentativas:
                self._aguardar(1.0)

        logger.erro(
            f"[Envio] {arte_label}: todas as {max_tentativas} tentativas de Enter "
            f"falharam. Prompt pode estar parado no composer."
        )
        return False

    def _enviar_prompt_compositor(self, campo, texto_inserido: str = "", arte_label: str = "Arte") -> Tuple[str, bool]:
        """Envia o prompt digitado no compositor. Retorna (método, confirmado).

        Fluxo:
        1. Busca botão de envio (3s) → clica → ``_confirmar_envio_real``.
        2. Se botão não encontrado ou confirmação falhou:
           → ``_enviar_via_enter_confirmado`` (valida foco, Enter, confirma).
        3. Retorna ``(método_usado, envio_confirmado)``.

        Nunca retorna ``True`` sem prova concreta de envio.

        Args:
            campo: WebElement do compositor (para fallback Enter).
            texto_inserido: Texto que foi inserido (para confirmação).
            arte_label: Rótulo para log (ex: 'Arte 2/3').

        Returns:
            Tupla ``(str, bool)`` — método e se envio foi confirmado.
        """
        driver = self.handler.driver
        t_ini = time.time()

        # ── Tentativa 1: Botão de envio ──
        logger.info(f"[Envio] {arte_label}: tentativa de envio via botão iniciada.")
        botao = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            botao = self._localizar_botao_gerar()
            if botao:
                break
            self._aguardar(0.5)

        t_busca = time.time() - t_ini

        if botao:
            logger.info(
                f"[Envio] {arte_label}: botão encontrado em {t_busca:.1f}s. Clicando..."
            )
            try:
                driver.execute_script("arguments[0].click();", botao)
            except Exception:
                try:
                    botao.click()
                except Exception as exc_click:
                    logger.aviso(
                        f"[Envio] {arte_label}: clique no botão falhou: {exc_click}"
                    )

            logger.info(
                f"[Envio] {arte_label}: botão clicado. Aguardando confirmação de envio..."
            )
            confirmado = self._confirmar_envio_real(
                campo, texto_inserido, timeout_s=5.0, arte_label=arte_label
            )
            if confirmado:
                logger.info(f"[Envio] {arte_label}: envio confirmado via botão.")
                return "botao", True

            logger.aviso(
                f"[Envio] {arte_label}: botão clicado mas envio NÃO confirmado "
                f"— caindo para fallback Enter."
            )
        else:
            logger.info(
                f"[Envio] {arte_label}: botão não encontrado após {t_busca:.1f}s "
                f"— usando Enter como fallback."
            )

        # ── Tentativa 2: Enter com validação de foco e confirmação ──
        logger.info(f"[Envio] {arte_label}: tentativa de envio via Enter iniciada.")
        confirmado = self._enviar_via_enter_confirmado(
            campo, texto_inserido, arte_label, max_tentativas=3
        )
        return "enter", confirmado

    def _localizar_campo_prompt(self):
        """Localiza o campo de texto de prompt na página.

        Atalho legado — usa `_aguardar_compositor` internamente com timeout curto.
        Mantido para compatibilidade com código externo.

        Returns:
            WebElement do campo ou None.
        """
        return self._aguardar_compositor(timeout_s=5)

    def _aguardar_compositor(self, timeout_s: int = 15) -> Optional[object]:
        """Aguarda e retorna o campo de entrada do compositor do chat.

        Estratégia em 3 rodadas progressivamente mais permissivas:

        - **padrao** (0% a 40% do timeout): heurística padrão, threshold=0.
          Penaliza levemente header/sidebar/rename. Não penaliza 'title'
          quando já estamos em URL de chat ativo.
        - **relaxado** (40% a 75% do timeout): penalidades mínimas (só
          header/sidebar reais). Threshold=-5.
        - **fallback** (>75% do timeout): sem penalidades. Retorna qualquer
          candidato visível. Se ainda assim scoring falhar, testa
          funcionalmente cada contenteditable com click+focus.

        Args:
            timeout_s: Tempo máximo de espera total em segundos.

        Returns:
            WebElement do compositor ou None se não encontrado.
        """
        inicio = time.time()
        deadline = inicio + timeout_s
        tentativa = 0

        while time.time() < deadline:
            tentativa += 1
            decorrido = time.time() - inicio
            restante = deadline - time.time()

            if timeout_s >= 8:
                if decorrido < timeout_s * 0.40:
                    modo = "padrao"
                elif decorrido < timeout_s * 0.75:
                    modo = "relaxado"
                else:
                    modo = "fallback"
            else:
                modo = "padrao" if decorrido < timeout_s * 0.6 else "fallback"

            candidatos = self._coletar_candidatos_compositor()

            if not candidatos:
                logger.info(
                    f"[Composer] Tentativa {tentativa} ({modo}): "
                    f"0 candidatos visíveis — aguardando... ({restante:.0f}s)"
                )
                self._aguardar(2.0)
                continue

            melhor = self._escolher_melhor_compositor(candidatos, modo=modo)

            if melhor is not None:
                tag = melhor.tag_name
                ce = melhor.get_attribute("contenteditable") or ""
                tipo = f"{tag}[contenteditable=true]" if ce == "true" else tag
                logger.info(
                    f"[Composer] Compositor resolvido: tipo='{tipo}', "
                    f"modo='{modo}', tentativa={tentativa}."
                )
                return melhor

            if restante > 2:
                logger.info(
                    f"[Composer] Tentativa {tentativa} ({modo}): "
                    f"nenhum candidato aprovado. {restante:.0f}s restantes."
                )
            self._aguardar(2.0)

        self._logar_diagnostico_compositor()

        # Último recurso: teste funcional direto em cada contenteditable visível
        logger.aviso(
            "[Composer] Timeout atingido. Tentando teste funcional direto "
            "em candidatos contenteditable..."
        )
        try:
            driver = self.handler.driver
            ces = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
            for ce_elem in ces:
                try:
                    if ce_elem.is_displayed() and ce_elem.is_enabled():
                        if self._verificar_foco_funcional(ce_elem):
                            logger.sucesso(
                                "[Composer] Compositor encontrado via teste funcional direto."
                            )
                            return ce_elem
                except Exception:
                    continue
        except Exception:
            pass

        return None

    def _coletar_candidatos_compositor(self) -> list:
        """Coleta todos os campos editáveis visíveis e habilitados da página.

        Busca por: div[contenteditable], textarea, input[type=text].

        Returns:
            Lista de WebElements visíveis e habilitados.
        """
        driver = self.handler.driver
        candidatos = []
        seletores = [
            "div[contenteditable='true']",
            "p[contenteditable='true']",
            "[contenteditable='true']",
            "textarea",
            "input[type='text']",
        ]
        for sel in seletores:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            candidatos.append(elem)
                    except Exception:
                        continue
            except Exception:
                continue
        return candidatos

    def _escolher_melhor_compositor(
        self, candidatos: list, modo: str = "padrao"
    ) -> Optional[object]:
        """Escolhe o melhor candidato a compositor de chat entre os disponíveis.

        Usa pontuação por contexto com três modos progressivamente mais
        permissivos. Penalidades são sempre **sinais fracos**, nunca vetos
        absolutos. O URL atual é o sinal mais forte de que estamos em um
        chat ativo e qualquer contenteditable visível provavelmente é o
        compositor correto.

        Pontuação:
          +20  URL atual é de chat válido (sinal primário)
          +25  ancestral contém chat/message/composer/editor/input
          +15  botão de envio visível próximo
          +12  campo na metade inferior da viewport
          + 5  campo no terço central da viewport
          +10  largura > 300px | +5 largura > 150px
          + 5  altura > 30px
          + 5  tag contenteditable | +3 tag textarea
          − 8  ancestral é header/sidebar (modo=padrao)
          − 5  ancestral contém 'title'/'nav' (apenas se não em chat ativo)
          − 4  ancestral é header/sidebar (modo=relaxado)
          modo=fallback: sem penalidades, aceita qualquer candidato visível

        Args:
            candidatos: Lista de WebElements visíveis e habilitados.
            modo: 'padrao' | 'relaxado' | 'fallback'

        Returns:
            WebElement escolhido, ou None se melhor_score < threshold.
        """
        driver = self.handler.driver

        try:
            url_atual = driver.current_url
            em_chat_ativo = self._e_url_de_chat_valida(url_atual)
        except Exception:
            em_chat_ativo = False

        def _pontuar_detalhado(elem) -> tuple:
            score = 0
            detalhes = {}
            try:
                tag = elem.tag_name.lower()
                ce = elem.get_attribute("contenteditable") or ""

                if ce == "true":
                    score += 5
                    detalhes["ce"] = "+5"
                elif tag == "textarea":
                    score += 3
                    detalhes["textarea"] = "+3"

                if em_chat_ativo:
                    score += 20
                    detalhes["url_chat"] = "+20"

                anc_pos = (
                    "./ancestor::*["
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'message') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'composer') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'editor') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'input') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'message') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'composer')"
                    "]"
                )
                if elem.find_elements(By.XPATH, anc_pos):
                    score += 25
                    detalhes["anc_pos"] = "+25"

                if modo == "padrao":
                    anc_neg_strict = (
                        "./ancestor::*["
                        "self::header or self::nav or "
                        "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sidebar') or "
                        "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'rename')"
                        "]"
                    )
                    if elem.find_elements(By.XPATH, anc_neg_strict):
                        score -= 8
                        detalhes["anc_neg_strict"] = "-8"

                    if not em_chat_ativo:
                        anc_neg_title = (
                            "./ancestor::*["
                            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'title') or "
                            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'nav')"
                            "]"
                        )
                        if elem.find_elements(By.XPATH, anc_neg_title):
                            score -= 5
                            detalhes["anc_neg_title"] = "-5"

                elif modo == "relaxado":
                    anc_neg_min = (
                        "./ancestor::*["
                        "self::header or "
                        "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sidebar')"
                        "]"
                    )
                    if elem.find_elements(By.XPATH, anc_neg_min):
                        score -= 4
                        detalhes["anc_neg_min"] = "-4"

                botoes = elem.find_elements(
                    By.XPATH,
                    "./following-sibling::button | "
                    "./preceding-sibling::button | "
                    "./parent::*/following-sibling::*//button | "
                    "./parent::*/child::button",
                )
                if any(b.is_displayed() for b in botoes):
                    score += 15
                    detalhes["botao_proximo"] = "+15"

                rect = driver.execute_script(
                    "var r=arguments[0].getBoundingClientRect();"
                    "return {top:r.top,width:r.width,height:r.height};",
                    elem,
                )
                vh = driver.execute_script("return window.innerHeight;")
                if rect and vh:
                    topo = rect.get("top", 0)
                    larg = rect.get("width", 0)
                    alt = rect.get("height", 0)
                    if topo > vh * 0.5:
                        score += 12
                        detalhes["pos_inferior"] = f"+12(top={topo:.0f})"
                    elif topo > vh * 0.3:
                        score += 5
                        detalhes["pos_centro"] = f"+5(top={topo:.0f})"
                    if larg > 300:
                        score += 10
                        detalhes["campo_largo"] = f"+10(w={larg:.0f})"
                    elif larg > 150:
                        score += 5
                        detalhes["campo_medio"] = f"+5(w={larg:.0f})"
                    if alt > 30:
                        score += 5
                        detalhes["campo_alto"] = f"+5(h={alt:.0f})"
            except Exception as exc:
                detalhes["exc"] = str(exc)[:60]
            return score, detalhes

        pontuados = []
        for c in candidatos:
            try:
                s, d = _pontuar_detalhado(c)
                pontuados.append((s, d, c))
            except Exception:
                pontuados.append((0, {}, c))

        if not pontuados:
            return None

        pontuados.sort(key=lambda x: x[0], reverse=True)

        for i, (s, d, c) in enumerate(pontuados):
            tag = c.tag_name
            ce = c.get_attribute("contenteditable") or ""
            tipo = f"{tag}[ce=true]" if ce == "true" else tag
            det_str = ", ".join(f"{k}:{v}" for k, v in d.items()) or "sem_bonus"
            logger.info(
                f"[Composer] [{modo}] Cand {i+1}/{len(pontuados)}: "
                f"tipo={tipo}, score={s} | {det_str}"
            )

        melhor_score, _, melhor = pontuados[0]

        if modo == "fallback":
            logger.info(
                f"[Composer] Fallback: aceitando melhor candidato "
                f"disponível (score={melhor_score})."
            )
            return melhor

        threshold = -5 if modo == "relaxado" else 0
        if melhor_score >= threshold:
            return melhor

        logger.info(
            f"[Composer] [{modo}] Melhor score={melhor_score} < threshold={threshold}. "
            f"Nenhum candidato aprovado nesta rodada."
        )
        return None

    def _limpar_campo_compositor(self, campo) -> None:
        """Limpa o conteúdo do campo de entrada do compositor.

        Trata corretamente tanto textarea/input quanto div[contenteditable].
        Para contenteditable, o método `clear()` do Selenium não funciona —
        é necessário usar JS e/ou combinações de teclas.

        Args:
            campo: WebElement do compositor.
        """
        driver = self.handler.driver
        tag = campo.tag_name.lower()
        ce = campo.get_attribute("contenteditable") or ""

        if ce == "true" or tag not in ("textarea", "input"):
            try:
                driver.execute_script("arguments[0].innerHTML = '';", campo)
                time.sleep(0.1)
            except Exception:
                pass
            try:
                campo.send_keys(Keys.CONTROL + "a")
                time.sleep(0.1)
                campo.send_keys(Keys.DELETE)
                time.sleep(0.1)
            except Exception:
                pass
        else:
            try:
                campo.send_keys(Keys.CONTROL + "a")
                time.sleep(0.2)
                campo.clear()
                time.sleep(0.1)
            except Exception:
                pass

    def _logar_diagnostico_compositor(self) -> None:
        """Emite log diagnóstico detalhado quando o compositor não é encontrado.

        Informa URL atual, título da página, quantidade de candidatos
        encontrados por seletor e se cada um estava visível/habilitado.
        Útil para depuração sem precisar de screenshot.
        """
        driver = self.handler.driver
        try:
            logger.aviso(
                f"[Composer][Diagnóstico] URL atual: {driver.current_url}"
            )
            logger.aviso(
                f"[Composer][Diagnóstico] Título da página: {driver.title}"
            )
        except Exception:
            pass

        seletores_diag = [
            "div[contenteditable='true']",
            "[contenteditable='true']",
            "textarea",
            "input[type='text']",
        ]
        for sel in seletores_diag:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                visiveis = sum(1 for e in elems if e.is_displayed())
                logger.aviso(
                    f"[Composer][Diagnóstico] '{sel}': "
                    f"{len(elems)} elemento(s), {visiveis} visível(is)."
                )
            except Exception:
                logger.aviso(f"[Composer][Diagnóstico] '{sel}': erro ao buscar.")

    def _verificar_foco_funcional(self, campo) -> bool:
        """Testa se um elemento aceita foco real via click + JS focus.

        Usado como teste final antes de descartar um candidato a compositor.
        Verifica se `document.activeElement` corresponde ao elemento após
        o foco, confirmando que ele está interativo e não apenas decorativo.

        Args:
            campo: WebElement candidato.

        Returns:
            True se o elemento ficou ativo após foco.
        """
        driver = self.handler.driver
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", campo
            )
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", campo)
            time.sleep(0.2)
            driver.execute_script("arguments[0].focus();", campo)
            time.sleep(0.2)
            eh_ativo = driver.execute_script(
                "return document.activeElement === arguments[0];", campo
            )
            if eh_ativo:
                logger.info(
                    f"[Composer] Teste funcional OK: "
                    f"tag='{campo.tag_name}' ficou ativo após focus."
                )
                return True
            logger.aviso(
                f"[Composer] Teste funcional FALHOU: "
                f"tag='{campo.tag_name}' não ficou ativo após focus "
                f"(activeElement é outro)."
            )
            return False
        except Exception as exc:
            logger.aviso(f"[Composer] Teste funcional ERRO: {exc}")
            return False

    def _aguardar_fim_rename(self, timeout_s: int = 8) -> None:
        """Aguarda o input temporário de rename desaparecer após criação de chat.

        Após pressionar Enter no campo de título, o Adapta One pode demorar
        um momento para remover o input temporário e exibir o compositor
        principal. Esta função aguarda até o input[autofocus] sumir ou até
        o timeout.

        Args:
            timeout_s: Tempo máximo de espera em segundos.
        """
        driver = self.handler.driver
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                autofocus = driver.find_elements(
                    By.CSS_SELECTOR, "input[autofocus]"
                )
                visiveis = [e for e in autofocus if e.is_displayed()]
                if not visiveis:
                    logger.info(
                        "[Chat] Input de rename não mais visível — "
                        "UI estabilizada para envio de prompt."
                    )
                    return
            except Exception:
                pass
            time.sleep(0.5)
        logger.aviso(
            "[Chat] Input de rename ainda presente após timeout de "
            f"{timeout_s}s — continuando mesmo assim."
        )

    def _localizar_botao_gerar(self):
        """Localiza o botão de geração na página.

        Returns:
            WebElement do botão ou None.
        """
        driver = self.handler.driver
        for xpath in XPATHS["botao_gerar"]:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except Exception:
                continue
        for sel in SELECTORS["botao_gerar"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except Exception:
                continue
        return None

    def _digitar_naturalista(self, elemento, texto: str, delay_min: float = 0.03, delay_max: float = 0.09) -> None:
        """Digita texto com atraso variável entre teclas, simulando humano.

        Args:
            elemento: WebElement alvo.
            texto: Texto a digitar.
            delay_min: Atraso mínimo entre teclas (segundos).
            delay_max: Atraso máximo entre teclas (segundos).
        """
        for char in texto:
            elemento.send_keys(char)
            time.sleep(random.uniform(delay_min, delay_max))

    def _aguardar_e_baixar(
        self,
        downloader,
        nome_arquivo: str,
        snapshot_antes: Optional[set] = None,
        urls_baixadas: Optional[set] = None,
        numero_arte: int = 0,
        total_artes: int = 0,
    ) -> Optional[Path]:
        """Aguarda a imagem gerada e baixa APENAS a imagem nova desta arte.

        Compara o estado do DOM contra o snapshot tirado antes do envio.
        Só considera imagens cujas URLs não estejam em ``snapshot_antes``
        nem em ``urls_baixadas`` — eliminando duplicatas entre artes.

        Args:
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.
            snapshot_antes: URLs de imagens presentes antes do envio.
            urls_baixadas: Conjunto compartilhado de URLs já baixadas no ciclo.
            numero_arte: Número desta arte (para log).
            total_artes: Total de artes (para log).

        Returns:
            Path do arquivo ou None.
        """
        from selenium.common.exceptions import TimeoutException
        driver = self.handler.driver
        inicio = time.time()
        _snapshot = snapshot_antes if snapshot_antes is not None else set()
        _baixadas = urls_baixadas if urls_baixadas is not None else set()
        arte_label = f"Arte {numero_arte}/{total_artes}" if numero_arte else "Arte"

        vistas: set = _snapshot | _baixadas

        alguma_nova_detectada = False
        algum_download_tentado = False

        logger.info(
            f"[Download] {arte_label}: snapshot antes={len(_snapshot)}, "
            f"já baixadas={len(_baixadas)}. Aguardando imagem nova..."
        )

        while time.time() - inicio < self.timeout:
            if self._cancelado:
                return None

            self._aguardar_fim_loading(driver, espera_max=5)

            novas = self._coletar_novas_imagens(vistas)

            snap_atual = len(vistas)
            logger.info(
                f"[Download] {arte_label}: snapshot após envio={snap_atual + len(novas)} imgs "
                f"({len(novas)} nova(s) detectada(s))."
            )

            for url_nova in novas:
                alguma_nova_detectada = True
                id_log = url_nova[:80] + ("..." if len(url_nova) > 80 else "")
                if url_nova in _baixadas:
                    logger.info(
                        f"[Download] {arte_label}: imagem ignorada por já ter sido "
                        f"processada — {id_log}"
                    )
                    vistas.add(url_nova)
                    continue

                logger.info(
                    f"[Download] {arte_label}: imagem selecionada para download — {id_log}"
                )
                algum_download_tentado = True
                arquivo = downloader.baixar_de_url(url_nova, nome_arquivo)
                if arquivo and downloader.verificar_arquivo(arquivo):
                    _baixadas.add(url_nova)
                    logger.sucesso(
                        f"[Download] {arte_label}: download concluído. "
                        f"URL registrada para deduplicação."
                    )
                    return arquivo

                logger.aviso(
                    f"[Download] {arte_label}: falha ao baixar {id_log}. Tentando próxima."
                )
                vistas.add(url_nova)

            arquivo = self._tentar_baixar_via_js_novo(downloader, nome_arquivo, vistas)
            if arquivo and downloader.verificar_arquivo(arquivo):
                logger.sucesso(
                    f"[Download] {arte_label}: download concluído via fallback JS."
                )
                return arquivo

            time.sleep(2)

        if not alguma_nova_detectada:
            msg_estado = (
                f"[Download] {arte_label}: ESTADO 2 — envio confirmado, "
                f"mas nenhuma imagem nova apareceu em {self.timeout}s. "
                f"A resposta do Adapta pode ter demorado além do timeout, "
                f"ou a imagem usa formato/seletor não detectado."
            )
        elif algum_download_tentado:
            msg_estado = (
                f"[Download] {arte_label}: ESTADO 4 — imagem(ns) detectada(s) "
                f"mas todos os downloads falharam (URL inacessível ou arquivo inválido)."
            )
        else:
            msg_estado = (
                f"[Download] {arte_label}: ESTADO 3 — resposta chegou, "
                f"imagem foi detectada mas filtros de dedup/URL a rejeitaram. "
                f"Verifique se a URL da imagem é nova ou se foi deduplicada incorretamente."
            )

        from selenium.common.exceptions import TimeoutException as _TE
        raise _TE(msg_estado)

    def _tirar_snapshot_imagens(self) -> set:
        """Captura as URLs HTTP de todas as imagens visíveis no momento.

        Usado para estabelecer o baseline antes de enviar o prompt.
        Qualquer URL ausente neste snapshot após o envio é candidata
        à imagem gerada pela arte atual.

        Returns:
            Conjunto de strings de URL (``http://...``).
        """
        driver = self.handler.driver
        try:
            resultado = driver.execute_script(
                """
                var urls = [];
                document.querySelectorAll('img').forEach(function(img) {
                    if (img.naturalWidth > 100 && img.naturalHeight > 100
                            && img.src && img.src.indexOf('http') === 0
                            && img.offsetWidth > 0) {
                        urls.push(img.src);
                    }
                });
                return urls;
                """
            ) or []
            return set(resultado)
        except Exception:
            return set()

    def _coletar_novas_imagens(self, vistas: set) -> list:
        """Retorna URLs HTTP de imagens visíveis não presentes em ``vistas``.

        Varre todo o DOM por ``<img>`` com naturalWidth > 100 e src HTTP.
        Exclui qualquer URL já presente em ``vistas`` (snapshot + baixadas).

        Args:
            vistas: Conjunto de URLs já conhecidas (não devem ser baixadas).

        Returns:
            Lista ordenada (DOM order) de URLs novas.
        """
        driver = self.handler.driver
        try:
            todas = driver.execute_script(
                """
                var urls = [];
                document.querySelectorAll('img').forEach(function(img) {
                    if (img.naturalWidth > 100 && img.naturalHeight > 100
                            && img.src && img.src.indexOf('http') === 0
                            && img.offsetWidth > 0) {
                        urls.push(img.src);
                    }
                });
                return urls;
                """
            ) or []
            return [u for u in todas if u not in vistas]
        except Exception:
            return []

    def _tentar_baixar_via_js_novo(
        self,
        downloader,
        nome_arquivo: str,
        urls_excluidas: set,
    ) -> Optional[Path]:
        """Fallback JS para canvas e data URIs ignorados pela varredura HTTP.

        Percorre canvas e img[src^='data:image'] em ordem reversa (mais novo
        primeiro) e baixa o primeiro que não esteja em ``urls_excluidas``.

        Args:
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.
            urls_excluidas: URLs que já foram processadas — não baixar novamente.

        Returns:
            Path do arquivo salvo ou None.
        """
        driver = self.handler.driver
        try:
            script = """
            var excluidas = arguments[0];
            // Canvas (mais recente primeiro)
            var canvases = document.querySelectorAll('canvas');
            for (var i = canvases.length - 1; i >= 0; i--) {
                if (canvases[i].offsetWidth < 100) continue;
                try {
                    var dataUrl = canvases[i].toDataURL('image/jpeg', 0.95);
                    if (excluidas.indexOf(dataUrl.substring(0, 100)) === -1) {
                        return dataUrl;
                    }
                } catch(e) {}
            }
            // Imagens data: URI
            var imgs = document.querySelectorAll('img[src^="data:image"]');
            for (var j = imgs.length - 1; j >= 0; j--) {
                if (imgs[j].naturalWidth > 200 && imgs[j].naturalHeight > 200) {
                    var src = imgs[j].src;
                    if (excluidas.indexOf(src.substring(0, 100)) === -1) {
                        return src;
                    }
                }
            }
            return null;
            """
            excluidas_prefixos = [u[:100] for u in urls_excluidas]
            resultado = driver.execute_script(script, excluidas_prefixos)
            if resultado and resultado.startswith("data:image"):
                return downloader._salvar_base64(
                    resultado, downloader.pasta_output / nome_arquivo
                )
        except Exception:
            pass
        return None

    def _aguardar_estabilizacao_spa(
        self, arte_label: str = "Arte", timeout_s: int = 8
    ) -> None:
        """Aguarda a SPA estabilizar entre artes (C9).

        Após o download de uma arte, o Adapta One pode re-renderizar a UI:
        criar novo estado de chat, recriar o compositor, atualizar o
        histórico. Enviar a próxima arte enquanto isso ocorre causa perda de
        foco, botão de envio não encontrado e Enter sem efeito.

        Verifica:
        1. Indicadores de loading desapareceram.
        2. URL não mudou nos últimos 1s (navegação SPA se estabilizou).
        3. Breve pausa fixa para permitir reconciliação do React/DOM.

        Args:
            arte_label: Rótulo para log.
            timeout_s: Tempo máximo de espera.
        """
        driver = self.handler.driver
        logger.info(
            f"[SPA] {arte_label}: aguardando estabilização da UI antes da próxima arte..."
        )

        inicio = time.time()

        self._aguardar_fim_loading(driver, espera_max=min(timeout_s, 5))

        url_anterior = ""
        estavel_desde = None
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                url_atual = driver.current_url
            except Exception:
                break
            if url_atual == url_anterior:
                if estavel_desde is None:
                    estavel_desde = time.time()
                elif time.time() - estavel_desde >= 1.0:
                    logger.info(
                        f"[SPA] {arte_label}: URL estável por 1s ({url_atual[:60]}...)."
                    )
                    break
            else:
                estavel_desde = None
                if url_anterior:
                    logger.info(
                        f"[SPA] {arte_label}: URL mudou após arte anterior "
                        f"({url_anterior[:40]} → {url_atual[:40]})."
                    )
                url_anterior = url_atual
            time.sleep(0.3)

        time.sleep(0.5)
        logger.info(
            f"[SPA] {arte_label}: estabilização concluída em "
            f"{time.time() - inicio:.1f}s."
        )

    def _aguardar_fim_loading(self, driver, espera_max: int = 30) -> None:
        """Aguarda desaparecer indicadores de carregamento.

        Args:
            driver: WebDriver ativo.
            espera_max: Tempo máximo de espera.
        """
        inicio = time.time()
        while time.time() - inicio < espera_max:
            carregando = False
            for sel in SELECTORS["indicador_carregando"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        carregando = True
                        break
                except Exception:
                    continue
            if not carregando:
                return
            time.sleep(1)
