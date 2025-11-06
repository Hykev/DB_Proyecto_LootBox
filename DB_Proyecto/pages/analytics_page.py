import reflex as rx
from .. import db
import json


# ==========================================================
# Vistas disponibles (deben existir en MySQL)
# ==========================================================

ANALYTICS_VIEWS = [
    "vw_ventas_por_categoria",
    "vw_ticket_promedio_mensual",
    "vw_sla_envios",
    "vw_tasa_devoluciones_mensual",
    "vw_clientes_ltv_alto",
    "vw_inventario_producto_bodega",
    "vw_clientes_por_pais",
    "vw_abc_productos",
]


# ==========================================================
# Consultas avanzadas predefinidas
# ==========================================================

ANALYTICS_QUERIES = {
    "ticket_promedio_por_mes": {
        "label": "Ticket promedio por mes (JOIN ordenes + items)",
        "sql": """
            SELECT
                YEAR(o.`Fecha de la orden`) AS anio,
                MONTH(o.`Fecha de la orden`) AS mes,
                COUNT(DISTINCT o.ID) AS total_ordenes,
                SUM(o.Total) AS total_ingresos,
                AVG(o.Total) AS ticket_promedio
            FROM Ordenes o
            GROUP BY YEAR(o.`Fecha de la orden`), MONTH(o.`Fecha de la orden`)
            ORDER BY anio, mes;
        """,
    },
    "clientes_multipais": {
        "label": "Clientes multipaís (ordenan desde más de un país)",
        "sql": """
            SELECT
                c.ID AS customer_id,
                c.Nombre,
                c.Apellido,
                COUNT(DISTINCT co.ID) AS paises_distintos
            FROM Customers c
            JOIN Cities ci ON ci.ID = c.Cities_ID
            JOIN Countries co ON co.ID = ci.Countries_ID
            JOIN Ordenes o ON o.Customers_ID = c.ID
            GROUP BY c.ID, c.Nombre, c.Apellido
            HAVING COUNT(DISTINCT co.ID) > 1
            ORDER BY paises_distintos DESC;
        """,
    },
    "proveedor_dominante_por_categoria": {
        "label": "Proveedor dominante por categoría (>60% de ventas)",
        "sql": """
            SELECT
                cat.ID AS categoria_id,
                cat.Nombre AS categoria_nombre,
                s.ID AS supplier_id,
                s.`Nombre de proveedor` AS supplier_nombre,
                SUM(oi.Cantidad * oi.`Precio por unidad`) AS ventas_proveedor_categoria,
                SUM(SUM(oi.Cantidad * oi.`Precio por unidad`)) OVER (PARTITION BY cat.ID) AS ventas_categoria_total,
                ROUND(
                    100 * SUM(oi.Cantidad * oi.`Precio por unidad`)
                    / SUM(SUM(oi.Cantidad * oi.`Precio por unidad`)) OVER (PARTITION BY cat.ID),
                    2
                ) AS porcentaje_participacion
            FROM Order_items oi
            JOIN Products p ON p.ID = oi.Products_ID
            JOIN Categories cat ON cat.ID = p.Categories_ID
            JOIN Suppliers s ON s.ID = p.Suppliers_ID
            GROUP BY cat.ID, cat.Nombre, s.ID, s.`Nombre de proveedor`
            HAVING porcentaje_participacion > 60
            ORDER BY cat.ID, porcentaje_participacion DESC;
        """,
    },
    "clientes_churn_180": {
        "label": "Clientes churn (>180 días sin comprar)",
        "sql": """
            SELECT
                c.ID AS customer_id,
                c.Nombre,
                c.Apellido,
                MAX(o.`Fecha de la orden`) AS ultima_compra,
                DATEDIFF(CURDATE(), MAX(o.`Fecha de la orden`)) AS dias_desde_ultima_compra
            FROM Customers c
            LEFT JOIN Ordenes o ON o.Customers_ID = c.ID
            GROUP BY c.ID, c.Nombre, c.Apellido
            HAVING dias_desde_ultima_compra >= 180
            ORDER BY dias_desde_ultima_compra DESC;
        """,
    },
    "abc_productos": {
        "label": "ABC de productos (A=80%, B=15%, C=5%)",
        "sql": """
            SELECT
                p.ID AS product_id,
                p.`Nombre del producto`,
                SUM(oi.Cantidad * oi.`Precio por unidad`) AS ventas_producto,
                SUM(SUM(oi.Cantidad * oi.`Precio por unidad`)) OVER () AS ventas_totales,
                ROUND(
                    100 * SUM(oi.Cantidad * oi.`Precio por unidad`)
                        / SUM(SUM(oi.Cantidad * oi.`Precio por unidad`)) OVER (),
                    2
                ) AS porcentaje_acumulado,
                CASE
                    WHEN
                        ROUND(
                            100 * SUM(oi.Cantidad * oi.`Precio por unidad`)
                                / SUM(SUM(oi.Cantidad * oi.`Precio por unidad`)) OVER (),
                            2
                        ) <= 80
                    THEN 'A'
                    WHEN
                        ROUND(
                            100 * SUM(oi.Cantidad * oi.`Precio por unidad`)
                                / SUM(SUM(oi.Cantidad * oi.`Precio por unidad`)) OVER (),
                            2
                        ) <= 95
                    THEN 'B'
                    ELSE 'C'
                END AS clasificacion_abc
            FROM Order_items oi
            JOIN Products p ON p.ID = oi.Products_ID
            GROUP BY p.ID, p.`Nombre del producto`
            ORDER BY ventas_producto DESC;
        """,
    },
}


