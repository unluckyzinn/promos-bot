"""
Scraper de ofertas da Amazon BR — usa a API interna de busca de produtos
(a mesma que o site usa para paginação ao rolar a página de /deals),
em vez de raspar HTML. Mais simples e mais confiável.

Endpoint descoberto via DevTools (Network > XHR) em 01/07/2026:
    GET /d2b/api/v1/products/search

Vantagem sobre o Mercado Livre: não precisa de cookie/sessão pra gerar
link de afiliado — é só colar "?tag=SEU_ASSOCIATE_TAG" na URL do produto.
"""

import json
import re
import requests

URL_BUSCA = "https://www.amazon.com.br/d2b/api/v1/products/search"

FILTROS_PADRAO = {
    "includedDepartments": [],
    "excludedDepartments": [],
    "includedTags": [],
    "excludedTags": ["EINKBF25"],
    "promotionTypes": ["LIGHTNING_DEAL", "BEST_DEAL"],
    "accessTypes": [],
    "brandIds": [],
    "unifiedIds": [],
}

RANKING_CONTEXT_PADRAO = {"pageTypeId": "deals", "rankGroup": "PARENT_ASIN_RANKING"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.amazon.com.br/deals",
}


class AmazonScraper:
    def __init__(self, url_busca: str = URL_BUSCA):
        self.url_busca = url_busca

    def buscar_ofertas(self, limite: int = 40) -> list[dict]:
        ofertas = []
        start_index = 0
        page_size = 30

        while len(ofertas) < limite:
            params = {
                "pageSize": page_size,
                "startIndex": start_index,
                "calculateRefinements": "false",
                "rankingContext": json.dumps(RANKING_CONTEXT_PADRAO),
                "filters": json.dumps(FILTROS_PADRAO),
                "pinnedPromotionsLayoutGroup": "default",
            }

            resp = requests.get(self.url_busca, params=params, headers=HEADERS, timeout=15)

            if resp.status_code != 200:
                print(f"[AmazonScraper] Erro HTTP: {resp.status_code}")
                break

            try:
                data = resp.json()
            except ValueError:
                print("[AmazonScraper] Resposta não é JSON válido — possível bloqueio.")
                break

            produtos_raw = data.get("products", [])
            if not produtos_raw:
                break  # acabaram as páginas

            for p in produtos_raw:
                oferta = self._normalizar_produto(p)
                if oferta:
                    ofertas.append(oferta)

            next_index = data.get("nextIndex")
            if not next_index or next_index == start_index:
                break
            start_index = next_index

        return ofertas[:limite]

    def _normalizar_produto(self, p: dict) -> dict | None:
        try:
            asin = p.get("asin")
            titulo = p.get("title")
            link_relativo = p.get("link")

            if not asin or not titulo or not link_relativo:
                return None

            link_produto = (
                f"https://www.amazon.com.br{link_relativo}"
                if link_relativo.startswith("/")
                else link_relativo
            )

            preco_info = p.get("price")
            if not preco_info:
                return None

            preco_atual = self._parse_valor(preco_info.get("priceToPay", {}).get("price"))
            preco_original = self._parse_valor(preco_info.get("basisPrice", {}).get("price"))

            if preco_atual is None:
                return None

            desconto_percentual = None
            if preco_original and preco_original > preco_atual:
                desconto_percentual = ((preco_original - preco_atual) / preco_original) * 100
            else:
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
