# -*- coding: utf-8 -*-
"""Testa a contagem de tempo do script (`esperar_com_deteccao`) SEM precisar do OBS.

Como rodar (de qualquer pasta):

    python Utilitarios/testes/testar_cronometro.py

O OBS e simulado com um client falso — as funcoes REAIS sao extraidas do proprio
`Script/Diamante Roxo.py` via AST, entao o teste valida o codigo que roda de
verdade, nao uma copia.

O que cobre:
  * trocar o tempo da cena no meio aplica NA HORA e VOLTA PRO VALOR DIGITADO
    (contagem reiniciada, nao desconta o que ja correu);
  * a exibicao mostra o valor exato digitado (ceil), nao valor-1;
  * so INICIO/RAID/FINAL reaproveitam; ENTRADA e finais de cena nao mexem;
  * trocar de cena no meio interrompe com "pular".

Demora ~40s de proposito (simula contagens reais de poucos segundos).
"""
import ast
import math
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

# Caminho do script RELATIVO a raiz do repo (sem caminho pessoal de ninguem).
RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "Script" / "Diamante Roxo.py"

if not SCRIPT.exists():
    sys.exit(f"[ERRO] Script nao encontrado: {SCRIPT}\n"
             "Rode a partir do repo (Utilitarios/testes/ tem que ser filho da raiz).")

PAINEL = os.path.join(tempfile.gettempdir(), "painel_sim_obs.txt")

src = open(SCRIPT, encoding="utf-8").read()
tree = ast.parse(src)

FONTES = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in (
            "esperar_com_deteccao", "converter_hhmmss", "converter_hhmmss_tupla"):
        FONTES[node.name] = ast.get_source_segment(src, node)

assert set(FONTES) == {"esperar_com_deteccao", "converter_hhmmss", "converter_hhmmss_tupla"}, \
    "Funcoes nao encontradas no script (mudou o nome?)"

CONV = {}
exec(FONTES["converter_hhmmss"], CONV)
exec(FONTES["converter_hhmmss_tupla"], CONV)
seg_de = CONV["converter_hhmmss"]           # codigo real

MAPA = {"ENTRADA": "duracao_entrada", "INÍCIO": "duracao_inicio",
        "RAID": "duracao_raid", "FINAL": "duracao_final"}


class Estado:
    def __init__(self, cena):
        self.cena = cena


class FakeClient:
    """So o que a contagem usa: qual cena esta no ar."""

    def __init__(self, estado):
        self.estado = estado

    def get_current_program_scene(self):
        return type("Prog", (), {"current_program_scene_name": self.estado.cena})()

    def get_media_input_status(self, *_a):
        raise RuntimeError("nao usado neste teste")


def escrever_painel(valores):
    with open(PAINEL, "w", encoding="utf-8") as f:
        for k, v in valores.items():
            f.write(f"{k} = {v}\n")


def montar(cena):
    estado = Estado(cena)
    fake = FakeClient(estado)
    logs, saidas = [], []

    def _log(m):
        logs.append(m)
        saidas.append("[LOG] " + m)          # mistura logs e prints = ve a ordem real

    ns = {
        "time": time, "math": math, "os": os, "datetime": datetime, "timedelta": timedelta,
        "painel_geral": PAINEL,
        "ultima_modificacao": 0, "ultima_modificacao_tempos": 0.0,
        "midia_decorrido_global": 0.0, "timeline_vlc_global": -1,
        "global_oraculo_ativado": False, "global_pausa_apos_filmes": 0,
        "global_duracao_entrada": "00:00:09", "global_duracao_inicio": "00:07:05",
        "global_duracao_raid": "00:11:10", "global_duracao_final": "00:05:10",
        "global_modo_conteudo": "filmes", "global_modo_sistema": "live",
        "client": fake, "event_client": None,
        "log": _log,
        "print": lambda *a, **k: saidas.append(" ".join(str(x) for x in a)),
        "visibilidade_fonte": lambda *a, **k: None,
        "carregar_censuras_do_filme": lambda _i: [],
        "cena_ativa_obs": lambda: fake.get_current_program_scene().current_program_scene_name,
    }
    exec(FONTES["converter_hhmmss"], ns)
    exec(FONTES["converter_hhmmss_tupla"], ns)
    exec(FONTES["esperar_com_deteccao"], ns)
    ns["_logs"], ns["_saidas"], ns["_estado"] = logs, saidas, estado
    return ns


