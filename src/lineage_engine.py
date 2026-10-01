import networkx as nx
import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage
from typing import Dict, Any, List, Set, Optional


class LineageEngine:
    """
    Column-level SQL lineage engine providing dual-graph separation:
    - Derivation Graph (G_val): Value-level data transformations.
    - Relational-Influence Graph (G_rel): Predicate, join, and grouping control flow.
    """

    def __init__(self, schema: dict | None = None, sniffer_mode: str = "extended"):
        """
        Initializes the lineage engine.
        sniffer_mode options:
          - 'none': Disables construct detection (baseline binary behavior).
          - 'targeted': Detects only the initial failure modes (exp.Union, RECURSIVE_CTE).
          - 'extended': Detects unseen complex constructs (LATERAL subqueries, EXISTS predicates).
        """
        self.schema = dict(schema) if schema else {}
        self.graph = nx.DiGraph()
        self.influence_graph = nx.DiGraph()
        self.unresolved_constructs: Dict[str, List[str]] = {}
        self.sniffer_mode = sniffer_mode

    def _get_node_id(self, node, target_table: str) -> str:
        """Resolves canonical node identities, unmasking query table aliases."""
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
        """Recursively traverses the sqlglot lineage tree and inserts directed edges."""
        parent_id = self._get_node_id(node, target_table)

        for child in node.downstream:
            child_id = self._get_node_id(child, target_table)
            self.graph.add_edge(child_id, parent_id)
            self._add_lineage_node(child, target_table)

    def _detect_unresolved_constructs(self, parsed: exp.Expression) -> List[str]:
        """Detects SQL constructs where AST lineage parsers are known to silently fail or drop column edges."""
        if self.sniffer_mode == "none":
            return []

        issues = []
        if isinstance(parsed, exp.Union):
            issues.append("SET_OPERATION_UNION")

        with_node = parsed.args.get("with_")
        if with_node and (with_node.args.get("recursive") or "recursive" in with_node.sql().lower()):
            issues.append("RECURSIVE_CTE")

        if self.sniffer_mode == "targeted":
            return issues

        if parsed.find(exp.Lateral) or "lateral" in parsed.sql().lower():
            issues.append("LATERAL_SUBQUERY")

        if parsed.find(exp.Exists):
            issues.append("EXISTS_PREDICATE")

        return issues


    def add_query(self, sql: str, target_table: str):
        """Parses a query, records AST risks, and constructs lineage graphs."""
        from sqlglot.optimizer import qualify

        parsed = sqlglot.parse_one(sql)
        
        detected_risks = self._detect_unresolved_constructs(parsed)
        if detected_risks:
            self.unresolved_constructs[target_table] = detected_risks

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
        """Computes derivation blast radius via directed graph traversal."""
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
        """Computes downstream relations influenced by filtering, joins, or aggregations."""
        if not target.startswith(("table:", "relation:")):
            target = f"table:{target}"

        if target not in self.influence_graph:
            return set()

        return nx.descendants(self.influence_graph, target)