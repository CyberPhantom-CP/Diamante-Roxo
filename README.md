# Diamante Roxo

![Versão](https://img.shields.io/badge/vers%C3%A3o-v5.1-7b2cbf)
![Python](https://img.shields.io/badge/Python-3.14-7b2cbf)
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
| **Kickerino** | Cliente de chat da Kick |

## Plataformas

- **Twitch** — todos os aplicativos (Mix It Up, Chatty, Streamer.bot, OBS)
- **Kick** — Streamer.bot, Kickerino e OBS

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
- **Oráculo de horário**: pausa noturna (23h-06h) com retorno em horário configurado
- **Pausa por quantidade** de filmes, com retorno automático
- **Retornos independentes** para pausa noturna e pausa por quantidade
- **Detecção de queda de stream**: pausa o filme e retoma após 3s de estabilidade
- **Fontes de texto dinâmicas** no OBS (ID LIVE, SESSÃO ID)
- **Log diário** completo de todas as ações
- Ajuste automático de prioridade do processo
- Transmissão **direta** para a Kick (sem relay FFmpeg)

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
├── tempo_duracao.txt                → durações e saltos pós-créditos (com cabeçalho comentado)
├── Diamante Roxo (Execução manual).bat → launcher manual
└── .gitignore
```

> **Na pasta de trabalho (Códigos):** usa-se `Painel_de_Controle.txt` (cópia ativa do `.example`), que não é versionado.

## Como rodar

1. Configure o `Painel_de_Controle.txt` (na raiz do projeto) com seus horários, modo e conexão do OBS
2. Configure a transmissão da Kick **diretamente no OBS** (Ferramentas → Configurações → Transmissão)
3. Defina `executar_sistema = yes` (senão o sistema se recusa a iniciar)
4. Execute o `Diamante Roxo.py` (ou o `.bat`)

> **Aviso de segurança:** este sistema depende de uma configuração muito específica do OBS (cenas, fontes, coleções com nomes exatos). Sem o OBS idêntico ao original, o sistema **não funciona** — e sem o painel correto, a trava de segurança bloqueia a inicialização de propósito. Este é um projeto pessoal, não um produto distribuível.

## Utilitários

Os dois utilitários preenchem os arquivos de texto da raiz do projeto:

| Script | Gera | Observação |
|---|---|---|
| `Utilitarios/gerar_tempo.py` | `tempo_duracao.txt` | Extrai a duração dos vídeos com `ffprobe`. Escreve o cabeçalho comentado no padrão do `controle_censura.txt` e **preserva** os comentários que você adicionar. Na opção "2" (dia novo), também reseta `controle_censura.txt` com uma linha `False | ` por sessão. |
| `Utilitarios/Gerar_Censuras.py` | `controle_censura.txt` | Captura as cenas a censurar. Requer `keyboard` e a Interface Web do MPC-BE na porta 13579. |

Ambos usam caminho hardcoded: preencha a constante `PASTA_*` no topo antes de executar.

> **Por que a censura é posicional:** o script principal casa a censura do filme *N* com a linha *N* do `tempo_duracao.txt`. Por isso o `gerar_tempo.py` grava exatamente uma linha `False | ` por sessão — se os dois arquivos tiverem quantidades diferentes de linhas, cada filme recebe a censura do vizinho.

## Requisitos

- Windows (utiliza `pywinauto`, `psutil` e `schedule`)
- Python 3.14 (testado nesta versão; códigos 3.10+ funcionam)
- OBS Studio com WebSocket habilitado (porta [PORTA])
- Streamer.bot / Mix It Up / Chatty / Kickerino (conforme a plataforma)
- Conexão de rede estável para transmitir direto na Kick

## Licença

Projeto pessoal. Não distribuir sem autorização.