# ==========================================================
# STATE: Analytics
# ==========================================================

class AnalyticsState(rx.State):
    """Estado para manejar vistas y consultas avanzadas."""

    # --- Vistas ---
    selected_view: str = ANALYTICS_VIEWS[0]
    view_rows: list[dict] = []
    view_columns: list[str] = []

    # --- Consultas ---
    selected_query_key: str = "ticket_promedio_por_mes"
    selected_query_label: str = ANALYTICS_QUERIES["ticket_promedio_por_mes"]["label"]
    query_rows_json: str = ""
    explain_rows: list[dict] = []
    query_message: str = ""

    # ================== VISTAS ==================

    def load_view(self):
        """Carga la vista seleccionada desde la BD y define columnas."""
        self.view_rows = db.get_view_data(self.selected_view)
        if self.view_rows:
            # Tomamos las llaves del primer registro como nombres de columnas
            self.view_columns = list(self.view_rows[0].keys())
        else:
            self.view_columns = []

    def change_view(self, value: str):
        """Se dispara al cambiar el select de vistas."""
        self.selected_view = value
        self.load_view()

    # ================== CONSULTAS ==================

    def change_query(self, key: str):
        """Cambia la consulta seleccionada y actualiza su label."""
        self.selected_query_key = key
        cfg = ANALYTICS_QUERIES.get(key)
        if cfg is not None:
            self.selected_query_label = cfg.get("label", key)
        else:
            self.selected_query_label = key

    def run_query(self):
        """Ejecuta la consulta avanzada seleccionada (sin EXPLAIN)."""
        self.query_message = ""
        self.query_rows_json = ""
        self.explain_rows = []

        cfg = ANALYTICS_QUERIES.get(self.selected_query_key)
        if cfg is None:
            self.query_message = "Consulta no encontrada."
            return

        sql = cfg["sql"]
        rows = db.run_sql_with_explain(sql, explain=False)

        if not rows:
            self.query_message = "La consulta se ejecutó, pero no devolvió filas."

        try:
            self.query_rows_json = json.dumps(
                rows, default=str, indent=2, ensure_ascii=False
            )
        except Exception:
            self.query_rows_json = "[]"

    def run_explain(self):
        """Ejecuta EXPLAIN para la consulta avanzada seleccionada."""
        self.query_message = ""
        self.explain_rows = []

        cfg = ANALYTICS_QUERIES.get(self.selected_query_key)
        if cfg is None:
            self.query_message = "Consulta no encontrada."
            return

        sql = cfg["sql"]
        rows = db.run_sql_with_explain(sql, explain=True)
        self.explain_rows = rows

        if not rows:
            self.query_message = "EXPLAIN no devolvió filas (revisa la consulta)."


# ==========================================================
# UI: VISTAS
# ==========================================================

