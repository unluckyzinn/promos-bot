"""
Scraper da página de ofertas do Mercado Livre.

STATUS DOS SELETORES (confirmados via inspeção real em 01/07/2026):
- Card do produto: CONFIRMADO (classe "poly-card").
- Título/link: CONFIRMADO (classe "poly-component__title").
- Preço original, preço atual e desconto: CONFIRMADOS. O ML coloca o valor
  por extenso no atributo aria-label (ex: "Antes: 699 reais com 90
  centavos"), o que é mais estável do que ler os <span> de fração/centavos
  separadamente — é essa abordagem que usamos aqui.
- SELETOR_IMAGEM: ainda não confirmado via F12, é estimativa. Não é
  crítico — se vier None, o bot posta sem foto, só isso.

Lembre-se: o ML pode mudar essas classes no futuro sem aviso — se um dia
o script parar de achar ofertas, esse é o primeiro lugar pra checar.
"""

import re
import re
import requests
from bs4 import BeautifulSoup

# Confirmado via inspeção real (F12) em 01/07/2026 — pode mudar no futuro
SELETOR_CARD_PRODUTO = "poly-card"
SELETOR_TITULO_LINK = "poly-component__title"       # <a> com título E href
SELETOR_PRECO_ORIGINAL = "andes-money-amount--previous"  # o <s> riscado
SELETOR_PRECO_ATUAL = "poly-price__amount"          # o preço em destaque
SELETOR_DESCONTO_LABEL = "poly-price__disc-label"   # ex: "77% OFF"
SELETOR_IMAGEM = "poly-component__picture"

# Ex: "Antes: 699 reais com 90 centavos" ou "Agora: 159 reais"
PADRAO_ARIA_PRECO = re.compile(r"(\d+)\s*reais(?:\s*com\s*(\d+)\s*centavos)?")
PADRAO_DESCONTO = re.compile(r"(\d+)\s*%")
# Aceita MLB1055308835 e variantes como MLBU4052258844
PADRAO_ITEM_ID = re.compile(r"(MLBU?\d+)")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}


class MercadoLivreScraper:
    def __init__(self, url_ofertas: str = "https://www.mercadolivre.com.br/ofertas"):
        self.url_ofertas = url_ofertas

    def buscar_ofertas(self, limite: int = 10) -> list[dict]:
        resp = requests.get(self.url_ofertas, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            print(f"[MercadoLivreScraper] Erro HTTP: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all(class_=SELETOR_CARD_PRODUTO)[:limite]

        if not cards:
            print(
                "[MercadoLivreScraper] Nenhum card encontrado. "
                "Provavelmente SELETOR_CARD_PRODUTO mudou — confira com F12."
            )
            return []

        promocoes = []
        for card in cards:
            promocao = self._extrair_promocao(card)
            if promocao:
                promocoes.append(promocao)

        return promocoes

    def _extrair_promocao(self, card) -> dict | None:
        try:
            titulo_el = card.find(class_=SELETOR_TITULO_LINK)
            titulo = titulo_el.get_text(strip=True) if titulo_el else None
            link = titulo_el.get("href") if titulo_el else None

            preco_atual_el = card.find(class_=SELETOR_PRECO_ATUAL)
            preco_atual = self._extrair_preco_de_aria_label(preco_atual_el)

            preco_original_el = card.find(class_=SELETOR_PRECO_ORIGINAL)
            preco_original = self._extrair_preco_de_aria_label(preco_original_el)

            desconto_percentual = self._extrair_desconto(card)

            imagem_el = card.find(class_=SELETOR_IMAGEM)
            imagem_url = imagem_el.get("src") or imagem_el.get("data-src") if imagem_el else None

            if not titulo or not link or preco_atual is None:
                return None  # card incompleto, pula

            # Se não veio o label "% OFF" pronto, calcula pelo preço (fallback)
            if desconto_percentual is None and preco_original and preco_original > preco_atual:
                desconto_percentual = ((preco_original - preco_atual) / preco_original) * 100

            link_limpo = self._limpar_link(link)
            item_id_match = PADRAO_ITEM_ID.search(link_limpo)
            item_id = item_id_match.group(1) if item_id_match else None

            return {
                "item_id": item_id,
                "titulo": titulo,
                "preco_atual": preco_atual,
                "preco_original": preco_original,
                "desconto_percentual": desconto_percentual,
                "link_afiliado": link_limpo,
                "imagem_url": imagem_url,
            }
        except Exception as e:
            print(f"[MercadoLivreScraper] Erro ao processar card: {e}")
            return None

    def _extrair_preco_de_aria_label(self, elemento) -> float | None:
        """
        Lê o aria-label do elemento de preço, ex: "Agora: 159 reais com 90
        centavos", e retorna 159.90 como float. Mais robusto que ler os
        <span> de fração/centavos, porque não depende de como o ML
        organiza o HTML interno — só do texto de acessibilidade.
        """
        if elemento is None:
            return None

        aria_label = elemento.get("aria-label", "")
        match = PADRAO_ARIA_PRECO.search(aria_label)
        if not match:
            return None

        reais = int(match.group(1))
        centavos = int(match.group(2)) if match.group(2) else 0
        return reais + (centavos / 100)

    def _extrair_desconto(self, card) -> float | None:
        """Lê o label pronto tipo '77% OFF' que o ML já calcula e mostra."""
        label_el = card.find(class_=SELETOR_DESCONTO_LABEL)
        if label_el is None:
            return None

        match = PADRAO_DESCONTO.search(label_el.get_text(strip=True))
        return float(match.group(1)) if match else None

    def _limpar_link(self, link_produto: str) -> str:
        """
        O link vem com parâmetros de tracking do ML (?pdp_filters=deal:...
        &tracking_id=...&sid=offers). Isso não quebra o link, mas deixa
        sujo — aqui cortamos tudo depois do '?' pra ficar só a URL do produto.

        IMPORTANTE: isso ainda NÃO é um link de afiliado. O Mercado Livre
        não tem API pública simples pra gerar link de afiliado automático
        pra afiliados pequenos. O caminho é pegar essa URL limpa e gerar o
        link de afiliado manualmente em mercadolivre.com.br/afiliados,
        ou automatizar depois com login (Selenium) — fica como v2.
        """
        if not link_produto:
            return link_produto
        if link_produto.startswith("//"):
            link_produto = f"https:{link_produto}"
        return link_produto.split("?")[0]
