"""
Gerador de link de afiliado do Mercado Livre.

Como funciona: replica a chamada que o botão "Gerar Link" do portal oficial
de afiliados faz (POST /affiliate-program/api/v2/affiliates/createLink),
usando os cookies de uma sessão já logada no navegador.

LIMITAÇÃO IMPORTANTE: os cookies de sessão expiram de tempos em tempos.
Quando isso acontecer, a chamada vai começar a falhar (normalmente com
401 ou 403) — nesse caso, repita o passo de copiar o Cookie do navegador
e atualize o ML_COOKIE_HEADER no seu .env.

TAMBÉM IMPORTANTE: essa chamada foi desenhada pelo ML pra ser feita de
dentro de um navegador logado, não por automação externa. É bem provável
que funcione rodando local (na sua máquina, mesmo IP do navegador onde
você logou), mas tem chance de ser bloqueada se você tentar rodar isso
no GitHub Actions (IP de datacenter, sem o mesmo "contexto" do navegador).
Por enquanto, use esse módulo só na execução local.
"""

import re
import requests

ENDPOINT = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"

# Extrai o ID do produto de uma URL do ML. Aceita variantes como
# MLB1055308835 (produto comum) e MLBU4052258844 (algumas variações
# de produto, ex: cor/tamanho diferentes na mesma publicação).
PADRAO_ITEM_ID = re.compile(r"(MLBU?\d+)")

# Headers extras pra parecer uma chamada vinda de dentro do navegador.
# O 'requests' por padrão manda User-Agent "python-requests/x.x", o que é
# um sinal claro de automação pra qualquer sistema anti-bot — e sites como
# o ML costumam também conferir Referer/Origin, não só o cookie/csrf.
USER_AGENT_NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


class MercadoLivreAffiliateLinkGenerator:
    def __init__(self, cookie_header: str, tag: str):
        """
        cookie_header: o valor inteiro do header 'Cookie' copiado do
                       DevTools (Network > createLink > Request Headers).
        tag: seu identificador de afiliado (ex: "filhomibson20220919203726").
        """
        self.cookie_header = cookie_header
        self.tag = tag
        self.csrf_token = self._extrair_csrf(cookie_header)

    def _extrair_csrf(self, cookie_header: str) -> str | None:
        """O header x-csrf-token precisa ser igual ao valor do cookie _csrf
        (padrão 'double submit cookie')."""
        match = re.search(r"_csrf=([^;]+)", cookie_header)
        return match.group(1) if match else None

    def _extrair_item_id(self, url_produto: str) -> str | None:
        match = PADRAO_ITEM_ID.search(url_produto)
        return match.group(1) if match else None

    def gerar_link(self, url_produto: str, item_id: str | None = None) -> str | None:
        """Recebe a URL limpa do produto e retorna o link de afiliado
        (short_url), ou None se não conseguir gerar.

        Se item_id não for passado, tenta extrair da própria URL.
        """
        if item_id is None:
            item_id = self._extrair_item_id(url_produto)

        if not item_id:
            print(f"[MLAffiliateLinkGenerator] Não achei o item_id em: {url_produto}")
            return None

        if not self.csrf_token:
            print(
                "[MLAffiliateLinkGenerator] Cookie sem _csrf — provavelmente "
                "a sessão expirou. Copie o Cookie de novo no navegador e "
                "atualize o .env."
            )
            return None

        payload = {
            "itemId": item_id,
            "tag": self.tag,
            "type": "product",
            "urls": [url_produto],
            "extraCommission": "false",
        }

        headers = {
            "Content-Type": "application/json",
            "x-csrf-token": self.csrf_token,
            "Cookie": self.cookie_header,
            "User-Agent": USER_AGENT_NAVEGADOR,
            "Referer": "https://www.mercadolivre.com.br/afiliados/linkbuilder",
            "Origin": "https://www.mercadolivre.com.br",
        }

        try:
            resp = requests.post(ENDPOINT, json=payload, headers=headers, timeout=15)
        except requests.RequestException as e:
            print(f"[MLAffiliateLinkGenerator] Erro de conexão: {e}")
            return None

        if resp.status_code != 200:
            print(
                f"[MLAffiliateLinkGenerator] Erro HTTP {resp.status_code} — "
                "provavelmente a sessão (cookie) expirou. Copie de novo no navegador."
            )
            return None

        dados = resp.json()
        urls = dados.get("urls", [])

        if not urls or not urls[0].get("created"):
            print(f"[MLAffiliateLinkGenerator] Resposta sem link criado: {dados}")
            return None

        return urls[0].get("short_url")
