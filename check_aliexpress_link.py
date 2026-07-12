"""
Teste isolado do AliExpressAffiliateLinkGenerator.

Rode com: python check_aliexpress_link.py
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from aliexpress_affiliate import AliExpressAffiliateLinkGenerator

load_dotenv()

cookie = os.environ.get("ALIEXPRESS_COOKIE_HEADER")

if not cookie:
    print("ALIEXPRESS_COOKIE_HEADER não configurado no .env")
else:
    gerador = AliExpressAffiliateLinkGenerator(cookie_header=cookie)
    # Usa o mesmo item_id do fone de ouvido que já vimos antes
    link = gerador.gerar_link("1005006630379814")
    print(f"Link gerado: {link}")
