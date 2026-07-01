"""
Módulo de postagem no Telegram.

Responsabilidade única: receber uma promoção já formatada e mandar pro canal.
Não sabe nada sobre Shopee, Amazon ou Mercado Livre — isso é de propósito,
pra você poder plugar qualquer fonte de promoção sem mexer aqui.
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

        Retorna True se conseguiu postar, False se deu erro.
        """
        texto = self._montar_texto(promocao)

        if promocao.get("imagem_url"):
            return self._postar_com_imagem(texto, promocao["imagem_url"])
        return self._postar_somente_texto(texto)

    def _montar_texto(self, promocao: dict) -> str:
        linhas = [f"🔥 <b>{promocao['titulo']}</b>", ""]

        if promocao.get("preco_original") and promocao.get("desconto_percentual"):
            linhas.append(
                f"~R$ {promocao['preco_original']:.2f}~ → "
                f"<b>R$ {promocao['preco_atual']:.2f}</b> "
                f"({promocao['desconto_percentual']:.0f}% OFF)"
            )
        else:
            linhas.append(f"<b>R$ {promocao['preco_atual']:.2f}</b>")

        linhas.append("")
        linhas.append(f'🛒 <a href="{promocao["link_afiliado"]}">Comprar agora</a>')

        return "\n".join(linhas)

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
