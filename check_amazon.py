"""
Diagnóstico único da Amazon — usa a classe AmazonScraper de verdade,
então sempre reflete o código atual do amazon_scraper.py.

Rode com: python check_amazon.py

APAGUE os arquivos antigos (diagnostico_amazon.py, diagnostico_amazon_v2.py,
diagnostico_amazon_v3.py, diagnostico_amazon_v4.py, ver_resposta_amazon.py)
pra não confundir qual está rodando.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

import requests
from amazon_scraper import AmazonScraper, URL_OFERTAS, HEADERS, MARCADOR_JSON

print(">>> Headers que serão enviados:")
for k, v in HEADERS.items():
    print(f"    {k}: {v}")
print()

resp = requests.get(URL_OFERTAS, headers=HEADERS, timeout=15)
print(f"Status code: {resp.status_code}")
print(f"Tamanho da resposta: {len(resp.text)} caracteres")

idx = resp.text.find(MARCADOR_JSON)
print(f"Marcador encontrado na posição: {idx}")

if idx == -1:
    print("Marcador não encontrado — bloqueio ou página diferente.")
else:
    scraper = AmazonScraper()
    produtos = scraper._extrair_produtos_json(resp.text)
    print(f"Total de produtos BRUTOS no JSON: {len(produtos) if produtos else 0}")

    if produtos:
        passaram = [scraper._normalizar_produto(p) for p in produtos]
        passaram = [p for p in passaram if p]
        print(f"Produtos que passaram no filtro: {len(passaram)}")
        print()
        print("=== Primeiros 3 ===")
        for p in passaram[:3]:
            print(p)
    else:
        print("productSearchResponse veio vazio (bloqueio suave provável).")
