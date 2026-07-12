"""
Scraper de produtos do AliExpress — usa a API do portal de afiliados
(a mesma que a "Central de Anúncios" usa pra listar produtos).

Endpoint descoberto via DevTools (Network > XHR) em 01/07/2026:
    GET /material/productRecommend.do

CONFIRMADO: esse endpoint PRECISA do cookie de sessão. Sem ele, o
servidor retorna erro 500 (NullPointerException) — provavelmente porque
tenta calcular comissão/preço personalizado pro usuário logado e não
acha esse usuário sem cookie. Sempre passe cookie_header.

O link de afiliado de verdade (com rastreio de comissão) é gerado
separadamente, via AliExpressAffiliateLinkGenerator — ver esse endpoint
não retorna aqui, o link bruto do produto é só o "link direto" (sem
comissão) até passar pelo gerador.
"""

import re
import requests

URL_LISTAGEM = "https://portals.aliexpress.com/material/productRecommend.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://portals.aliexpress.com/",
}


class AliExpressScraper:
    def __init__(self, cookie_header: str | None = None, comissao_elevada: bool = True):
        """
        cookie_header: opcional. A listagem parece funcionar sem cookie
        (testado com signedIn=false retornando produtos reais), mas se
        um dia parar de funcionar sem, passe o Cookie da sua sessão
        (mesmo processo de F12 que usamos pro Mercado Livre).

        comissao_elevada: se True (padrão), busca da aba "Comissão
        elevada" (type=2, requireCouponCode=y) em vez de "Melhores
        Produtos" (type=1) — prioriza produtos que rendem mais comissão.
        """
        self.cookie_header = cookie_header.strip() if cookie_header else None
        self.comissao_elevada = comissao_elevada

    def buscar_ofertas(self, limite: int = 40) -> list[dict]:
        ofertas = []
        page_num = 1
        page_size = 12  # valor confirmado via F12, pode não aceitar mais que isso

        headers = dict(HEADERS)
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header

        while len(ofertas) < limite:
            params = {
                "requireCouponCode": "y" if self.comissao_elevada else "",
                "freeShipping": "",
                "shipTo": "BR",
                "currency": "BRL",
                "language": "pt",
                "pageSize": page_size,
                "pageNum": page_num,
                "type": 2 if self.comissao_elevada else 1,
            }

            resp = requests.get(URL_LISTAGEM, params=params, headers=headers, timeout=15)

            if resp.status_code != 200:
                print(f"[AliExpressScraper] Erro HTTP: {resp.status_code}")
                print(f"[AliExpressScraper] Corpo da resposta: {resp.text[:500]}")
                break

            try:
                data = resp.json()
            except ValueError:
                print("[AliExpressScraper] Resposta não é JSON válido.")
                break

            if not data.get("success"):
                print(f"[AliExpressScraper] Resposta sem sucesso: {data.get('code')}")
                break

            resultados = data.get("data", {}).get("results", [])
            if not resultados:
                break

            for item in resultados:
                oferta = self._normalizar_item(item)
                if oferta:
                    ofertas.append(oferta)

            if data.get("data", {}).get("finish"):
                break
            page_num += 1

        return ofertas[:limite]

    def _normalizar_item(self, item: dict) -> dict | None:
        try:
            item_id = item.get("itemId")
            titulo = item.get("itemTitle")
            item_url = item.get("itemUrl")
            imagem_url = item.get("itemMainPic")

            if not item_id or not titulo or not item_url:
                return None

            preco_atual = self._parse_preco_brl(item.get("itemPriceDiscountMin"))
            preco_original = self._parse_preco_brl(item.get("itemOriginPriceMin"))

            if preco_atual is None:
                return None

            desconto_percentual = None
            if preco_original and preco_original > preco_atual:
                desconto_percentual = ((preco_original - preco_atual) / preco_original) * 100

            link_limpo = item_url.split("?")[0]

            return {
                "item_id": str(item_id),
                "titulo": titulo,
                "preco_atual": preco_atual,
                "preco_original": preco_original,
                "desconto_percentual": desconto_percentual,
                "link_afiliado": link_limpo,  # ainda sem rastreio, ver AliExpressAffiliateLinkGenerator
                "imagem_url": imagem_url,
            }
        except Exception as e:
            print(f"[AliExpressScraper] Erro ao normalizar item: {e}")
            return None

    def _parse_preco_brl(self, texto: str | None) -> float | None:
        """Converte 'BRL 122.22' pra float 122.22"""
        if not texto:
            return None
        match = re.search(r"([\d.]+)", texto)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None
