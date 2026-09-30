import networkx as nx
import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage


class LineageEngine:
    def __init__(self, schema: dict | None = None):
        self.schema = dict(schema) if schema else {}
        self.graph = nx.DiGraph()
        self.influence_graph = nx.DiGraph()

    def _get_node_id(self, node, target_table: str) -> str:
        if isinstance(node.source, exp.Table):
            real_table = (
                getattr(node.source, "name", None)
                or getattr(node.expression, "name", None)
                or node.name.split(".")[0]
            )
            col_name = node.name.split(".")[-1]
            return f"table:{real_table}.{col_name}"

        if node.reference_node_name:
            col_name = node.name.split(".")[-1]
            return f"cte:{target_table}.{node.reference_node_name}.{col_name}"

        col_name = node.name.split(".")[-1]
        return f"table:{target_table}.{col_name}"

    def _add_lineage_node(self, node, target_table: str):
        parent_id = self._get_node_id(node, target_table)

        for child in node.downstream:
            child_id = self._get_node_id(child, target_table)
            self.graph.add_edge(child_id, parent_id)
            self._add_lineage_node(child, target_table)

    def add_query(self, sql: str, target_table: str):
        from sqlglot.optimizer import qualify

        parsed = sqlglot.parse_one(sql)
        cte_names = {cte.alias for cte in parsed.find_all(exp.CTE)}
        query_tables = {
            t.name for t in parsed.find_all(exp.Table) if t.name not in cte_names
        }

        alias_map = {}
        for tbl in parsed.find_all(exp.Table):
            if tbl.name not in cte_names:
                alias_map[tbl.alias_or_name] = tbl.name
                alias_map[tbl.name] = tbl.name

        has_schema = any(t in self.schema for t in query_tables)
        active_schema = self.schema if (self.schema and has_schema) else None

        if active_schema:
            try:
                parsed = qualify.qualify(parsed, schema=active_schema, quote_identifiers=False)
            except Exception:
                pass

        output_columns = [
            col.alias_or_name for col in parsed.selects if col.alias_or_name != "*"
        ]

        query_sql = parsed.sql()
        for col_name in output_columns:
            root = lineage(col_name, query_sql, schema=active_schema)
            self._add_lineage_node(root, target_table)

        if target_table not in self.schema:
            self.schema[target_table] = {}
        for col in output_columns:
            self.schema[target_table][col] = "unknown"

        target_relation = f"relation:{target_table}"

        for src_table in query_tables:
            self.influence_graph.add_edge(f"relation:{src_table}", target_relation, influence="pipeline")

        def extract_influence_cols(clause_expr, influence_type):
            if not clause_expr:
                return
            for col in clause_expr.find_all(exp.Column):
                table_ref = col.table
                real_table = alias_map.get(table_ref) if table_ref else None
                if not real_table:
                    for st in query_tables:
                        if st in self.schema and col.name in self.schema[st]:
                            real_table = st
                            break
                if not real_table and query_tables:
                    real_table = next(iter(query_tables))

                if real_table:
                    col_id = f"table:{real_table}.{col.name}"
                    self.influence_graph.add_edge(col_id, target_relation, influence=influence_type)

        extract_influence_cols(parsed.args.get("where"), "filter")

        for j in parsed.args.get("joins", []):
            extract_influence_cols(j.args.get("on"), "join")

        extract_influence_cols(parsed.args.get("group"), "group_by")
        extract_influence_cols(parsed.args.get("having"), "having")

    def get_blast_radius(self, target: str, include_ctes: bool = False) -> set[str]:
        if not target.startswith(("table:", "cte:")):
            target = f"table:{target}"

        if target not in self.graph:
            return set()

        descendants = nx.descendants(self.graph, target)

        if not include_ctes:
            return {node for node in descendants if node.startswith("table:")}

        return descendants

    def get_derivation_blast_radius(self, target: str, include_ctes: bool = False) -> set[str]:
        return self.get_blast_radius(target, include_ctes)

    def get_relational_blast_radius(self, target: str) -> set[str]:
        if not target.startswith(("table:", "relation:")):
            target = f"table:{target}"

        if target not in self.influence_graph:
            return set()

        return nx.descendants(self.influence_graph, target)