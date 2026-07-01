"""
Script principal: busca ofertas no Mercado Livre e posta no canal do Telegram.

Uso local:
    python main.py

Uso agendado (recomendado): GitHub Actions com schedule, rodando este
script a cada X minutos, sem precisar de servidor ligado 24h.

NOTA: A integração com Shopee (src/shopee_client.py) está pronta mas
depende de aprovação de acesso à Open API deles (precisa de CNPJ).
Enquanto isso não sai, o fluxo principal usa o Mercado Livre via scraping.
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from ml_scraper import MercadoLivreScraper
from telegram_poster import TelegramPoster

load_dotenv()


def main():
    telegram = TelegramPoster(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
    )

    mercado_livre = MercadoLivreScraper()

    min_desconto = float(os.environ.get("MIN_DESCONTO_PERCENTUAL", 30))

    ofertas = mercado_livre.buscar_ofertas(limite=10)

    if not ofertas:
        print("Nenhuma oferta encontrada nesta rodada.")
        return

    postadas = 0
    for oferta in ofertas:
        # Filtro simples de qualidade — ajuste esse critério como quiser
        if oferta.get("desconto_percentual") is not None:
            if oferta["desconto_percentual"] < min_desconto:
                continue

        sucesso = telegram.postar_promocao(oferta)
        if sucesso:
            postadas += 1

    print(f"Postagem concluída: {postadas}/{len(ofertas)} ofertas postadas.")


if __name__ == "__main__":
    main()
