"""
Controle de ofertas já postadas, usando Postgres (ex: Neon, Supabase).

Evita postar o mesmo produto duas vezes: antes de postar, checa se o
item_id já está na tabela; depois de postar com sucesso, registra.

A tabela é criada automaticamente na primeira execução (CREATE TABLE
IF NOT EXISTS), não precisa rodar migration manual.

Usamos pg8000 em vez de psycopg2 de propósito: pg8000 é 100% Python puro,
sem extensão C — evita o erro comum no Windows de precisar do Microsoft
C++ Build Tools instalado só pra compilar o driver do banco.
"""

import urllib.parse
import pg8000


class OfertasRepositorio:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._criar_tabela_se_nao_existir()

    def _conectar(self):
        """
        pg8000 não aceita a connection string inteira de uma vez (diferente
        do psycopg2) — precisa dos pedaços separados (host, usuário, etc).
        Por isso fazemos o parse da URL aqui.
        """
        partes = urllib.parse.urlparse(self.database_url)
        return pg8000.connect(
            user=partes.username,
            password=partes.password,
            host=partes.hostname,
            port=partes.port or 5432,
            database=partes.path.lstrip("/"),
            ssl_context=True,  # Neon/Supabase exigem conexão SSL
        )

    def _criar_tabela_se_nao_existir(self):
        conn = self._conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ofertas_postadas (
                    item_id TEXT PRIMARY KEY,
                    titulo TEXT NOT NULL,
                    postado_em TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def ja_foi_postado(self, item_id: str) -> bool:
        conn = self._conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM ofertas_postadas WHERE item_id = %s",
                (item_id,),
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    def marcar_como_postado(self, item_id: str, titulo: str) -> None:
        conn = self._conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO ofertas_postadas (item_id, titulo)
                VALUES (%s, %s)
                ON CONFLICT (item_id) DO NOTHING
                """,
                (item_id, titulo),
            )
            conn.commit()
        finally:
            conn.close()
