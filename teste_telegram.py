"""
Teste rápido: só confirma que o TELEGRAM_BOT_TOKEN e o TELEGRAM_CHANNEL_ID
estão certos e o bot consegue postar no canal.

Rode com: python teste_telegram.py
Se der certo, aparece uma mensagem no seu canal e "Sucesso!" no terminal.
Depois que confirmar que funciona, pode apagar esse arquivo.
"""

import os
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from telegram_poster import TelegramPoster

load_dotenv()

telegram = TelegramPoster(
    bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
    channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
)

promocao_teste = {
    "titulo": "Produto de teste — ignore",
    "preco_atual": 99.90,
    "preco_original": 149.90,
    "desconto_percentual": 33,
    "link_afiliado": "https://example.com",
    "imagem_url": None,
}

sucesso = telegram.postar_promocao(promocao_teste)

if sucesso:
    print("Sucesso! Confere o canal, deve ter uma mensagem de teste lá.")
else:
    print("Deu erro. Confere se o TOKEN e o CHANNEL_ID no .env estão certos,")
    print("e se o bot está mesmo como admin do canal.")
