"""
Scraper da página de cupons do Mercado Livre
(https://www.mercadolivre.com.br/cupons).

Diferente das ofertas de produto, cupons AQUI não têm link individual —
é só um botão "Aplicar" que ativa o cupom na conta de quem clicar,
dentro da própria página. Por isso todo post de cupom aponta pra mesma
URL geral da página de cupons, não pra um link específico.

STATUS DOS SELETORES: confirmados via inspeção real (F12) em 01/07/2026.
Cada cupom fica dentro de uma <div class="coupons-list">.
"""

import re
import requests
from bs4 import BeautifulSoup

URL_CUPONS = "https://www.mercadolivre.com.br/cupons?source_page=mperfil"

SELETOR_CARD_CUPOM = "coupons-list"
SELETOR_TITULO = "title"                                  # tem o texto completo no atributo title=""
SELETOR_SUBTITULO_VALOR = "interpolated-label__container--subtitle"  # compra mínima / limite
SELETOR_VENCIMENTO = "expiration-text"

PADRAO_ARIA_PRECO = re.compile(r"(\d+)\s*reais(?:\s*com\s*(\d+)\s*centavos)?")
PADRAO_VALOR_OFF = re.compile(r"R\$\s*([\d.]+)\s*OFF", re.IGNORECASE)
PADRAO_MARCA = re.compile(r"OFF\s+em\s+(.+)$", re.IGNORECASE)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}


class CupomScraper:
    def __init__(self, url_cupons: str = URL_CUPONS, cookie_header: str | None = None):
        """
        cookie_header: a página de cupons é pessoal (nota o "mperfil" na
        URL — "meu perfil"), então precisa de uma sessão logada pra
        retornar os cupons de verdade. Reaproveite o mesmo ML_COOKIE_HEADER
        usado pro gerador de link de afiliado.
        """
        self.url_cupons = url_cupons
        self.cookie_header = cookie_header

    def buscar_cupons(self) -> list[dict]:
        headers = dict(HEADERS)
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header

        resp = requests.get(self.url_cupons, headers=headers, timeout=15)

        if resp.status_code != 200:
            print(f"[CupomScraper] Erro HTTP: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all(class_=SELETOR_CARD_CUPOM)

        if not cards:
            print(
                "[CupomScraper] Nenhum cupom encontrado. "
                "Provavelmente SELETOR_CARD_CUPOM mudou — confira com F12."
            )
            return []

        cupons = []
        for card in cards:
            cupom = self._extrair_cupom(card)
            if cupom:
                cupons.append(cupom)

        return cupons

    def _extrair_cupom(self, card) -> dict | None:
        try:
            titulo_el = card.find(class_=SELETOR_TITULO)
            titulo_completo = titulo_el.get("title") if titulo_el else None

            if not titulo_completo:
                return None

            valor_match = PADRAO_VALOR_OFF.search(titulo_completo)
            valor_desconto = (
                float(valor_match.group(1).replace(".", "")) if valor_match else None
            )

            marca_match = PADRAO_MARCA.search(titulo_completo)
            marca = marca_match.group(1).strip() if marca_match else None

            compra_minima, limite = self._extrair_compra_minima_e_limite(card)

            vencimento_el = card.find(class_=SELETOR_VENCIMENTO)
            vencimento = vencimento_el.get_text(strip=True) if vencimento_el else None

            return {
                "chave": self._gerar_chave(titulo_completo, vencimento),
                "titulo_completo": titulo_completo,
                "valor_desconto": valor_desconto,
                "marca": marca,  # None = cupom genérico, não vinculado a marca
                "compra_minima": compra_minima,
                "limite": limite,
                "vencimento": vencimento,
            }
        except Exception as e:
            print(f"[CupomScraper] Erro ao processar cupom: {e}")
            return None

    def _extrair_compra_minima_e_limite(self, card) -> tuple[float | None, float | None]:
        compra_minima = None
        limite = None

        secoes = card.find_all(class_=SELETOR_SUBTITULO_VALOR)
        for secao in secoes:
            label_el = secao.find(class_="text-label")
            valor_el = secao.find(class_="andes-money-amount")

            if not label_el or not valor_el:
                continue

            label_texto = label_el.get_text(strip=True).lower()
            valor = self._extrair_preco_de_aria_label(valor_el)

            if "mínima" in label_texto or "minima" in label_texto:
                compra_minima = valor
            elif "limite" in label_texto:
                limite = valor

        return compra_minima, limite

    def _extrair_preco_de_aria_label(self, elemento) -> float | None:
        aria_label = elemento.get("aria-label", "")
        match = PADRAO_ARIA_PRECO.search(aria_label)
        if not match:
            return None
        reais = int(match.group(1))
        centavos = int(match.group(2)) if match.group(2) else 0
        return reais + (centavos / 100)

    def _gerar_chave(self, titulo: str, vencimento: str | None) -> str:
        """Chave estável pra dedup — mesmo cupom (mesmo texto + validade)
        não deve ser tratado como novo em rodadas diferentes."""
        base = f"{titulo}|{vencimento or ''}"
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
