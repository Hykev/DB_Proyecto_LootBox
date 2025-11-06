import reflex as rx
from .. import db

# ==========================================================
# Constantes de vistas analíticas (basadas en las vistas SQL)
# ==========================================================

VIEW_OPTIONS = [
    {
        "value": "vw_ventas_por_categoria",
        "label": "Ventas por categoría",
        "description": "Suma de ventas (Q) agrupadas por categoría de producto.",
    },
    {
        "value": "vw_ticket_promedio_mensual",
        "label": "Ticket promedio mensual",
        "description": "Promedio de total de orden por mes.",
    },
    {
        "value": "vw_sla_envios",
        "label": "SLA de envíos",
        "description": "Días entre fecha de envío y fecha de entrega por envío.",
    },
    {
        "value": "vw_tasa_devoluciones_mensual",
        "label": "Tasa de devoluciones mensual",
        "description": "Relación entre órdenes y devoluciones por mes.",
    },
    {
        "value": "vw_clientes_ltv_alto",
        "label": "Clientes con LTV alto",
        "description": "Clientes con Lifetime Value mayor al umbral definido.",
    },
    {
        "value": "vw_inventario_producto_bodega",
        "label": "Inventario por producto y bodega",
        "description": "Stock actual por producto y bodega.",
    },
    {
        "value": "vw_clientes_por_pais",
        "label": "Clientes por país",
        "description": "Número de clientes agrupados por país.",
    },
    {
        "value": "vw_abc_productos",
        "label": "ABC de productos",
        "description": "Clasificación ABC según participación en ventas.",
    },
]

# ==========================================================
# Consultas avanzadas (mínimo 3, luego pueden agregar más)
# ==========================================================

ADVANCED_QUERIES = {
    "clientes_multipais": {
        "label": "Clientes multipaís",
        "description": "Clientes con compras registradas en más de un país.",
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
            HAVING COUNT(DISTINCT co.ID) > 1;
        """,
    },
    "clientes_churn_180": {
        "label": "Clientes churn (>180 días sin comprar)",
        "description": "Clientes cuya última compra fue hace más de 180 días.",
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
            HAVING MAX(o.`Fecha de la orden`) IS NOT NULL
              AND DATEDIFF(CURDATE(), MAX(o.`Fecha de la orden`)) > 180;
        """,
    },
    "abc_productos_query": {
        "label": "ABC de productos (detalle)",
        "description": "Consulta directa sobre la vista vw_abc_productos.",
        "sql": """
            SELECT
              product_id,
              `Nombre del producto`,
              total_ventas,
              acumulado,
              total_general,
              categoria_abc
            FROM vw_abc_productos;
        """,
    },
    # Aquí pueden agregar más consultas avanzadas para el proyecto
}


# ==========================================================
# Estado de Analítica
# ==========================================================

