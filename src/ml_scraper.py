"""
Scraper da página de ofertas do Mercado Livre.

IMPORTANTE: os seletores CSS abaixo (find/find_all com class_=...) são um
ponto de partida baseado na estrutura comum de páginas de listagem do ML,
mas o ML muda o HTML com frequência e eu não tenho acesso à internet
pública neste ambiente pra confirmar os seletores atuais.

Antes de usar de verdade, você precisa:
1. Abrir https://www.mercadolivre.com.br/ofertas no navegador
2. Apertar F12 (DevTools) > aba "Elements"
3. Clicar com botão direito num card de produto > "Inspecionar"
4. Ver o nome real das classes CSS usadas hoje e ajustar as constantes
   SELETOR_* lá embaixo.

Isso é normal em projetos de scraping — o "contrato" (o HTML) não é seu,
então ele pode mudar sem aviso. Por isso é bom manter os seletores como
constantes fáceis de achar e trocar, como fiz abaixo.
"""

import requests
from bs4 import BeautifulSoup

# Ajuste estas classes depois de inspecionar o HTML real da página
SELETOR_CARD_PRODUTO = "poly-card"
SELETOR_TITULO = "poly-component__title"
SELETOR_PRECO_ATUAL = "andes-money-amount__fraction"
SELETOR_PRECO_ORIGINAL = "andes-money-amount--previous"
SELETOR_LINK = "poly-component__title"  # geralmente o próprio título é um <a>
SELETOR_IMAGEM = "poly-component__picture"

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
                "Provavelmente os seletores CSS mudaram — confira com F12."
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
            titulo_el = card.find(class_=SELETOR_TITULO)
            titulo = titulo_el.get_text(strip=True) if titulo_el else None
            link = titulo_el.get("href") if titulo_el and titulo_el.name == "a" else None

            preco_atual_el = card.find(class_=SELETOR_PRECO_ATUAL)
            preco_atual = self._parse_preco(preco_atual_el.get_text(strip=True)) if preco_atual_el else None

            preco_original_el = card.find(class_=SELETOR_PRECO_ORIGINAL)
            preco_original = self._parse_preco(preco_original_el.get_text(strip=True)) if preco_original_el else None

            imagem_el = card.find(class_=SELETOR_IMAGEM)
            imagem_url = imagem_el.get("src") or imagem_el.get("data-src") if imagem_el else None

            if not titulo or not link or preco_atual is None:
                return None  # card incompleto, pula

            desconto_percentual = None
            if preco_original and preco_original > preco_atual:
                desconto_percentual = ((preco_original - preco_atual) / preco_original) * 100

            return {
                "titulo": titulo,
                "preco_atual": preco_atual,
                "preco_original": preco_original,
                "desconto_percentual": desconto_percentual,
                "link_afiliado": self._gerar_link_afiliado(link),
                "imagem_url": imagem_url,
            }
        except Exception as e:
            print(f"[MercadoLivreScraper] Erro ao processar card: {e}")
            return None

    def _parse_preco(self, texto: str) -> float | None:
        """Converte '1.234' ou '1234,56' pra float."""
        try:
            limpo = texto.replace(".", "").replace(",", ".")
            return float(limpo)
        except (ValueError, AttributeError):
            return None

    def _gerar_link_afiliado(self, link_produto: str) -> str:
        """
        Aqui entra a etapa MANUAL por enquanto: o Mercado Livre não tem uma
        API pública simples pra gerar link de afiliado automaticamente pra
        afiliados pequenos. O caminho comum é pegar o link do produto e
        passar pelo encurtador/gerador de link de afiliado deles
        (dentro da sua conta em https://www.mercadolivre.com.br/afiliados),
        manualmente, ou automatizar isso depois com Selenium fazendo login
        na sua conta (mais complexo, deixamos pra uma v2).

        Por enquanto, este método só garante que o link é absoluto.
        """
        if link_produto and link_produto.startswith("//"):
            return f"https:{link_produto}"
        return link_produto
