import networkx as nx
import sqlglot
from sqlglot import exp


class TableBaseline:
    def __init__(self, schema: dict | None = None):
        self.schema = dict(schema) if schema else {}
        self.table_graph = nx.DiGraph()

    def add_query(self, sql: str, target_table: str):
        parsed = sqlglot.parse_one(sql)
        cte_names = {cte.alias for cte in parsed.find_all(exp.CTE)}
        source_tables = {
            t.name for t in parsed.find_all(exp.Table) if t.name not in cte_names
        }

        for src in source_tables:
            self.table_graph.add_edge(src, target_table)

        if target_table not in self.schema:
            self.schema[target_table] = {}

        for c in parsed.selects:
            if c.alias_or_name == "*":
                for src in source_tables:
                    if src in self.schema:
                        for col in self.schema[src]:
                            self.schema[target_table][col] = "unknown"
            else:
                self.schema[target_table][c.alias_or_name] = "unknown"

    def get_blast_radius(self, target: str) -> set[str]:
        clean = target.replace("table:", "").replace("cte:", "")
        src_table = clean.split(".")[0]

        if src_table not in self.table_graph:
            return set()

        downstream_tables = nx.descendants(self.table_graph, src_table)
        affected_columns = set()
        for tbl in downstream_tables:
            if tbl in self.schema:
                for col in self.schema[tbl]:
                    affected_columns.add(f"table:{tbl}.{col}")

        return affected_columns