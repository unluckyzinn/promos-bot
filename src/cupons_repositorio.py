"""
Controle de cupons já postados sozinhos (sem produto casado), pra não
repetir o mesmo cupom em toda execução enquanto ele estiver ativo.

Mesma abordagem do ofertas_repositorio.py: uma conexão só, reaproveitada,
com reconexão automática se cair (ex: banco "dormiu" no plano free).
"""

import urllib.parse
import pg8000


class CuponsRepositorio:
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
        try:
            conn = self._obter_conexao()
            cur = conn.cursor()
            cur.execute(query, params)
            resultado = cur.fetchone() if buscar else None
            conn.commit()
            return resultado
        except Exception as e:
            print(f"[CuponsRepositorio] Conexão falhou ({e}), reconectando...")
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
            CREATE TABLE IF NOT EXISTS cupons_postados (
                chave TEXT PRIMARY KEY,
                titulo TEXT NOT NULL,
                postado_em TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

    def ja_foi_postado(self, chave: str) -> bool:
        resultado = self._executar(
            "SELECT 1 FROM cupons_postados WHERE chave = %s",
            (chave,),
            buscar=True,
        )
        return resultado is not None

    def marcar_como_postado(self, chave: str, titulo: str) -> None:
        self._executar(
            """
            INSERT INTO cupons_postados (chave, titulo)
            VALUES (%s, %s)
            ON CONFLICT (chave) DO NOTHING
            """,
            (chave, titulo),
        )
