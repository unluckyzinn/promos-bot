"""
Script principal: busca ofertas no Mercado Livre e cupons ativos, casa
cupons com produtos compatíveis (marca mencionada no cupom aparece no
título do produto + preço do produto >= compra mínima do cupom), posta
o combo no Telegram. Cupons que não casaram com nenhum produto são
postados sozinhos, com controle de duplicata próprio.

Uso local:
    python main.py

IMPORTANTE sobre duplicatas: uma oferta já postada antes é PULADA sem
gastar a cota da rodada — o script continua procurando ofertas novas até
completar MAX_POSTS_POR_EXECUCAO ou esgotar a lista buscada.

NOTA: A geração de link de afiliado (ml_affiliate.py) depende de cookies
de sessão do navegador, que expiram.

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
from cupom_scraper import CupomScraper, URL_CUPONS
from cupons_repositorio import CuponsRepositorio
from telegram_poster import TelegramPoster

load_dotenv()

MAX_CUPONS_SOZINHOS_POR_EXECUCAO = 2


def encontrar_cupom_compativel(oferta: dict, cupons: list) -> dict | None:
    """Casa um cupom com a oferta se a marca do cupom aparecer no título
    do produto E o preço do produto for >= compra mínima do cupom."""
    titulo_lower = oferta["titulo"].lower()

    for cupom in cupons:
        if not cupom.get("marca"):
            continue  # cupom genérico sem marca — não arriscamos casar

        if cupom["marca"].lower() not in titulo_lower:
            continue

        compra_minima = cupom.get("compra_minima")
        if compra_minima and oferta["preco_atual"] < compra_minima:
            continue

        return cupom

    return None


def main():
    telegram = TelegramPoster(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
    )

    mercado_livre = MercadoLivreScraper()
    repositorio = OfertasRepositorio(database_url=os.environ["DATABASE_URL"])

    cookie_header = os.environ.get("ML_COOKIE_HEADER")
    tag_afiliado = os.environ.get("ML_AFFILIATE_TAG")

    cupom_scraper = CupomScraper(cookie_header=cookie_header)
    cupons_repositorio = CuponsRepositorio(database_url=os.environ["DATABASE_URL"])

    afiliado = None
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
    max_posts_por_execucao = int(os.environ.get("MAX_POSTS_POR_EXECUCAO", 10))

    ofertas = mercado_livre.buscar_ofertas(limite=60)
    cupons = cupom_scraper.buscar_cupons()
    cupons_usados = set()

    if not ofertas:
        print("Nenhuma oferta encontrada nesta rodada.")

    postadas = 0
    for oferta in ofertas or []:
        if postadas >= max_posts_por_execucao:
            print(
                f"[main] Cota de {max_posts_por_execucao} posts atingida "
                "nesta rodada. O resto fica pra próxima execução."
            )
            break

        item_id = oferta.get("item_id")

        if not item_id:
            print(f"[main] Sem item_id, pulando: {oferta['titulo']}")
            continue

        if repositorio.ja_foi_postado(item_id):
            print(f"[main] Já postado antes, pulando: {oferta['titulo']}")
            continue

        if oferta.get("desconto_percentual") is not None:
            if oferta["desconto_percentual"] < min_desconto:
                continue

        cupom_compativel = encontrar_cupom_compativel(oferta, cupons)
        if cupom_compativel:
            oferta["cupom"] = cupom_compativel
            cupons_usados.add(cupom_compativel["chave"])
            print(f"[main] Cupom '{cupom_compativel['titulo_completo']}' casado com: {oferta['titulo']}")

        if afiliado:
            link_gerado = afiliado.gerar_link(oferta["link_afiliado"], item_id=item_id)
            if link_gerado:
                oferta["link_afiliado"] = link_gerado
            else:
                print(f"[main] Não gerou link de afiliado pra: {oferta['titulo']}")

        sucesso = telegram.postar_promocao(oferta)
        if sucesso:
            postadas += 1
            repositorio.marcar_como_postado(item_id, oferta["titulo"])

    print(f"Postagem concluída: {postadas} oferta(s) nova(s) postada(s) nesta rodada.")

    cupons_sozinhos_postados = 0
    for cupom in cupons:
        if cupons_sozinhos_postados >= MAX_CUPONS_SOZINHOS_POR_EXECUCAO:
            break
        if cupom["chave"] in cupons_usados:
            continue
        if cupons_repositorio.ja_foi_postado(cupom["chave"]):
            continue

        sucesso = telegram.postar_cupom_sozinho(cupom, URL_CUPONS)
        if sucesso:
            cupons_sozinhos_postados += 1
            cupons_repositorio.marcar_como_postado(cupom["chave"], cupom["titulo_completo"])

    print(f"Cupons sozinhos postados nesta rodada: {cupons_sozinhos_postados}")


if __name__ == "__main__":
    main()
