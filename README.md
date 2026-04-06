# Media Rats — Artgen

Gerador automático de artes para redes sociais usando Selenium + Excel + PyQt6.

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

## Estrutura de Pastas

```
MEDIARATS-ARTGEN/
├── main.py                  # Ponto de entrada
├── requirements.txt
├── .env                     # Configurações de ambiente
├── settings.json            # Preferências da janela
├── version.txt
├── gui/                     # Interface gráfica (PyQt6)
│   ├── main_window.py
│   ├── dashboard.py
│   ├── fila_panel.py
│   ├── log_panel.py
│   ├── controles_panel.py
│   └── configuracoes_dialog.py
├── bot/                     # Automação Selenium
│   ├── selenium_handler.py
│   ├── adapta_generator.py
│   └── download_manager.py
├── excel/                   # Leitura/escrita de planilha
│   ├── reader.py
│   └── writer.py
├── utils/                   # Utilitários
│   ├── config.py
│   ├── logger.py
│   └── helpers.py
├── assets/                  # Logo e ícones
├── logs/                    # Logs em artgen.log
├── output/                  # Imagens geradas (criada automaticamente)
└── planilha/
    └── planilha-artgenmediarats.xlsx
```

## Variáveis de Ambiente (.env)

| Variável | Padrão | Descrição |
|---|---|---|
| `URL_ADAPTA` | `https://www.adapta.org` | URL do gerador de imagens |
| `CAMINHO_PLANILHA` | `./planilha/planilha-artgenmediarats.xlsx` | Caminho da planilha |
| `CAMINHO_OUTPUT` | `./output` | Pasta de saída das imagens |
| `TIMEOUT_GERADOR` | `60` | Segundos aguardando geração |
| `MODO_HEADLESS` | `false` | Navegador invisível (`true`/`false`) |
| `FECHAR_NAVEGADOR_APOS_CONCLUSAO` | `true` | Fechar browser ao terminar |

## Estrutura da Planilha

### Aba CLIENTES
| CODIGO_CLIENTE | NOME |
|---|---|
| DUDE | Cliente Exemplo |

### Aba CONTEUDOS
| PROTOCOLO | CODIGO_CLIENTE | CLIENTE | NUMERO_SOLICITACAO | TEMA | STATUS | DATA_PLANEJADA | PROMPT 1 … PROMPT 10 |
|---|---|---|---|---|---|---|---|

**Status válidos para geração:** `Planejado`, `Pendente`

### Aba AVALIACAO_DETALHADA
Preenchida automaticamente após cada geração com os dados das artes.

## Troubleshooting

**Navegador não inicia**
- Verifique se Chrome, Edge ou Firefox está instalado.
- O `webdriver-manager` baixa o driver automaticamente.

**Login necessário no Adapta.org**
- O programa nunca faz login automático.
- Faça login manualmente no navegador que será aberto.

**Planilha travada**
- Feche o arquivo Excel antes de iniciar.

**Logs detalhados**
- Consulte `logs/artgen.log` para diagnóstico completo.

## Versão

1.0.0
