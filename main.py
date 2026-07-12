"""
Script principal: busca ofertas no Mercado Livre, na Amazon e no
AliExpress, gera link de afiliado de cada fonte (mecanismo diferente
pra cada uma) e posta no Telegram. Só produtos — sem cupom.

Uso local:
    python main.py

IMPORTANTE sobre duplicatas: uma oferta já postada antes é PULADA sem
gastar a cota da rodada — o script continua procurando ofertas novas até
completar a cota daquela fonte ou esgotar a lista buscada.

NOTA: A geração de link de afiliado do ML e do AliExpress depende de
cookies de sessão do navegador, que expiram. Já a da Amazon é só
decoração de URL, sem essa dependência.

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
from aliexpress_scraper import AliExpressScraper
from aliexpress_affiliate import AliExpressAffiliateLinkGenerator
from ofertas_repositorio import OfertasRepositorio
from telegram_poster import TelegramPoster

load_dotenv()


def intercalar(*listas):
    """Intercala N listas de ofertas, uma de cada por vez, em vez de
    postar tudo de uma fonte primeiro."""
    resultado = []
    max_len = max((len(lista) for lista in listas), default=0)
    for i in range(max_len):
        for lista in listas:
            if i < len(lista):
                resultado.append(lista[i])
    return resultado


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

    # --- AliExpress ---
    ali_cookie_header = os.environ.get("ALIEXPRESS_COOKIE_HEADER")
    aliexpress = AliExpressScraper(cookie_header=ali_cookie_header)
    ali_tracking_id = os.environ.get("ALIEXPRESS_TRACKING_ID", "default")

    ali_afiliado = None
    if ali_cookie_header:
        ali_afiliado = AliExpressAffiliateLinkGenerator(
            cookie_header=ali_cookie_header, tracking_id=ali_tracking_id
        )
    else:
        print(
            "[main] ALIEXPRESS_COOKIE_HEADER não configurado — "
            "ofertas do AliExpress sairão sem link de afiliado (sem comissão)."
        )

    min_desconto = float(os.environ.get("MIN_DESCONTO_PERCENTUAL", 30))
    max_posts_ml = int(os.environ.get("MAX_POSTS_ML", 5))
    max_posts_amazon = int(os.environ.get("MAX_POSTS_AMAZON", 5))
    max_posts_aliexpress = int(os.environ.get("MAX_POSTS_ALIEXPRESS", 5))

    ofertas_ml = mercado_livre.buscar_ofertas(limite=60)
    for oferta in ofertas_ml:
        oferta["fonte"] = "mercado_livre"

    ofertas_amazon = amazon.buscar_ofertas(limite=40)
    for oferta in ofertas_amazon:
        oferta["fonte"] = "amazon"

    ofertas_aliexpress = aliexpress.buscar_ofertas(limite=40)
    for oferta in ofertas_aliexpress:
        oferta["fonte"] = "aliexpress"

    ofertas = intercalar(ofertas_ml, ofertas_amazon, ofertas_aliexpress)

    if not ofertas:
        print("Nenhuma oferta encontrada nesta rodada.")

    limites = {
        "mercado_livre": max_posts_ml,
        "amazon": max_posts_amazon,
        "aliexpress": max_posts_aliexpress,
    }
    postadas_por_fonte = {fonte: 0 for fonte in limites}
    puladas_por_fonte = {}

    for oferta in ofertas:
        fonte = oferta["fonte"]

        if postadas_por_fonte[fonte] >= limites[fonte]:
            continue  # essa fonte já bateu a cota dela, mas as outras podem continuar

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
        elif fonte == "aliexpress" and ali_afiliado:
            link_gerado = ali_afiliado.gerar_link(item_id)
            if link_gerado:
                oferta["link_afiliado"] = link_gerado
            else:
                print(f"[main] Não gerou link de afiliado AliExpress pra: {oferta['titulo']}")

        sucesso = telegram.postar_promocao(oferta)
        if sucesso:
            postadas_por_fonte[fonte] += 1
            repositorio.marcar_como_postado(item_id, oferta["titulo"])

        if all(postadas_por_fonte[f] >= limites[f] for f in limites):
            print("[main] Cotas de todas as fontes atingidas nesta rodada.")
            break

    if puladas_por_fonte:
        resumo = ", ".join(f"{fonte}: {n}" for fonte, n in puladas_por_fonte.items())
        print(f"[main] Ofertas já postadas antes, puladas — {resumo}")

    total_postadas = sum(postadas_por_fonte.values())
    resumo_postadas = ", ".join(f"{fonte}: {n}" for fonte, n in postadas_por_fonte.items())
    print(f"Postagem concluída: {total_postadas} oferta(s) nova(s) postada(s) — {resumo_postadas}")


if __name__ == "__main__":
    main()
