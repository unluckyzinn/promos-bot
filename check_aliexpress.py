"""
Teste isolado do AliExpressScraper — só busca e mostra produtos,
sem postar no Telegram nem gerar link de afiliado ainda.

Rode com: python check_aliexpress.py
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

import os
from dotenv import load_dotenv

load_dotenv()

from aliexpress_scraper import AliExpressScraper

cookie = os.environ.get("ALIEXPRESS_COOKIE_HEADER")
scraper = AliExpressScraper(cookie_header=cookie)  # comissao_elevada=True por padrão

print("Buscando ofertas da aba 'Comissão elevada'...")
ofertas = scraper.buscar_ofertas(limite=20)

print(f"\nTotal de ofertas encontradas: {len(ofertas)}\n")

for oferta in ofertas[:5]:
    print(f"- {oferta['titulo'][:60]}")
    print(f"  R$ {oferta['preco_original']} -> R$ {oferta['preco_atual']} "
          f"({oferta['desconto_percentual']:.0f}% OFF)")
    print(f"  {oferta['link_afiliado']}")
    print()