class AnalyticsState(rx.State):
    """Maneja vistas analíticas y consultas avanzadas."""

    # --- Vistas analíticas ---
    selected_view: str = "vw_ventas_por_categoria"
    view_all_rows: list[dict] = []
    view_rows: list[dict] = []
    view_columns: list[str] = []
    view_page: int = 0
    view_page_size: int = 15
    view_message: str = ""

    # --- Consultas avanzadas ---
    selected_query: str = "clientes_multipais"
    query_all_rows: list[dict] = []
    query_rows: list[dict] = []
    query_columns: list[str] = []
    query_page: int = 0
    query_page_size: int = 15
    query_message: str = ""

    # --- Plan de ejecución (EXPLAIN) ---
    plan_rows: list[dict] = []
    plan_columns: list[str] = []
    show_plan: bool = True
    # ======================================================
    # Helpers internos de paginación
    # ======================================================

    def _update_view_page(self):
        start = self.view_page * self.view_page_size
        end = start + self.view_page_size
        self.view_rows = self.view_all_rows[start:end]

    def _update_query_page(self):
        start = self.query_page * self.query_page_size
        end = start + self.query_page_size
        self.query_rows = self.query_all_rows[start:end]

    # ======================================================
    # Vistas analíticas (vistas SQL)
    # ======================================================

    def set_selected_view(self, value: str):
        """Se llama al hacer clic en un botón de vista."""
        self.selected_view = value
        self.view_page = 0
        self.load_view_data()

    def load_view_data(self):
        """Carga datos de la vista seleccionada usando db.get_view_data."""
        self.view_message = ""
        rows = db.get_view_data(self.selected_view)
        self.view_all_rows = rows
        self.view_page = 0

        if rows:
            self.view_columns = list(rows[0].keys())
        else:
            self.view_columns = []

        self._update_view_page()

        if not rows:
            self.view_message = "Esta vista no tiene datos para mostrar en este momento."

    def next_view_page(self):
        """Página siguiente de la vista."""
        total = len(self.view_all_rows)
        if (self.view_page + 1) * self.view_page_size < total:
            self.view_page += 1
            self._update_view_page()

    def prev_view_page(self):
        """Página anterior de la vista."""
        if self.view_page > 0:
            self.view_page -= 1
            self._update_view_page()

    # ======================================================
    # Consultas avanzadas + EXPLAIN
    # ======================================================

    def toggle_plan(self):
        """Muestra u oculta la tabla de EXPLAIN."""
        self.show_plan = not self.show_plan


    def set_selected_query(self, value: str):
        """Se llama al cambiar de consulta avanzada."""
        self.selected_query = value

    def run_selected_query(self):
        """Ejecuta la consulta avanzada seleccionada y su EXPLAIN."""
        self.query_message = ""
        self.query_all_rows = []
        self.query_rows = []
        self.plan_rows = []
        self.plan_columns = []

        info = ADVANCED_QUERIES.get(self.selected_query)
        if not info:
            self.query_message = "Consulta no encontrada."
            return

        sql = info["sql"]

        # Ejecutar consulta principal
        rows = db.run_sql_with_explain(sql, explain=False)
        self.query_all_rows = rows
        self.query_page = 0
        if rows:
            self.query_columns = list(rows[0].keys())
        else:
            self.query_columns = []
        self._update_query_page()

        if not rows:
            self.query_message = "La consulta no devolvió resultados."

        # Ejecutar EXPLAIN
        plan = db.run_sql_with_explain(sql, explain=True)
        self.plan_rows = plan
        if plan:
            self.plan_columns = list(plan[0].keys())
        else:
            self.plan_columns = []

    def next_query_page(self):
        """Página siguiente de resultados de consulta avanzada."""
        total = len(self.query_all_rows)
        if (self.query_page + 1) * self.query_page_size < total:
            self.query_page += 1
            self._update_query_page()

    def prev_query_page(self):
        """Página anterior de resultados de consulta avanzada."""
        if self.query_page > 0:
            self.query_page -= 1
            self._update_query_page()


# ==========================================================
# UI Helpers genéricos para tablas
# ==========================================================

def _generic_table(columns_var, rows_var) -> rx.Component:
    """
    Tabla genérica que usa las columnas y filas pasadas.
    columns_var: lista de nombres de columna (state var)
    rows_var: lista de diccionarios (state var)
    """
    def render_header_cell(col: str):
        return rx.table.column_header_cell(str(col))

    def render_row(row: dict):
        # Por cada columna, mostramos la celda correspondiente.
        return rx.table.row(
            rx.foreach(
                columns_var,
                lambda col: rx.table.cell(
                    rx.cond(
                        row[col] != None,
                        row[col],
                        "",
                    )
                ),
            )
        )

    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.foreach(columns_var, render_header_cell),
            )
        ),
        rx.table.body(
            rx.foreach(rows_var, render_row),
        ),
    )
    
