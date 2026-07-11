"""
Scraper da página de ofertas da Amazon BR.

DESCOBERTA IMPORTANTE: a grade de produtos é renderizada via JavaScript
(a página começa com a classe "a-no-js" e troca pra "a-js" depois que o
JS roda). Mas os dados de TODOS os produtos já vêm prontos, como um JSON
embutido dentro de um <script>, numa chamada do tipo:

    assets.mountWidget('slot-14', {"marketplaceId": ..., "symphonyConfig":
        {"productSearchResponse": {"products": [...]}}})

Ou seja, não precisamos executar JavaScript nem simular navegador — só
extrair esse JSON direto do HTML. Isso é MAIS confiável que ler classes
CSS de card, porque não depende de nomes de classe que a Amazon pode
mudar a qualquer deploy.

Vantagem sobre o Mercado Livre: não precisa de cookie/API pra gerar link
de afiliado — é só colar "?tag=SEU_ASSOCIATE_TAG" na URL do produto.
"""

import json
import re
import requests

URL_OFERTAS = "https://www.amazon.com.br/deals"

MARCADOR_JSON = "assets.mountWidget('slot-14', "

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


class AmazonScraper:
    def __init__(self, url_ofertas: str = URL_OFERTAS):
        self.url_ofertas = url_ofertas

    def buscar_ofertas(self, limite: int = 40) -> list[dict]:
        resp = requests.get(self.url_ofertas, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            print(f"[AmazonScraper] Erro HTTP: {resp.status_code}")
            return []

        produtos_raw = self._extrair_produtos_json(resp.text)

        if produtos_raw is None:
            print(
                "[AmazonScraper] Não encontrei o JSON embutido de produtos. "
                "Provavelmente a Amazon mudou a estrutura da página."
            )
            return []

        ofertas = []
        for p in produtos_raw[:limite]:
            oferta = self._normalizar_produto(p)
            if oferta:
                ofertas.append(oferta)

        return ofertas

    def _extrair_produtos_json(self, html: str) -> list | None:
        idx = html.find(MARCADOR_JSON)
        if idx == -1:
            return None

        start = idx + len(MARCADOR_JSON)
        decoder = json.JSONDecoder()
        try:
            # raw_decode acha o fim do objeto JSON automaticamente, sem
            # precisar saber onde ele termina de antemão.
            data, _ = decoder.raw_decode(html, start)
        except json.JSONDecodeError as e:
            print(f"[AmazonScraper] Erro ao decodificar JSON embutido: {e}")
            return None

        return data.get("productSearchResponse", {}).get("products", [])

    def _normalizar_produto(self, p: dict) -> dict | None:
        try:
            asin = p.get("asin")
            titulo = p.get("title")
            link_relativo = p.get("link")

            if not asin or not titulo or not link_relativo:
                return None  # provavelmente um slot de anúncio, não produto

            link_produto = (
                f"https://www.amazon.com.br{link_relativo}"
                if link_relativo.startswith("/")
                else link_relativo
            )

            preco_info = p.get("price")
            if not preco_info:
                return None  # sem preço = não é uma oferta postável

            preco_atual = self._parse_valor(preco_info.get("priceToPay", {}).get("price"))
            preco_original = self._parse_valor(preco_info.get("basisPrice", {}).get("price"))

            if preco_atual is None:
                return None

            desconto_percentual = None
            if preco_original and preco_original > preco_atual:
                desconto_percentual = ((preco_original - preco_atual) / preco_original) * 100
            else:
                # fallback: usa o badge textual, ex: "36% off"
                fragments = (
                    p.get("dealBadge", {}).get("label", {}).get("content", {}).get("fragments", [])
                )
                if fragments:
                    match = re.search(r"(\d+)\s*%", fragments[0].get("text", ""))
                    if match:
                        desconto_percentual = float(match.group(1))

            imagem_hires = p.get("image", {}).get("hiRes", {})
            imagem_url = None
            if imagem_hires.get("baseUrl"):
                imagem_url = f"{imagem_hires['baseUrl']}.{imagem_hires.get('extension', 'jpg')}"

            return {
                "item_id": asin,
                "titulo": titulo,
                "preco_atual": preco_atual,
                "preco_original": preco_original,
                "desconto_percentual": desconto_percentual,
                "link_afiliado": link_produto,  # ainda sem ?tag=, ver AmazonAffiliateLinkBuilder
                "imagem_url": imagem_url,
            }
        except Exception as e:
            print(f"[AmazonScraper] Erro ao normalizar produto: {e}")
            return None

    def _parse_valor(self, valor) -> float | None:
        if valor is None:
            return None
        try:
            return float(valor)
        except (ValueError, TypeError):
            return None
