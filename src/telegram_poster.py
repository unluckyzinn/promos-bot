"""
Módulo de postagem no Telegram.

Responsabilidade única: receber uma promoção (ou cupom) já formatada e
mandar pro canal. Não sabe nada sobre Shopee, Amazon ou Mercado Livre —
isso é de propósito, pra você poder plugar qualquer fonte sem mexer aqui.

Layout inspirado em grupos de promoção populares (ex: Magalu): título +
preço na mesma linha, com o PREÇO servindo de link (em vez de uma linha
separada "Comprar agora"), e cupom mostrado com emoji de ticket + link
próprio de aplicação.
"""

import requests


class TelegramPoster:
    def __init__(self, bot_token: str, channel_id: str):
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.channel_id = channel_id

    def postar_promocao(self, promocao: dict) -> bool:
        """
        Espera um dict com as chaves:
            titulo (str)
            preco_atual (float)
            preco_original (float | None)
            desconto_percentual (float | None)
            link_afiliado (str)
            imagem_url (str | None)
            cupom (dict | None) — opcional, ver CupomScraper pro formato

        Retorna True se conseguiu postar, False se deu erro.
        """
        texto = self._montar_texto(promocao)

        if promocao.get("imagem_url"):
            return self._postar_com_imagem(texto, promocao["imagem_url"])
        return self._postar_somente_texto(texto)

    def postar_cupom_sozinho(self, cupom: dict) -> bool:
        """
        Posta um cupom sem produto casado. Espera o dict retornado pelo
        CupomScraper (titulo_completo, compra_minima, limite, vencimento, url).
        """
        texto = self._montar_texto_cupom(cupom)
        return self._postar_somente_texto(texto)

    def _formatar_preco(self, valor: float) -> str:
        """Formata no padrão brasileiro: vírgula decimal, ponto de milhar.
        Ex: 1234.5 -> '1.234,50'"""
        texto = f"{valor:,.2f}"  # formato US: '1,234.50'
        texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
        return texto

    def _montar_texto(self, promocao: dict) -> str:
        linhas = [f"🔥 <b>{promocao['titulo']}</b>", ""]

        if promocao.get("preco_original") and promocao.get("desconto_percentual"):
            linhas.append(
                f"~R$ {self._formatar_preco(promocao['preco_original'])}~ → "
                f"<b>R$ {self._formatar_preco(promocao['preco_atual'])}</b> "
                f"({promocao['desconto_percentual']:.0f}% OFF)"
            )
        else:
            linhas.append(f"<b>R$ {self._formatar_preco(promocao['preco_atual'])}</b>")

        linhas.append("")
        linhas.append(f'🛒 <a href="{promocao["link_afiliado"]}">Comprar agora</a>')

        return "\n".join(linhas)

    def _montar_texto_cupom(self, cupom: dict) -> str:
        linhas = ["🎫 <b>Cupom disponível no Mercado Livre</b>", ""]
        linhas.extend(self._linhas_do_cupom(cupom))
        linhas.append(f'👉 <a href="{cupom["url"]}">Aplicar cupom</a>')
        return "\n".join(linhas)

    def _linhas_do_cupom(self, cupom: dict) -> list:
        linhas = [f"🎫 <b>CUPOM: {cupom['titulo_completo']}</b>"]

        detalhes = []
        if cupom.get("compra_minima"):
            detalhes.append(f"compra mínima R$ {self._formatar_preco(cupom['compra_minima'])}")
        if cupom.get("vencimento"):
            detalhes.append(cupom["vencimento"])
        if detalhes:
            linhas.append(" · ".join(detalhes))

        linhas.append("")
        return linhas

    def _postar_somente_texto(self, texto: str) -> bool:
        resp = requests.post(
            f"{self.base_url}/sendMessage",
            json={
                "chat_id": self.channel_id,
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        return self._checar_resposta(resp)

    def _postar_com_imagem(self, texto: str, imagem_url: str) -> bool:
        resp = requests.post(
            f"{self.base_url}/sendPhoto",
            json={
                "chat_id": self.channel_id,
                "photo": imagem_url,
                "caption": texto,
                "parse_mode": "HTML",
            },
            timeout=15,
        )
        return self._checar_resposta(resp)

    def _checar_resposta(self, resp: requests.Response) -> bool:
        if resp.status_code != 200:
            print(f"[TelegramPoster] Erro ao postar: {resp.status_code} - {resp.text}")
            return False
        return True