def cenario(nome, cena, seg_inicial, alterar_chave=None, alterar_valor=None,
            momento=1.5, trocar_cena_para=None):
    valores = {"duracao_entrada": "00:00:09", "duracao_inicio": "00:07:05",
               "duracao_raid": "00:11:10", "duracao_final": "00:05:10"}
    valores[MAPA[cena]] = f"00:00:{seg_inicial:02d}"
    escrever_painel(valores)

    ns = montar(cena)
    ns["ultima_modificacao_tempos"] = os.path.getmtime(PAINEL)

    saida = {}

    def alvo():
        saida["r"] = ns["esperar_com_deteccao"](seg_de(valores[MAPA[cena]]), cena, is_midia=False)

    th = threading.Thread(target=alvo, daemon=True)
    t0 = time.time()
    th.start()
    time.sleep(momento)

    if trocar_cena_para:
        ns["_estado"].cena = trocar_cena_para
        acao = f"trocou cena {cena} -> {trocar_cena_para}"
    else:
        valores[alterar_chave] = alterar_valor
        escrever_painel(valores)
        acao = f"mudou {alterar_chave}: {seg_inicial}s -> {alterar_valor}"

    th.join(timeout=30)
    elapsed = time.time() - t0
    return {"nome": nome, "acao": acao, "elapsed": elapsed,
            "resultado": saida.get("r"), "logs": ns["_logs"], "saidas": ns["_saidas"]}


def linha_apos_log(saidas, trecho="alterado em cena"):
    """Proxima linha de countdown depois do log de alteracao (ou None)."""
    for i, s in enumerate(saidas):
        if trecho in s:
            for prox in saidas[i + 1:]:
                if "Restante" in prox:
                    return prox.strip()
            return None
    return None


falhas = 0


def checar(titulo, cond, detalhe=""):
    global falhas
    if not cond:
        falhas += 1
    print(f"  [{'OK ' if cond else 'FALHA'}] {titulo}{(' -> ' + detalhe) if detalhe else ''}")


print("=== Simulacao de cena do OBS com o codigo REAL (cronometro no terminal) ===")
print(f"Script testado: {SCRIPT}")

# 1) RAID: mudar duracao_raid DEVE aplicar na hora e voltar pro valor digitado
r = cenario("RAID muda duracao_raid", "RAID", 7, "duracao_raid", "00:00:03")
print(f"\n[1] {r['acao']}  (t={r['elapsed']:.2f}s, resultado={r['resultado']!r})")
checar("logou 'alterado em cena'", any("Tempo RAID alterado em cena: 7s -> 00:00:03" in m
                                       for m in r["logs"]), str([m for m in r["logs"] if "alterado" in m]))
checar("contador mostrou 00:00:03 logo apos a troca",
       "Restante: 00:00:03" in (linha_apos_log(r["saidas"]) or ""),
       (linha_apos_log(r["saidas"]) or "(nada)"))
checar("reiniciou e rodou os 3s novos", 4.0 <= r["elapsed"] <= 6.0, f"t={r['elapsed']:.2f}s")
checar("resultado normal", r["resultado"] == "normal", repr(r["resultado"]))

# 2) RAID: mudar duracao_final NAO deve afetar a cena RAID
r = cenario("RAID nao afetado por duracao_final", "RAID", 7, "duracao_final", "00:00:03")
print(f"\n[2] {r['acao']}  (t={r['elapsed']:.2f}s, resultado={r['resultado']!r})")
checar("nao logou 'alterado em cena'", not any("alterado em cena" in m for m in r["logs"]),
       str([m for m in r["logs"] if "alterado" in m]))
