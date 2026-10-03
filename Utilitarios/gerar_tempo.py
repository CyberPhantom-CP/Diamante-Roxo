# Extraindo a duracao dos videos

# === Importacoes ===
import os, sys, subprocess

# Preencha com o caminho completo da pasta do Diamante Roxo, ex.:
#   PASTA_SCRIPT_PRINCIPAL = r"C:\Seu\Caminho\Diamante_Roxo"
PASTA_SCRIPT_PRINCIPAL = r"SEU_CAMINHO_DO_DIAMANTE_ROXO_AQUI"
ARQUIVO_TEMPOS = os.path.join(PASTA_SCRIPT_PRINCIPAL, "tempo_duracao.txt")
ARQUIVO_CENSURA = os.path.join(PASTA_SCRIPT_PRINCIPAL, "controle_censura.txt")

# Cabecalho padrao do tempo_duracao.txt. Escrito sempre ao final, para o arquivo
# ficar sempre documentado (mesmo padrao do controle_censura.txt).
CABECALHO_TEMPOS = [
    "# ====================================================================",
    "#  SISTEMA DE TEMPOS",
    "# ====================================================================",
    "#  FORMATO   :  DURAÇÃO (HH:MM:SS) | GATILHO> DESTINO; GATILHO> DESTINO",
    "#  DURAÇÃO   :  Tempo do filme sem créditos. Obrigatório.",
    "#  APÓS O |  :  Saltos pós-crédito. Opcional, vários separados por (;).",
    "#",
    "#  EXEMPLO   :  00:00:00 | 00:00:00>00:00:00;00:00:00>00:00:00",
    "#  EXEMPLO   :  00:00:00",
    "# ====================================================================",
    "",
    "# ==== Bloco de Tempos ====",
]

# Mantido como esta: o reset da censura continua definido por "False | ".
CABECALHO_CENSURA = [
    "# SISTEMA DE CENSURAS",
    "# ====================================================================",
    '# REGRAS: ("True/False > INICIO (HH:MM:SS) > FIM (HH:MM:SS) > CENSURA, TARJA").',
    "# SEPARADOR: Usa (;) para colocar mais do que uma censura na mesma linha.",
    "# ====================================================================",
    "",
    "# ==== Bloco de Censuras ====",
]

def separar_arquivo_tempos(caminho):
    """Separa o bloco de comentarios das linhas de dados.

    O cabecalho padrao e sempre reescrito no final, entao as copias dele que
    estiverem no arquivo sao descartadas. Comentarios do usuario sao preservados.
    """
    comentarios = []
    dados = []
    padrao = {l.strip() for l in CABECALHO_TEMPOS}

    if not os.path.exists(caminho):
        return comentarios, dados

    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            l = linha.strip()
            if not l:
                continue
            if l.startswith("#") or l.startswith("="):
                if l not in padrao:
                    comentarios.append(l)
            else:
                dados.append(l)

    return comentarios, dados

def gravar_tempos(caminho, comentarios, dados):
    """Grava cabecalho + comentarios do usuario + linhas de dados."""
    partes = list(CABECALHO_TEMPOS)
    if comentarios:
        partes.append("")
        partes.append("# --- Comentarios adicionais ---")
        partes.extend(comentarios)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(partes + dados) + "\n")

def resetar_censura(caminho, total_sessoes):
    """Zera a censura do dia com uma linha 'False | ' por sessao.

    O script principal casa censura por posicao, entao o numero de linhas
    precisa ser igual ao numero de sessoes de tempo para nao desalinhar.
    """
    linhas = list(CABECALHO_CENSURA) + ["False | "] * total_sessoes
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

def gerar_tempos():
    if len(sys.argv) > 1:
        videos = sys.argv[1:]
        print("Videos recebidos via arrastar e soltar:")
        for v in videos:
            print(f"  {v}")
    else:
        pasta_videos = os.getcwd()
        arquivos = os.listdir(pasta_videos)
        videos = [os.path.join(pasta_videos, f) for f in arquivos
                  if f.lower().endswith((".mp4", ".mkv", ".mov", ".avi"))]

        print("Videos detectados na pasta:")
        for v in videos:
            print(f"  {v}")

    if not videos:
        print("\nNenhum video encontrado.")
        return

    print(f"\nArquivo de saida: {ARQUIVO_TEMPOS}")

    print("\nOPCOES DE ARQUIVO:")
    print("[1] Adicionar novos tempos ao arquivo atual")
    print("[2] Gerar NOVO arquivo (apagar tempos antigos)")

    escolha = input("Escolha uma opcao (1 ou 2): ").strip()

    comentarios, dados = [], []
    if escolha == "1" and os.path.exists(ARQUIVO_TEMPOS):
        comentarios, dados = separar_arquivo_tempos(ARQUIVO_TEMPOS)
        print(f"\n{len(dados)} tempo(s) existente(s) mantido(s).")
    elif escolha == "2" and os.path.exists(ARQUIVO_TEMPOS):
        print("\nTempos antigos serao apagados.")

    for caminho_video in videos:
        video = os.path.basename(caminho_video)
        print(f"\nProcessando: {video}")

        resultado = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", caminho_video],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if resultado.returncode != 0:
            print(f"FFprobe falhou para: {video}")
            if resultado.stderr.strip():
                print(f"  Erro: {resultado.stderr.strip()}")
            continue

        duracao_str = resultado.stdout.strip()
        if not duracao_str:
            print(f"FFprobe nao retornou duracao para: {video}")
            continue

        duracao_segundos = float(duracao_str)
        h = int(duracao_segundos // 3600)
        m = int((duracao_segundos % 3600) // 60)
        s = int(duracao_segundos % 60)
        tempo_formatado = f"{h:02d}:{m:02d}:{s:02d}"

        dados.append(tempo_formatado)
        print(f"Gravado: {tempo_formatado}")

    gravar_tempos(ARQUIVO_TEMPOS, comentarios, dados)
    print(f"\ntempo_duracao.txt gravado com {len(dados)} sessao(oes).")

    # Vinculo com o Controle de Censuras: so na opcao 2 (dia novo), como antes.
    if escolha == "2":
        resetar_censura(ARQUIVO_CENSURA, len(dados))
        print(f"controle_censura.txt resetado com {len(dados)} linha(s) 'False | '.")

    print("\nFinalizado!")

gerar_tempos()
