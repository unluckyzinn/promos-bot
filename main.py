"""
Script principal: busca um lote grande de ofertas no Mercado Livre, mas
posta só uma quantidade pequena por execução — o resto fica pra próximas
rodadas (o GitHub Actions roda de hora em hora, então o efeito é o canal
recebendo posts aos poucos, não uma enxurrada de uma vez).

Uso local:
    python main.py

IMPORTANTE sobre duplicatas: uma oferta já postada antes é PULADA sem
gastar a cota da rodada — o script continua procurando ofertas novas até
completar MAX_POSTS_POR_EXECUCAO ou esgotar a lista buscada. Ou seja,
"cair" numa duplicada não trava nem atrasa o lançamento de ofertas novas.

NOTA: A geração de link de afiliado (ml_affiliate.py) depende de cookies
de sessão do navegador, que expiram — por enquanto rode isso local, não
no GitHub Actions. Se ML_COOKIE_HEADER não estiver configurado, o bot
ainda funciona, só posta o link direto do produto (sem comissão).

NOTA 2: A integração com Shopee (src/shopee_client.py) está pronta mas
depende de aprovação de acesso à Open API deles (precisa de CNPJ).
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from ml_scraper import MercadoLivreScraper
from ml_affiliate import MercadoLivreAffiliateLinkGenerator
from ofertas_repositorio import OfertasRepositorio
from telegram_poster import TelegramPoster

load_dotenv()


def main():
    telegram = TelegramPoster(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
    )

    mercado_livre = MercadoLivreScraper()
    repositorio = OfertasRepositorio(database_url=os.environ["DATABASE_URL"])

    afiliado = None
    cookie_header = os.environ.get("ML_COOKIE_HEADER")
    tag_afiliado = os.environ.get("ML_AFFILIATE_TAG")
    if cookie_header and tag_afiliado:
        afiliado = MercadoLivreAffiliateLinkGenerator(
            cookie_header=cookie_header, tag=tag_afiliado
        )
    else:
        print(
            "[main] ML_COOKIE_HEADER ou ML_AFFILIATE_TAG não configurados — "
            "postando sem link de afiliado (sem comissão)."
        )

    min_desconto = float(os.environ.get("MIN_DESCONTO_PERCENTUAL", 30))
    max_posts_por_execucao = int(os.environ.get("MAX_POSTS_POR_EXECUCAO", 3))

    # Busca um lote grande (bem maior que a cota de postagem), pra ter de
    # onde escolher mesmo descartando duplicatas e ofertas com desconto
    # baixo demais.
    ofertas = mercado_livre.buscar_ofertas(limite=60)

    if not ofertas:
        print("Nenhuma oferta encontrada nesta rodada.")
        return

    postadas = 0
    for oferta in ofertas:
        if postadas >= max_posts_por_execucao:
            print(
                f"[main] Cota de {max_posts_por_execucao} posts atingida "
                "nesta rodada. O resto fica pra próxima execução."
            )
            break

        item_id = oferta.get("item_id")

        if not item_id:
            print(f"[main] Sem item_id, pulando: {oferta['titulo']}")
            continue  # não conta pra cota

        if repositorio.ja_foi_postado(item_id):
            print(f"[main] Já postado antes, pulando: {oferta['titulo']}")
            continue  # não conta pra cota — segue procurando uma nova

        # Filtro simples de qualidade — ajuste esse critério como quiser
        if oferta.get("desconto_percentual") is not None:
            if oferta["desconto_percentual"] < min_desconto:
                continue  # não conta pra cota

        if afiliado:
            link_gerado = afiliado.gerar_link(oferta["link_afiliado"], item_id=item_id)
            if link_gerado:
                oferta["link_afiliado"] = link_gerado
            else:
                print(f"[main] Não gerou link de afiliado pra: {oferta['titulo']}")
                # segue com o link direto do produto mesmo assim

        sucesso = telegram.postar_promocao(oferta)
        if sucesso:
            postadas += 1
            repositorio.marcar_como_postado(item_id, oferta["titulo"])

    print(f"Postagem concluída: {postadas} oferta(s) nova(s) postada(s) nesta rodada.")


if __name__ == "__main__":
    main()