checar("rodou o tempo cheio (7s)", r["elapsed"] >= 6.5, f"t={r['elapsed']:.2f}s")

# 3) RAID: mudar duracao_entrada NAO deve afetar (ENTRADA e excluida)
r = cenario("RAID nao afetado por duracao_entrada", "RAID", 7, "duracao_entrada", "00:00:03")
print(f"\n[3] {r['acao']}  (t={r['elapsed']:.2f}s, resultado={r['resultado']!r})")
checar("ENTRADA fora do reload em cena", not any("alterado em cena" in m for m in r["logs"]),
       str([m for m in r["logs"] if "alterado" in m]))
checar("rodou o tempo cheio (7s)", r["elapsed"] >= 6.5, f"t={r['elapsed']:.2f}s")

# 4) INICIO: mudar duracao_inicio DEVE aplicar e mostrar o valor novo
r = cenario("INICIO muda duracao_inicio", "INÍCIO", 7, "duracao_inicio", "00:00:03")
print(f"\n[4] {r['acao']}  (t={r['elapsed']:.2f}s, resultado={r['resultado']!r})")
checar("logou 'alterado em cena'", any("Tempo INÍCIO alterado em cena: 7s -> 00:00:03" in m
                                       for m in r["logs"]), str([m for m in r["logs"] if "alterado" in m]))
checar("contador mostrou 00:00:03 logo apos a troca",
       "Restante: 00:00:03" in (linha_apos_log(r["saidas"]) or ""),
       (linha_apos_log(r["saidas"]) or "(nada)"))
checar("reiniciou e rodou os 3s novos", 4.0 <= r["elapsed"] <= 6.0, f"t={r['elapsed']:.2f}s")

# 5) FINAL: mudar duracao_final DEVE aplicar e mostrar o valor novo
r = cenario("FINAL muda duracao_final", "FINAL", 7, "duracao_final", "00:00:03")
print(f"\n[5] {r['acao']}  (t={r['elapsed']:.2f}s, resultado={r['resultado']!r})")
checar("logou 'alterado em cena'", any("Tempo FINAL alterado em cena: 7s -> 00:00:03" in m
                                       for m in r["logs"]), str([m for m in r["logs"] if "alterado" in m]))
checar("contador mostrou 00:00:03 logo apos a troca",
       "Restante: 00:00:03" in (linha_apos_log(r["saidas"]) or ""),
       (linha_apos_log(r["saidas"]) or "(nada)"))
checar("reiniciou e rodou os 3s novos", 4.0 <= r["elapsed"] <= 6.0, f"t={r['elapsed']:.2f}s")

# 6) Cena nova comeca mostrando o valor cheio (exibicao = ceil)
r = cenario("INICIO comeca no valor cheio", "INÍCIO", 7)
print(f"\n[6] cena {r['resultado']}  (t={r['elapsed']:.2f}s)")
primeiro = next((s.strip() for s in r["saidas"] if "Restante" in s), "")
checar("primeira tela mostra 00:00:07 (e nao 06)", "Restante: 00:00:07" in primeiro, primeiro)
checar("rodou o tempo cheio (7s)", r["elapsed"] >= 6.5, f"t={r['elapsed']:.2f}s")

# 7) Trocar de cena no meio -> interrompe a contagem com 'pular'
r = cenario("Troca de cena manual", "RAID", 10, trocar_cena_para="FINAL", momento=2.0)
print(f"\n[7] {r['acao']}  (t={r['elapsed']:.2f}s, resultado={r['resultado']!r})")
checar("resultado 'pular' ao trocar de cena", r["resultado"] == "pular", repr(r["resultado"]))
checar("parou logo apos a troca", r["elapsed"] < 5.0, f"t={r['elapsed']:.2f}s")

print(f"\nRESULTADO GERAL: {'TUDO PASSOU' if falhas == 0 else str(falhas) + ' FALHA(S)'}")
sys.exit(1 if falhas else 0)
