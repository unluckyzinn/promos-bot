# Promo Bot — Canal de Promoções Automático (Telegram)

Bot que busca ofertas no Mercado Livre (scraping) e posta automaticamente
num canal do Telegram. Rodando no GitHub Actions, sem custo de servidor.

A integração com Shopee Affiliate API já está pronta em `src/shopee_client.py`,
mas depende de aprovação de acesso deles (exige CNPJ) — plugue quando liberar.

## Estrutura

```
promo-bot/
├── main.py                    # orquestra: busca oferta -> posta no Telegram
├── src/
│   ├── telegram_poster.py     # só sabe postar no Telegram
│   ├── ml_scraper.py          # busca ofertas no Mercado Livre (ativo)
│   └── shopee_client.py       # busca ofertas na Shopee (aguardando aprovação)
├── .env.example                # modelo de variáveis (copie pra .env)
├── .github/workflows/postar.yml # roda o bot de hora em hora, de graça
└── requirements.txt
```

## Setup local

```bash
cd promo-bot
python -m venv venv
source venv/bin/activate      # no Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # depois edite o .env com suas credenciais reais
python main.py
```

## ⚠️ IMPORTANTE: antes de rodar — ajustar os seletores do scraper

Eu não tenho acesso à internet pública neste ambiente pra confirmar a
estrutura HTML atual do Mercado Livre, então os seletores CSS em
`src/ml_scraper.py` (as constantes `SELETOR_*` no topo do arquivo) são um
ponto de partida, não uma garantia de que vão funcionar de primeira.

**Como ajustar (leva uns 5 minutos):**

1. Abra https://www.mercadolivre.com.br/ofertas no Chrome.
2. Aperte `F12` pra abrir o DevTools.
3. Clique no ícone de seta (inspecionar elemento) e clique em cima do
   título de um produto na página.
4. O DevTools vai destacar o HTML correspondente — veja o nome da `class`
   usada ali.
5. Repita pra: preço atual, preço original (o riscado), imagem e o card
   inteiro do produto.
6. Cole os nomes reais nas constantes `SELETOR_*` em `ml_scraper.py`.

Se rodar e aparecer a mensagem "Nenhum card encontrado", é sinal de que
os seletores estão desatualizados — repita esse processo.

## Onde pegar cada credencial

- **TELEGRAM_BOT_TOKEN**: fale com @BotFather no Telegram, `/newbot`.
- **TELEGRAM_CHANNEL_ID**: se o canal for público, é `@nomedocanal`.
  Adicione o bot como admin do canal antes de testar.

## Sobre o link de afiliado do Mercado Livre

Diferente da Shopee, o ML não tem uma API pública simples pra gerar link
de afiliado automaticamente pra afiliados pequenos. Por enquanto o script
te entrega o **link direto do produto** — você precisa passar esse link
pelo gerador de link de afiliado dentro da sua conta em
`mercadolivre.com.br/afiliados` manualmente antes de postar, ou aceitar
postar sem afiliação por enquanto. Automatizar isso com login (Selenium)
é uma evolução futura, mais complexa.

## Automação no GitHub Actions

Configure os secrets em Settings → Secrets and variables → Actions:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

(Os secrets da Shopee só são necessários quando você plugar aquele módulo.)

## Próximos passos (quando quiser expandir)

- Gerar o link de afiliado do ML automaticamente (via login/Selenium ou
  se a Shopee aprovar, focar energia lá que é mais simples).
- Adicionar Amazon quando a PA-API for liberada (3 vendas em 180 dias).
- Guardar no banco os produtos já postados, pra não repetir a mesma
  oferta em rodadas seguidas (hoje o script não tem essa checagem).
