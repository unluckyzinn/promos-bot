"""
Controle de ofertas já postadas, usando Postgres (ex: Neon, Supabase).

Evita postar o mesmo produto duas vezes: antes de postar, checa se o
item_id já está na tabela; depois de postar com sucesso, registra.

A tabela é criada automaticamente na primeira execução (CREATE TABLE
IF NOT EXISTS), não precisa rodar migration manual.

Usamos pg8000 em vez de psycopg2 de propósito: pg8000 é 100% Python puro,
sem extensão C — evita o erro comum no Windows de precisar do Microsoft
C++ Build Tools instalado só pra compilar o driver do banco.

Mantemos UMA conexão reaproveitada (em vez de abrir uma nova por consulta)
pra reduzir o número de handshakes SSL — isso diminui bastante a chance
de erros transitórios de rede, além de ser mais rápido. Se a conexão
cair no meio do uso (ex: banco "dormiu" no plano free), reconectamos
automaticamente uma vez antes de desistir.
"""

import urllib.parse
import pg8000


class OfertasRepositorio:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn = None
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

    def _obter_conexao(self):
        if self._conn is None:
            self._conn = self._conectar()
        return self._conn

    def _executar(self, query: str, params: tuple = (), buscar: bool = False):
        """Executa uma query reaproveitando a conexão. Se der erro de
        conexão (ex: banco dormiu), tenta reconectar uma vez."""
        try:
            conn = self._obter_conexao()
            cur = conn.cursor()
            cur.execute(query, params)
            resultado = cur.fetchone() if buscar else None
            conn.commit()
            return resultado
        except Exception as e:
            print(f"[OfertasRepositorio] Conexão falhou ({e}), reconectando...")
            try:
                if self._conn:
                    self._conn.close()
            except Exception:
                pass
            self._conn = self._conectar()
            cur = self._conn.cursor()
            cur.execute(query, params)
            resultado = cur.fetchone() if buscar else None
            self._conn.commit()
            return resultado

    def _criar_tabela_se_nao_existir(self):
        self._executar(
            """
            CREATE TABLE IF NOT EXISTS ofertas_postadas (
                item_id TEXT PRIMARY KEY,
                titulo TEXT NOT NULL,
                postado_em TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

    def ja_foi_postado(self, item_id: str) -> bool:
        resultado = self._executar(
            "SELECT 1 FROM ofertas_postadas WHERE item_id = %s",
            (item_id,),
            buscar=True,
        )
        return resultado is not None

    def marcar_como_postado(self, item_id: str, titulo: str) -> None:
        self._executar(
            """
            INSERT INTO ofertas_postadas (item_id, titulo)
            VALUES (%s, %s)
            ON CONFLICT (item_id) DO NOTHING
            """,
            (item_id, titulo),
        )
