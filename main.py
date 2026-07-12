"""
Script principal: busca ofertas no Mercado Livre e na Amazon, gera link de
afiliado de cada fonte (mecanismo diferente pra cada uma) e posta no
Telegram. Só produtos — sem cupom.

Uso local:
    python main.py

IMPORTANTE sobre duplicatas: uma oferta já postada antes é PULADA sem
gastar a cota da rodada — o script continua procurando ofertas novas até
completar MAX_POSTS_POR_EXECUCAO ou esgotar a lista buscada.

NOTA: A geração de link de afiliado do ML (ml_affiliate.py) depende de
cookies de sessão do navegador, que expiram. Já a da Amazon
(amazon_affiliate.py) é só decoração de URL, sem essa dependência.

NOTA 2: A integração com Shopee (src/shopee_client.py) está pronta mas
depende de aprovação de acesso à Open API deles (precisa de CNPJ).
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from ml_scraper import MercadoLivreScraper
from ml_affiliate import MercadoLivreAffiliateLinkGenerator
from amazon_scraper import AmazonScraper
from amazon_affiliate import AmazonAffiliateLinkBuilder
from ofertas_repositorio import OfertasRepositorio
from telegram_poster import TelegramPoster

load_dotenv()


def main():
    telegram = TelegramPoster(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
    )

    repositorio = OfertasRepositorio(database_url=os.environ["DATABASE_URL"])

    # --- Mercado Livre ---
    mercado_livre = MercadoLivreScraper()
    ml_cookie_header = os.environ.get("ML_COOKIE_HEADER")
    ml_tag_afiliado = os.environ.get("ML_AFFILIATE_TAG")

    ml_afiliado = None
    if ml_cookie_header and ml_tag_afiliado:
        ml_afiliado = MercadoLivreAffiliateLinkGenerator(
            cookie_header=ml_cookie_header, tag=ml_tag_afiliado
        )
    else:
        print(
            "[main] ML_COOKIE_HEADER ou ML_AFFILIATE_TAG não configurados — "
            "ofertas do ML sairão sem link de afiliado (sem comissão)."
        )

    # --- Amazon ---
    amazon = AmazonScraper()
    amazon_tag = os.environ.get("AMAZON_ASSOCIATE_TAG")
    amazon_afiliado = AmazonAffiliateLinkBuilder(amazon_tag) if amazon_tag else None
    if not amazon_afiliado:
        print(
            "[main] AMAZON_ASSOCIATE_TAG não configurado — "
            "ofertas da Amazon sairão sem link de afiliado (sem comissão)."
        )

    min_desconto = float(os.environ.get("MIN_DESCONTO_PERCENTUAL", 30))
    max_posts_ml = int(os.environ.get("MAX_POSTS_ML", 5))
    max_posts_amazon = int(os.environ.get("MAX_POSTS_AMAZON", 5))

    ofertas_ml = mercado_livre.buscar_ofertas(limite=60)
    for oferta in ofertas_ml:
        oferta["fonte"] = "mercado_livre"

    ofertas_amazon = amazon.buscar_ofertas(limite=40)
    for oferta in ofertas_amazon:
        oferta["fonte"] = "amazon"

    # Intercala as duas fontes em vez de postar tudo de uma primeiro —
    # assim o canal não fica "só ML" numa hora e "só Amazon" na outra.
    ofertas = []
    max_len = max(len(ofertas_ml), len(ofertas_amazon))
    for i in range(max_len):
        if i < len(ofertas_ml):
            ofertas.append(ofertas_ml[i])
        if i < len(ofertas_amazon):
            ofertas.append(ofertas_amazon[i])

    if not ofertas:
        print("Nenhuma oferta encontrada nesta rodada.")

    postadas_por_fonte = {"mercado_livre": 0, "amazon": 0}
    puladas_por_fonte = {}

    limites = {"mercado_livre": max_posts_ml, "amazon": max_posts_amazon}

    for oferta in ofertas:
        fonte = oferta["fonte"]

        if postadas_por_fonte[fonte] >= limites[fonte]:
            continue  # essa fonte já bateu a cota dela, mas a outra pode continuar

        item_id = oferta.get("item_id")

        if not item_id:
            continue

        if repositorio.ja_foi_postado(item_id):
            puladas_por_fonte[fonte] = puladas_por_fonte.get(fonte, 0) + 1
            continue

        if oferta.get("desconto_percentual") is not None:
            if oferta["desconto_percentual"] < min_desconto:
                continue

        if fonte == "mercado_livre" and ml_afiliado:
            link_gerado = ml_afiliado.gerar_link(oferta["link_afiliado"], item_id=item_id)
            if link_gerado:
                oferta["link_afiliado"] = link_gerado
            else:
                print(f"[main] Não gerou link de afiliado ML pra: {oferta['titulo']}")
        elif fonte == "amazon" and amazon_afiliado:
            oferta["link_afiliado"] = amazon_afiliado.gerar_link(oferta["link_afiliado"])

        sucesso = telegram.postar_promocao(oferta)
        if sucesso:
            postadas_por_fonte[fonte] += 1
            repositorio.marcar_como_postado(item_id, oferta["titulo"])

        if all(postadas_por_fonte[f] >= limites[f] for f in limites):
            print("[main] Cotas das duas fontes atingidas nesta rodada.")
            break

    if puladas_por_fonte:
        resumo = ", ".join(f"{fonte}: {n}" for fonte, n in puladas_por_fonte.items())
        print(f"[main] Ofertas já postadas antes, puladas — {resumo}")

    total_postadas = sum(postadas_por_fonte.values())
    resumo_postadas = ", ".join(f"{fonte}: {n}" for fonte, n in postadas_por_fonte.items())
    print(f"Postagem concluída: {total_postadas} oferta(s) nova(s) postada(s) — {resumo_postadas}")


if __name__ == "__main__":
    main()
