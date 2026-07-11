"""
Controle de cupons já postados sozinhos (sem produto casado), pra não
repetir o mesmo cupom em toda execução enquanto ele estiver ativo.

Usa a mesma abordagem do ofertas_repositorio.py (pg8000, sem compilação C).
"""

import urllib.parse
import pg8000


class CuponsRepositorio:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._criar_tabela_se_nao_existir()

    def _conectar(self):
        partes = urllib.parse.urlparse(self.database_url)
        return pg8000.connect(
            user=partes.username,
            password=partes.password,
            host=partes.hostname,
            port=partes.port or 5432,
            database=partes.path.lstrip("/"),
            ssl_context=True,
        )

    def _criar_tabela_se_nao_existir(self):
        conn = self._conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cupons_postados (
                    chave TEXT PRIMARY KEY,
                    titulo TEXT NOT NULL,
                    postado_em TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def ja_foi_postado(self, chave: str) -> bool:
        conn = self._conectar()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM cupons_postados WHERE chave = %s", (chave,))
            return cur.fetchone() is not None
        finally:
            conn.close()

    def marcar_como_postado(self, chave: str, titulo: str) -> None:
        conn = self._conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO cupons_postados (chave, titulo)
                VALUES (%s, %s)
                ON CONFLICT (chave) DO NOTHING
                """,
                (chave, titulo),
            )
            conn.commit()
        finally:
            conn.close()
