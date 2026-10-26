"""Adaptador de banco de dados nativo PostgreSQL (Cloud SQL) compatível com a API do Supabase client.

Permite que todas as rotas do backend continuem funcionando de forma assíncrona
(usando a sintaxe db.table(...).select(...).eq(...).execute()) conectando-se diretamente
ao PostgreSQL gerenciado pelo Cloud SQL / Firebase Data Connect sem necessidade do Supabase.
"""

from typing import Any, Dict, List, Optional
import json
import logging
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("Pool de conexões PostgreSQL inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao inicializar pool PostgreSQL: {e}")
            raise e
    return _pool


class QueryResult:
    def __init__(self, data: List[Dict[str, Any]], count: Optional[int] = None):
        self.data = data
        self.count = count if count is not None else len(data)


def _normalize_row(row) -> Dict[str, Any]:
    """Converte UUID, datetime e tipos complexos do asyncpg para compatibilidade com o formato JSON retornado pelo Supabase."""
    import uuid
    import datetime
    out = {}
    for k, v in dict(row).items():
        if isinstance(v, uuid.UUID):
            out[k] = str(v)
        elif isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


class TableQueryBuilder:
    def __init__(self, pool: asyncpg.Pool, table_name: str):
        self.pool = pool
        self.table_name = table_name
        self.op_type = "select"  # "select", "insert", "update", "delete"
        self.select_columns = "*"
        self.insert_data: Any = None
        self.update_data: Dict[str, Any] = {}
        self.where_clauses: List[str] = []
        self.params: List[Any] = []
        self.order_by_clause: Optional[str] = None
        self.limit_val: Optional[int] = None
        self.offset_val: Optional[int] = None

    def select(self, columns: str = "*", count: Optional[str] = None):
        self.op_type = "select"
        self.select_columns = columns
        return self

    def insert(self, values: Any):
        self.op_type = "insert"
        self.insert_data = values
        return self

    def update(self, values: Dict[str, Any]):
        self.op_type = "update"
        self.update_data = values
        return self

    def delete(self):
        self.op_type = "delete"
        return self

    def eq(self, column: str, value: Any):
        self.params.append(value)
        self.where_clauses.append(f'"{column}" = ${len(self.params)}')
        return self

    def neq(self, column: str, value: Any):
        self.params.append(value)
        self.where_clauses.append(f'("{column}" != ${len(self.params)} OR "{column}" IS NULL)')
        return self

    def ilike(self, column: str, value: Any):
        self.params.append(value)
        self.where_clauses.append(f'"{column}" ILIKE ${len(self.params)}')
        return self

    def like(self, column: str, value: Any):
        self.params.append(value)
        self.where_clauses.append(f'"{column}" LIKE ${len(self.params)}')
        return self

    def or_(self, expr: str):
        # Ex: "category.ilike.moving_sale:%,name.ilike.[MUDANÇA]%" or "email.eq.foo,phone.eq.bar"
        parts = expr.split(",")
        sub_clauses = []
        for part in parts:
            part = part.strip()
            if ".eq." in part:
                col, val = part.split(".eq.", 1)
                # Parse booleans se for 'true' ou 'false'
                if val.lower() == "true":
                    val_parsed = True
                elif val.lower() == "false":
                    val_parsed = False
                elif val.lower() == "null":
                    sub_clauses.append(f'"{col}" IS NULL')
                    continue
                else:
                    val_parsed = val
                self.params.append(val_parsed)
                sub_clauses.append(f'"{col}" = ${len(self.params)}')
            elif ".ilike." in part:
                col, val = part.split(".ilike.", 1)
                self.params.append(val)
                sub_clauses.append(f'"{col}" ILIKE ${len(self.params)}')
            elif ".like." in part:
                col, val = part.split(".like.", 1)
                self.params.append(val)
                sub_clauses.append(f'"{col}" LIKE ${len(self.params)}')
            elif ".is." in part:
                col, val = part.split(".is.", 1)
                if val.lower() == "null":
                    sub_clauses.append(f'"{col}" IS NULL')
                elif val.lower() == "true":
                    sub_clauses.append(f'"{col}" IS TRUE')
                elif val.lower() == "false":
                    sub_clauses.append(f'"{col}" IS FALSE')
                else:
                    self.params.append(val)
                    sub_clauses.append(f'"{col}" IS ${len(self.params)}')
        if sub_clauses:
            self.where_clauses.append(f"({' OR '.join(sub_clauses)})")
        return self

    def in_(self, column: str, values: List[Any]):
        self.params.append(values)
        self.where_clauses.append(f'"{column}" = ANY(${len(self.params)})')
        return self

    def order(self, column: str, desc: bool = False):
        direction = "DESC" if desc else "ASC"
        self.order_by_clause = f'"{column}" {direction}'
        return self

    def limit(self, count: int):
        self.limit_val = count
        return self

    def offset(self, start: int):
        self.offset_val = start
        return self

    def range(self, start: int, end: int):
        """Supabase compatibility: .range(start, end) where end is inclusive."""
        self.offset_val = start
        self.limit_val = max(0, end - start + 1)
        return self

    async def execute(self) -> QueryResult:
        async with self.pool.acquire() as conn:
            where_sql = f" WHERE {' AND '.join(self.where_clauses)}" if self.where_clauses else ""

            if self.op_type == "select":
                order_sql = f" ORDER BY {self.order_by_clause}" if self.order_by_clause else ""
                limit_sql = f" LIMIT {self.limit_val}" if self.limit_val is not None else ""
                offset_sql = f" OFFSET {self.offset_val}" if self.offset_val is not None else ""
                
                cols = "*" if self.select_columns in ("*", None) else self.select_columns
                sql = f'SELECT {cols} FROM "{self.table_name}"{where_sql}{order_sql}{limit_sql}{offset_sql};'
                rows = await conn.fetch(sql, *self.params)
                data = [_normalize_row(r) for r in rows]
                return QueryResult(data)

            elif self.op_type == "insert":
                if isinstance(self.insert_data, list):
                    records = self.insert_data
                else:
                    records = [self.insert_data]

                inserted_data = []
                for record in records:
                    keys = list(record.keys())
                    vals = []
                    for k in keys:
                        v = record[k]
                        if isinstance(v, dict):
                            vals.append(json.dumps(v))
                        elif isinstance(v, list):
                            # Se for lista de strings ou números (ex: languages, services_offered),
                            # envia diretamente como lista nativa para o PostgreSQL aceitar como ARRAY.
                            # Se for lista de dicionários/objetos, serializa para JSON.
                            if v and isinstance(v[0], (dict, list)):
                                vals.append(json.dumps(v))
                            else:
                                vals.append(v)
                        else:
                            vals.append(v)
                    cols_str = ", ".join(f'"{k}"' for k in keys)
                    placeholders = ", ".join(f"${i+1}" for i in range(len(vals)))
                    sql = f'INSERT INTO "{self.table_name}" ({cols_str}) VALUES ({placeholders}) RETURNING *;'
                    row = await conn.fetchrow(sql, *vals)
                    if row:
                        inserted_data.append(_normalize_row(row))
                return QueryResult(inserted_data)

            elif self.op_type == "update":
                set_parts = []
                exec_params = []
                for k, v in self.update_data.items():
                    if isinstance(v, dict):
                        val = json.dumps(v)
                    elif isinstance(v, list):
                        if v and isinstance(v[0], (dict, list)):
                            val = json.dumps(v)
                        else:
                            val = v
                    else:
                        val = v
                    exec_params.append(val)
                    set_parts.append(f'"{k}" = ${len(exec_params)}')

                where_parts = []
                for clause in self.where_clauses:
                    # Se houver placeholders ${i} na cláusula WHERE, ajusta pelo offset de exec_params
                    where_parts.append(clause)
                for val in self.params:
                    exec_params.append(val)

                # Reindexa os placeholders no WHERE para bater com a ordem em exec_params
                where_sql = ""
                if self.where_clauses:
                    offset = len(self.update_data)
                    adjusted_clauses = []
                    for i, clause in enumerate(self.where_clauses):
                        # Troca $1, $2 pelo offset correspondente
                        idx = offset + i + 1
                        import re
                        adjusted_clause = re.sub(r'\$\d+', f'${idx}', clause)
                        adjusted_clauses.append(adjusted_clause)
                    where_sql = f" WHERE {' AND '.join(adjusted_clauses)}"

                set_sql = ", ".join(set_parts)
                sql = f'UPDATE "{self.table_name}" SET {set_sql}{where_sql} RETURNING *;'
                rows = await conn.fetch(sql, *exec_params)
                data = [_normalize_row(r) for r in rows]
                return QueryResult(data)

            elif self.op_type == "delete":
                sql = f'DELETE FROM "{self.table_name}"{where_sql} RETURNING *;'
                rows = await conn.fetch(sql, *self.params)
                data = [_normalize_row(r) for r in rows]
                return QueryResult(data)

            return QueryResult([])


class PostgresDatabaseClient:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    def table(self, table_name: str) -> TableQueryBuilder:
        return TableQueryBuilder(self.pool, table_name)


async def get_service_db() -> PostgresDatabaseClient:
    pool = await get_pool()
    return PostgresDatabaseClient(pool)


async def get_anon_db() -> PostgresDatabaseClient:
    return await get_service_db()


async def get_db() -> PostgresDatabaseClient:
    return await get_service_db()
