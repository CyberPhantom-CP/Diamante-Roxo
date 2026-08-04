# 💎 Diamante Roxo

![Versão](https://img.shields.io/badge/vers%C3%A3o-v4.13-7b2cbf)
![Python](https://img.shields.io/badge/Python-3.x-7b2cbf)
![Status](https://img.shields.io/badge/status-em%20uso-7b2cbf)

Sistema de automação para transmissão ao vivo (lives), gerenciando cenas, áudio, alertas e transições no **OBS Studio**.

Projeto pessoal de uso contínuo em lives reais. Configuração 100% por arquivos de texto, sem necessidade de editar o código.

---

## Aplicativos gerenciados

| Aplicativo | Função |
|---|---|
| **OBS Studio** | Transmissão e gravação de áudio/vídeo |
| **Streamer.bot** | Automação de eventos, comandos e alertas |
| **Mix It Up** | Chat, comandos e interatividade |
| **Chatty** | Cliente de chat com moderação |

## Plataformas

- **Twitch** — todos os aplicativos (Mix It Up, Chatty, Streamer.bot, OBS)
- **Kick** — apenas Streamer.bot e OBS

## Modos de operação

- **FILMES** — reprodução de mídia com censura por tempo e saltos
- **RERUN** — retransmissão ao vivo com contagem regressiva
- **ESTUDO** — acionamento direto de mídias sem passar pela cena INÍCIO

---

## Funcionalidades

- **Trava de segurança**: o sistema só executa se `executar_sistema` for `yes`, `sim` ou `true` no painel
- **Localização dinâmica** dos softwares — não depende de caminho fixo de instalação
- **Fluxo automático de cenas** com cronômetro (ENTRADA → INÍCIO → MÍDIAS → PAUSA → RAID → FINAL) e roteamento manual
- **Ducking de áudio durante alertas**: reduz o volume das fontes e restaura com fade suave, sem picos
- **Sistema de censura por trecho** (`controle_censura.txt`): liga/desliga fontes nos horários exatos do filme
- **Pulos pós-créditos**: avança automaticamente trechos desnecessários
- **Oráculo de horário**: corta a reprodução antes das 23h para não estourar o limite
- **Pausa por quantidade** de filmes, com retorno automático
- **Detecção de queda de stream**: pausa o filme e retoma após 3s de estabilidade
- **Fontes de texto dinâmicas** no OBS (ID LIVE, SESSÃO ID)
- **Log diário** completo de todas as ações
- Ajuste automático de prioridade do processo

---

## Estrutura do projeto

```
Diamante-Roxo\
├── README.md                        → este arquivo
├── Script\
│   └── Diamante Roxo.py             → script principal
├── Utilitarios\
│   ├── gerar_tempo.py               → extrai durações dos vídeos (gera tempo_duracao.txt)
│   └── Gerar_Censuras.py            → captura cenas a censurar (gera controle_censura.txt)
├── DOCUMENTACAO_COMPLETA.md         → documentação técnica detalhada
├── JORNADA_DIAMANTE_ROXO.md         → histórico da jornada de desenvolvimento
├── Painel_de_Controle.example.txt   → modelo de configuração
├── controle_censura.txt             → regras de censura por filme
├── tempo_duracao.txt                → durações e saltos pós-créditos
├── Diamante Roxo (Execução manual).bat → launcher manual
└── .gitignore
```

## Como rodar

1. Copie o `Painel_de_Controle.example.txt` para `Painel_de_Controle.txt` (na raiz do projeto)
2. Preencha seus horários, modo e conexão do OBS
3. Defina `executar_sistema = yes` (senão o sistema se recusa a iniciar)
4. Execute o `Diamante Roxo.py` (ou o `.bat`)

> ⚠ **Aviso de segurança:** este sistema depende de uma configuração muito específica do OBS (cenas, fontes, coleções com nomes exatos). Sem o OBS idêntico ao original, o sistema **não funciona** — e sem o painel correto, a trava de segurança bloqueia a inicialização de propósito. Este é um projeto pessoal, não um produto distribuível.

## Requisitos

- Windows (utiliza `pywinauto`, `psutil` e `schedule`)
- Python 3.8+
- OBS Studio com WebSocket habilitado (porta 4455)
- Streamer.bot / Mix It Up / Chatty (conforme a plataforma)

## Licença

Projeto pessoal. Não distribuir sem autorização.
