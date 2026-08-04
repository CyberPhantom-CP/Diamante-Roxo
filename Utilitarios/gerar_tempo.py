# Extraindo a duracao dos videos

# === Importacoes ===
import os, sys, subprocess

# Preencha com o caminho completo da pasta do Diamante Roxo, ex.:
#   PASTA_SCRIPT_PRINCIPAL = r"C:\Seu\Caminho\Diamante_Roxo"
PASTA_SCRIPT_PRINCIPAL = r"SEU_CAMINHO_DO_DIAMANTE_ROXO_AQUI"
ARQUIVO_CENSURA = os.path.join(PASTA_SCRIPT_PRINCIPAL, "controle_censura.txt")

CABECALHO_CENSURA = [
    "# SISTEMA DE CENSURAS",
    "# ====================================================================",
    '# REGRAS: ("True/False > INICIO (HH:MM:SS) > FIM (HH:MM:SS) > CENSURA, TARJA").',
    "# SEPARADOR: Usa (;) para colocar mais do que uma censura na mesma linha.",
    "# ====================================================================",
    "",
    "# ==== Bloco de Censuras ====",
    "False | "
]

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

    caminho_saida = os.path.join(PASTA_SCRIPT_PRINCIPAL, "tempo_duracao.txt")
    print(f"\nArquivo de saida: {caminho_saida}")

    print("\nOPCOES DE ARQUIVO:")
    print("[1] Adicionar novos tempos ao arquivo atual")
    print("[2] Gerar NOVO arquivo (apagar tempos antigos)")

    escolha = input("Escolha uma opcao (1 ou 2): ").strip()

    linhas = []
    if escolha == "1" and os.path.exists(caminho_saida):
        with open(caminho_saida, "r", encoding="utf-8") as f:
            for linha in f:
                l = linha.strip()
                if l:
                    linhas.append(l)

    if escolha == "2":
        with open(ARQUIVO_CENSURA, "w", encoding="utf-8") as f:
            f.write("\n".join(CABECALHO_CENSURA))
        print(f"\ncontrole_censura.txt resetado para o cabecalho padrao")

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

        linhas.append(tempo_formatado)
        print(f"Gravado: {tempo_formatado}")

    with open(caminho_saida, "w", encoding="utf-8") as out:
        out.write("\n".join(linhas))

    print("\nFinalizado!")

gerar_tempos()