def views_section() -> rx.Component:
    """Selector de vista + tabla dinámica."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Vistas analíticas", size="5", color="orange.9"),
                rx.spacer(),
                rx.select(
                    items=ANALYTICS_VIEWS,
                    value=AnalyticsState.selected_view,
                    on_change=AnalyticsState.change_view,
                    width="22rem",
                ),
                spacing="3",
                align_items="center",
                wrap="wrap",
            ),
            rx.text(
                "Selecciona una vista (nombre de la VIEW en MySQL) para analizar KPIs de LootBox.",
                font_size="0.9rem",
                color="gray.9",
            ),
            rx.cond(
                AnalyticsState.view_rows != [],
                view_table(),
            ),
            spacing="2",
        ),
        width="100%",
    )


def view_table() -> rx.Component:
    """Tabla dinámica para mostrar cualquier vista."""
    def render_header(col: str):
        return rx.table.column_header_cell(col)

    def render_row(row: dict):
        def render_cell(col: str):
            return rx.table.cell(row[col])
        return rx.table.row(
            rx.foreach(AnalyticsState.view_columns, render_cell)
        )

    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.foreach(AnalyticsState.view_columns, render_header),
                )
            ),
            rx.table.body(
                rx.foreach(AnalyticsState.view_rows, render_row),
            ),
        ),
        width="100%",
        overflow_x="auto",
        bg="white",
        padding="1rem",
        border_radius="1rem",
        box_shadow="0 8px 16px rgba(15, 23, 42, 0.08)",
    )


# ==========================================================
# UI: CONSULTAS AVANZADAS
# ==========================================================

def queries_section() -> rx.Component:
    """Sección para ejecutar consultas avanzadas + EXPLAIN."""
    return rx.box(
        rx.vstack(
            rx.heading("Consultas avanzadas", size="5", color="orange.9"),
            rx.text(
                "Ejecuta consultas complejas predefinidas y revisa su plan de ejecución (EXPLAIN).",
                font_size="0.9rem",
                color="gray.9",
            ),
            rx.hstack(
                rx.select(
                    items=list(ANALYTICS_QUERIES.keys()),
                    value=AnalyticsState.selected_query_key,
                    on_change=AnalyticsState.change_query,
                    width="24rem",
                ),
                rx.button(
                    "Ejecutar consulta",
                    color_scheme="orange",
                    on_click=AnalyticsState.run_query,
                ),
                rx.button(
                    "Ver EXPLAIN",
                    variant="soft",
                    on_click=AnalyticsState.run_explain,
                ),
                spacing="3",
                wrap="wrap",
            ),
            rx.text(
                AnalyticsState.selected_query_label,
                font_size="0.8rem",
                color="gray.8",
            ),
            rx.cond(
                AnalyticsState.query_message != "",
                rx.text(
                    AnalyticsState.query_message,
                    color="orange.10",
                    font_size="0.85rem",
                ),
            ),
            rx.cond(
                AnalyticsState.query_rows_json != "",
                rx.box(
                    rx.heading("Resultados de la consulta", size="4", color="orange.9"),
                    rx.box(
                        rx.code_block(
                            AnalyticsState.query_rows_json,
                            language="json",
                            width="100%",
                        ),
                        max_height="300px",
                        overflow_y="auto",
                        margin_top="0.5rem",
                    ),
                    margin_top="0.5rem",
                ),
            ),
            explain_table(),
            spacing="3",
        ),
        width="100%",
        bg="#fff8f0",
        padding="1.5rem",
        border_radius="1.25rem",
        border="1px solid #fed7aa",
    )


def explain_table() -> rx.Component:
    """Tabla para mostrar el resultado de EXPLAIN."""
    headers = [
        "id",
        "select_type",
        "table",
        "type",
        "possible_keys",
        "key",
        "key_len",
        "ref",
        "rows",
        "filtered",
        "Extra",
    ]

    def render_row(r: dict):
        return rx.table.row(
            rx.table.cell(str(r.get("id", ""))),
            rx.table.cell(str(r.get("select_type", ""))),
            rx.table.cell(str(r.get("table", ""))),
            rx.table.cell(str(r.get("type", ""))),
            rx.table.cell(str(r.get("possible_keys", ""))),
            rx.table.cell(str(r.get("key", ""))),
            rx.table.cell(str(r.get("key_len", ""))),
            rx.table.cell(str(r.get("ref", ""))),
            rx.table.cell(str(r.get("rows", ""))),
            rx.table.cell(str(r.get("filtered", ""))),
            rx.table.cell(str(r.get("Extra", ""))),
        )

    return rx.cond(
        AnalyticsState.explain_rows != [],
        rx.box(
            rx.heading("Plan de ejecución (EXPLAIN)", size="4", color="orange.9"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        *[rx.table.column_header_cell(h) for h in headers],
                    )
                ),
                rx.table.body(
                    rx.foreach(AnalyticsState.explain_rows, render_row),
                ),
            ),
            width="100%",
            overflow_x="auto",
            bg="white",
            padding="1rem",
            border_radius="1rem",
            box_shadow="0 8px 16px rgba(15,23,42,0.08)",
            margin_top="0.5rem",
        ),
    )


# ==========================================================
# PÁGINA PRINCIPAL
# ==========================================================

def analytics_page() -> rx.Component:
    """Vista principal del módulo Analítica."""
    return rx.vstack(
        rx.heading("Analítica", size="6", color="orange.9"),
        rx.text(
            "Explora vistas analíticas y ejecuta consultas avanzadas sobre LootBox.",
        ),
        rx.divider(margin_y="0.5rem"),
        views_section(),
        rx.divider(margin_y="1.5rem"),
        queries_section(),
        spacing="4",
        width="100%",
        on_mount=AnalyticsState.load_view,
    )
