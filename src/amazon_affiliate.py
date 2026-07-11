"""
Gerador de link de afiliado da Amazon.

Bem mais simples que o do Mercado Livre: a Amazon rastreia comissão só
pelo parâmetro "?tag=SEU_ASSOCIATE_TAG" na URL — sem precisar de cookie,
sessão logada, nem chamada de API nenhuma. Isso funciona igual rodando
local ou na nuvem (GitHub Actions), sem as limitações que tivemos com o
mecanismo do Mercado Livre.
"""


class AmazonAffiliateLinkBuilder:
    def __init__(self, associate_tag: str):
        self.associate_tag = associate_tag

    def gerar_link(self, url_produto: str) -> str:
        separador = "&" if "?" in url_produto else "?"
        return f"{url_produto}{separador}tag={self.associate_tag}"