def _selected_view_description() -> rx.Component:
    """Descripción amigable de la vista analítica seleccionada."""
    return rx.vstack(
        # Título / label
        rx.cond(
            AnalyticsState.selected_view == "vw_ventas_por_categoria",
            rx.text("Ventas por categoría", font_weight="medium", font_size="0.95rem"),
            rx.cond(
                AnalyticsState.selected_view == "vw_ticket_promedio_mensual",
                rx.text("Ticket promedio mensual", font_weight="medium", font_size="0.95rem"),
                rx.cond(
                    AnalyticsState.selected_view == "vw_sla_envios",
                    rx.text("SLA de envíos", font_weight="medium", font_size="0.95rem"),
                    rx.cond(
                        AnalyticsState.selected_view == "vw_tasa_devoluciones_mensual",
                        rx.text("Tasa de devoluciones mensual", font_weight="medium", font_size="0.95rem"),
                        rx.cond(
                            AnalyticsState.selected_view == "vw_clientes_ltv_alto",
                            rx.text("Clientes con LTV alto", font_weight="medium", font_size="0.95rem"),
                            rx.cond(
                                AnalyticsState.selected_view == "vw_inventario_producto_bodega",
                                rx.text("Inventario por producto y bodega", font_weight="medium", font_size="0.95rem"),
                                rx.cond(
                                    AnalyticsState.selected_view == "vw_clientes_por_pais",
                                    rx.text("Clientes por país", font_weight="medium", font_size="0.95rem"),
                                    rx.text("ABC de productos", font_weight="medium", font_size="0.95rem"),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        # Descripción
        rx.cond(
            AnalyticsState.selected_view == "vw_ventas_por_categoria",
            rx.text(
                "Suma de ventas (Q) agrupadas por categoría de producto.",
                font_size="0.85rem",
                color="gray.9",
            ),
            rx.cond(
                AnalyticsState.selected_view == "vw_ticket_promedio_mensual",
                rx.text(
                    "Promedio del total de orden por mes.",
                    font_size="0.85rem",
                    color="gray.9",
                ),
                rx.cond(
                    AnalyticsState.selected_view == "vw_sla_envios",
                    rx.text(
                        "Días entre fecha de envío y fecha de entrega por envío.",
                        font_size="0.85rem",
                        color="gray.9",
                    ),
                    rx.cond(
                        AnalyticsState.selected_view == "vw_tasa_devoluciones_mensual",
                        rx.text(
                            "Relación entre órdenes y devoluciones por mes.",
                            font_size="0.85rem",
                            color="gray.9",
                        ),
                        rx.cond(
                            AnalyticsState.selected_view == "vw_clientes_ltv_alto",
                            rx.text(
                                "Clientes cuyo Lifetime Value (LTV) supera el umbral definido.",
                                font_size="0.85rem",
                                color="gray.9",
                            ),
                            rx.cond(
                                AnalyticsState.selected_view == "vw_inventario_producto_bodega",
                                rx.text(
                                    "Stock actual por producto y bodega calculado desde movimientos de inventario.",
                                    font_size="0.85rem",
                                    color="gray.9",
                                ),
                                rx.cond(
                                    AnalyticsState.selected_view == "vw_clientes_por_pais",
                                    rx.text(
                                        "Número de clientes agrupados por país.",
                                        font_size="0.85rem",
                                        color="gray.9",
                                    ),
                                    rx.text(
                                        "Clasificación ABC de productos según participación en ventas totales.",
                                        font_size="0.85rem",
                                        color="gray.9",
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        spacing="1",
        align_items="flex-start",
    )


# ==========================================================
# Sección de Vistas Analíticas
# ==========================================================
def _views_selector() -> rx.Component:
    """Botones amigables para seleccionar la vista analítica."""

    def render_button(option: dict):
        return rx.button(
            option["label"],
            size="2",
            variant="soft",
            color_scheme=rx.cond(
                AnalyticsState.selected_view == option["value"],
                "orange",
                "gray",
            ),
            on_click=AnalyticsState.set_selected_view(option["value"]),
        )

    return rx.vstack(
        rx.text("Vistas analíticas:", font_weight="medium"),
        rx.hstack(
            rx.foreach(VIEW_OPTIONS, render_button),
            spacing="2",
            wrap="wrap",
        ),
        _selected_view_description(),
        spacing="2",
        align_items="flex-start",
        width="100%",
    )


def _views_table_section() -> rx.Component:
    """Contenedor de la tabla de la vista seleccionada con paginación."""
    return rx.box(
        rx.vstack(
            rx.cond(
                AnalyticsState.view_message != "",
                rx.text(
                    AnalyticsState.view_message,
                    color="orange.10",
                    font_size="0.85rem",
                ),
            ),
            rx.cond(
                AnalyticsState.view_rows != [],
                _generic_table(
                    AnalyticsState.view_columns,
                    AnalyticsState.view_rows,
                ),
            ),
            rx.hstack(
                rx.button(
                    "← Anterior",
                    size="1",
                    variant="outline",
                    on_click=AnalyticsState.prev_view_page,
                ),
                rx.button(
                    "Siguiente →",
                    size="1",
                    variant="outline",
                    on_click=AnalyticsState.next_view_page,
                ),
                spacing="3",
            ),
            spacing="3",
        ),
        width="100%",
        overflow_x="auto",
        bg="white",
        padding="1rem",
        border_radius="1rem",
        box_shadow="0 8px 16px rgba(15,23,42,0.08)",
    )


def analytics_views_section() -> rx.Component:
    """Sección completa para las vistas analíticas."""
    return rx.vstack(
        rx.heading("Vistas analíticas", size="5", color="orange.9"),
        rx.text(
            "Explora las vistas agregadas en MySQL (ventas, SLA, devoluciones, LTV, inventario, etc.).",
            font_size="0.9rem",
            color="gray.9",
        ),
        _views_selector(),
        _views_table_section(),
        spacing="3",
        width="100%",
    )


# ==========================================================
# Sección de Consultas Avanzadas + EXPLAIN
# ==========================================================

def _selected_query_description() -> rx.Component:
    """Descripción amigable de la consulta avanzada seleccionada."""
    return rx.vstack(
        rx.cond(
            AnalyticsState.selected_query == "clientes_multipais",
            rx.text(
                "Clientes multipaís",
                font_weight="medium",
                font_size="0.95rem",
            ),
            rx.cond(
                AnalyticsState.selected_query == "clientes_churn_180",
                rx.text(
                    "Clientes churn (>180 días sin comprar)",
                    font_weight="medium",
                    font_size="0.95rem",
                ),
                rx.text(
                    "ABC de productos (detalle)",
                    font_weight="medium",
                    font_size="0.95rem",
                ),
            ),
        ),
        rx.cond(
            AnalyticsState.selected_query == "clientes_multipais",
            rx.text(
                "Clientes con compras registradas en más de un país.",
                font_size="0.85rem",
                color="gray.9",
            ),
            rx.cond(
                AnalyticsState.selected_query == "clientes_churn_180",
                rx.text(
                    "Clientes cuya última compra fue hace más de 180 días.",
                    font_size="0.85rem",
                    color="gray.9",
                ),
                rx.text(
                    "Consulta directa sobre la vista vw_abc_productos.",
                    font_size="0.85rem",
                    color="gray.9",
                ),
            ),
        ),
        spacing="1",
        align_items="flex-start",
    )

def _queries_selector() -> rx.Component:
    """Botones para elegir qué consulta avanzada ejecutar."""
    options = [
        {"value": key, "label": info["label"], "description": info["description"]}
        for key, info in ADVANCED_QUERIES.items()
    ]

    def render_button(option: dict):
        return rx.button(
            option["label"],
            size="2",
            variant="soft",
            color_scheme=rx.cond(
                AnalyticsState.selected_query == option["value"],
                "orange",
                "gray",
            ),
            on_click=AnalyticsState.set_selected_query(option["value"]),
        )

    return rx.vstack(
        rx.text("Consultas avanzadas:", font_weight="medium"),
        rx.hstack(
            rx.foreach(options, render_button),
            spacing="2",
            wrap="wrap",
        ),
        _selected_query_description(),
        spacing="2",
        align_items="flex-start",
        width="100%",
    )


def _queries_result_section() -> rx.Component:
    """Tabla con resultados de la consulta avanzada + paginación."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.button(
                    "Ejecutar consulta",
                    color_scheme="orange",
                    on_click=AnalyticsState.run_selected_query,
                ),
                spacing="3",
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
                AnalyticsState.query_rows != [],
                _generic_table(
                    AnalyticsState.query_columns,
                    AnalyticsState.query_rows,
                ),
            ),
            rx.hstack(
                rx.button(
                    "← Anterior",
                    size="1",
                    variant="outline",
                    on_click=AnalyticsState.prev_query_page,
                ),
                rx.button(
                    "Siguiente →",
                    size="1",
                    variant="outline",
                    on_click=AnalyticsState.next_query_page,
                ),
                spacing="3",
            ),
            spacing="3",
        ),
        width="100%",
        overflow_x="auto",
        bg="white",
        padding="1rem",
        border_radius="1rem",
        box_shadow="0 8px 16px rgba(15,23,42,0.08)",
    )

def _explain_section() -> rx.Component:
    """Tabla con el plan de ejecución (EXPLAIN) de la consulta avanzada."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Plan de ejecución (EXPLAIN)", size="4", color="orange.9"),
                rx.spacer(),
                rx.button(
                    rx.cond(
                        AnalyticsState.show_plan,
                        "Cerrar plan",
                        "Mostrar plan",
                    ),
                    size="1",
                    variant="outline",
                    on_click=AnalyticsState.toggle_plan,
                ),
                align_items="center",
            ),
            rx.cond(
                AnalyticsState.show_plan
                & (AnalyticsState.plan_rows != []),
                _generic_table(
                    AnalyticsState.plan_columns,
                    AnalyticsState.plan_rows,
                ),
                rx.cond(
                    AnalyticsState.show_plan,
                    rx.text(
                        "Ejecuta una consulta avanzada para ver su plan de ejecución.",
                        font_size="0.85rem",
                        color="gray.9",
                    ),
                    rx.text(
                        "El plan de ejecución está oculto. Pulsa “Mostrar plan” para verlo.",
                        font_size="0.85rem",
                        color="gray.9",
                    ),
                ),
            ),
            spacing="2",
        ),
        width="100%",
        overflow_x="auto",
        bg="#fff8f0",
        padding="1rem",
        border_radius="1rem",
        border="1px solid #fed7aa",
    )


def analytics_queries_section() -> rx.Component:
    """Sección completa de consultas avanzadas + EXPLAIN."""
    return rx.vstack(
        rx.heading("Consultas avanzadas & EXPLAIN", size="5", color="orange.9"),
        rx.text(
            "Ejecuta consultas avanzadas (churn, multipaís, ABC, etc.) y revisa su plan de ejecución.",
            font_size="0.9rem",
            color="gray.9",
        ),
        _queries_selector(),
        _queries_result_section(),
        _explain_section(),
        spacing="3",
        width="100%",
    )


# ==========================================================
# PÁGINA PRINCIPAL DE ANALÍTICA
# ==========================================================

def analytics_page() -> rx.Component:
    """Vista principal del módulo Analítica."""
    return rx.vstack(
        rx.heading("Analítica", size="6", color="orange.9"),
        rx.text(
            "Explora KPIs, vistas agregadas y consultas avanzadas sobre la base de datos LootBox.",
        ),
        rx.divider(margin_y="0.5rem"),
        analytics_views_section(),
        rx.divider(margin_y="1.5rem"),
        analytics_queries_section(),
        spacing="4",
        width="100%",
        on_mount=AnalyticsState.load_view_data,
    )
