MANUTENCAO NOVEMBRO — Diamante Roxo (01/11/2026)
====================================================

DONE / COMMITADO (pequeno):
- intervalo_detecao = 0.5 (única alteração de d7e779d)
- d7e779d restaurado; ultima_troca_arquivo removido; sem grace period
- Painel alinhado (executar_sistema=yes, live, kick, filmes, oraculo=nao)
- tempo_duracao.txt / controle_censura.txt reconstruídos (MS: HH:MM:SS:MS)

PENDENTE (lista formal — não alterado ainda):
1. PAUSE / Oráculo (linha 1173-1200) — oraculo_ativado=nao; retorno 23:59:59
2. Skip manual (Streamer.bot/Websocket) — debounce_skip removido; testar amanhã; se falhar, reconstruir
3. Falso skip — aguarda teste 2 filmes (0.5); se aparecer filme 3, analisar timeline_vlc_global
4. Arquivos .txt — verificar conteúdo MS escrito corretamente
5. PAUSE independente do Oráculo — skip → PAUSE → retorno pelo painel (pausa_retorno), sem depender de oraculo_ativado

AMBIENTE INALTERADO: OBS, x264, 24fps, 3000kbps, i5-3470
