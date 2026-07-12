"""
Gerador de link de afiliado do AliExpress.

Usa o mesmo endpoint que o botão "Promova agora" do portal de afiliados
dispara, autenticado via cookie de sessão (JSESSIONID, xman_us_f, etc —
os mesmos cookies que o navegador já usa quando você está logado no
portals.aliexpress.com).

Endpoint descoberto via DevTools em 01/07/2026:
    GET /promote/promoteNow.do

LIMITAÇÃO IMPORTANTE (mesma do Mercado Livre): o cookie de sessão expira
de tempos em tempos. Quando isso acontecer, essa chamada vai parar de
retornar link válido — repita o processo de copiar o Cookie do navegador
(F12 > Network > qualquer chamada pro portals.aliexpress.com > Headers >
Request Headers > campo Cookie) e atualize o ALIEXPRESS_COOKIE_HEADER.
"""

import requests

ENDPOINT = "https://portals.aliexpress.com/promote/promoteNow.do"

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://portals.aliexpress.com/",
}


class AliExpressAffiliateLinkGenerator:
    def __init__(self, cookie_header: str, tracking_id: str = "default"):
        self.cookie_header = cookie_header.strip() if cookie_header else cookie_header
        self.tracking_id = tracking_id

    def gerar_link(self, item_id: str) -> str | None:
        params = {
            "productId": item_id,
            "trackingId": self.tracking_id,
            "language": "pt_PT",
            "shipTo": "BR",
            "currency": "BRL",
            "subChannel": "hd",
        }

        headers = dict(HEADERS_BASE)
        headers["Cookie"] = self.cookie_header

        try:
            resp = requests.get(ENDPOINT, params=params, headers=headers, timeout=15)
        except requests.RequestException as e:
            print(f"[AliExpressAffiliateLinkGenerator] Erro de conexão: {e}")
            return None

        if resp.status_code != 200:
            print(
                f"[AliExpressAffiliateLinkGenerator] Erro HTTP {resp.status_code} — "
                "provavelmente o cookie expirou. Copie de novo no navegador."
            )
            return None

        try:
            dados = resp.json()
        except ValueError:
            print("[AliExpressAffiliateLinkGenerator] Resposta não é JSON válido.")
            return None

        if not dados.get("success"):
            print(f"[AliExpressAffiliateLinkGenerator] Resposta sem sucesso: {dados}")
            return None

        return dados.get("data", {}).get("promoteUrl")
