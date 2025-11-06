import reflex as rx
from .. import db


class InventoryState(rx.State):
    """Estado para el módulo Inventario & Logística."""

    # --- Tabla principal de inventario (vista vw_inventario_producto_bodega) ---
    inventory_rows: list[dict] = []
    page: int = 0
    page_size: int = 20

    # --- Filtros ---
    filter_product_id: str = ""
    filter_warehouse_id: str = ""

    # --- Mensaje general (debug / info) ---
    message: str = ""

    # --- Stock puntual (SP sp_calcular_stock_producto_bodega) ---
    stock_product_id: str = ""
    stock_warehouse_id: str = ""
    stock_result_text: str = ""

    # --- Registro de movimiento (SP sp_registrar_movimiento_inventario) ---
    mov_product_id: str = ""
    mov_warehouse_id: str = ""
    mov_empleado_id: str = ""
    mov_cantidad: str = ""
    mov_tipo: str = "IN"  # IN / OUT
    mov_message: str = ""

    # ==========================================================
    # Inventario (vista vw_inventario_producto_bodega)
    # ==========================================================

    def load_inventory(self):
        """Carga el inventario desde la vista con filtros y paginación."""
        product_id = None
        warehouse_id = None

        if self.filter_product_id.strip() != "":
            try:
                product_id = int(self.filter_product_id)
            except ValueError:
                product_id = None

        if self.filter_warehouse_id.strip() != "":
            try:
                warehouse_id = int(self.filter_warehouse_id)
            except ValueError:
                warehouse_id = None

        try:
            rows = db.get_inventory_view(
                product_id=product_id,
                warehouse_id=warehouse_id,
                page=self.page,
                page_size=self.page_size,
            )
            self.inventory_rows = rows
            self.message = f"Inventario cargado: {len(rows)} filas (página {self.page + 1})."
        except Exception as e:
            self.inventory_rows = []
            self.message = f"Error al cargar inventario: {e}"

    def next_page(self):
        """Página siguiente."""
        self.page += 1
        self.load_inventory()

    def prev_page(self):
        """Página anterior."""
        if self.page > 0:
            self.page -= 1
        self.load_inventory()

    def clear_inventory_filters(self):
        """Limpia filtros y reinicia paginación."""
        self.filter_product_id = ""
        self.filter_warehouse_id = ""
        self.page = 0
        self.load_inventory()

    # ==========================================================
    # Stock puntual (SP sp_calcular_stock_producto_bodega)
    # ==========================================================

    def check_stock(self):
        """Consulta el stock actual de un producto en una bodega específica."""
        self.stock_result_text = ""

        if not self.stock_product_id or not self.stock_warehouse_id:
            self.stock_result_text = "Ingresa ID de producto y bodega para consultar stock."
            return

        try:
            product_id = int(self.stock_product_id)
            warehouse_id = int(self.stock_warehouse_id)
        except ValueError:
            self.stock_result_text = "Producto y bodega deben ser IDs numéricos."
            return

        # get_stock_producto_bodega devuelve una lista de filas (0 o 1 normalmente)
        rows = db.get_stock_producto_bodega(product_id, warehouse_id)
        if not rows:
            self.stock_result_text = "No se encontró stock para ese producto y bodega."
            return

        row = dict(rows[0])
        # Normalizamos stock_actual a no negativo
        try:
            stock_val = int(row.get("stock_actual", 0))
        except (TypeError, ValueError):
            stock_val = 0
        stock_val = max(stock_val, 0)

        nombre_prod = row.get("Nombre del producto", "Producto")
        nombre_bod = row.get("warehouse_nombre", "Bodega")

        self.stock_result_text = (
            f'Producto #{row.get("product_id", "")}: {nombre_prod} | '
            f'Bodega #{row.get("warehouse_id", "")}: {nombre_bod} | '
            f"Stock actual: {stock_val}"
        )

    # ==========================================================
    # Movimiento de inventario (SP sp_registrar_movimiento_inventario)
    # ==========================================================

    def registrar_movimiento(self):
        """Registra un movimiento IN/OUT de inventario."""
        self.mov_message = ""

        if not (
            self.mov_product_id
            and self.mov_warehouse_id
            and self.mov_empleado_id
            and self.mov_cantidad
        ):
            self.mov_message = "Producto, bodega, empleado y cantidad son obligatorios."
            return

        try:
            product_id = int(self.mov_product_id)
            warehouse_id = int(self.mov_warehouse_id)
            empleado_id = int(self.mov_empleado_id)
            cantidad = int(self.mov_cantidad)
        except ValueError:
            self.mov_message = "IDs y cantidad deben ser numéricos."
            return

        if self.mov_tipo not in ("IN", "OUT"):
            self.mov_message = "El tipo de movimiento debe ser IN o OUT."
            return

        ok = db.register_inventory_movement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            empleado_id=empleado_id,
            cantidad=cantidad,
            tipo_movimiento=self.mov_tipo,
        )

        if ok:
            self.mov_message = "Movimiento registrado correctamente."
            self.mov_cantidad = ""
            # refrescamos inventario por si cambió stock
            self.load_inventory()
        else:
            self.mov_message = "Error al registrar movimiento de inventario."


# ==========================================================
# Componentes de UI
# ==========================================================

def inventory_filters_bar() -> rx.Component:
    """Barra de filtros para el inventario."""
    return rx.hstack(
        rx.input(
            placeholder="Filtrar por ID de producto...",
            value=InventoryState.filter_product_id,
            on_change=InventoryState.set_filter_product_id,
            width="14rem",
        ),
        rx.input(
            placeholder="Filtrar por ID de bodega...",
            value=InventoryState.filter_warehouse_id,
            on_change=InventoryState.set_filter_warehouse_id,
            width="14rem",
        ),
        rx.button(
            "Filtrar",
            color_scheme="orange",
            on_click=InventoryState.load_inventory,
        ),
        rx.button(
            "Limpiar",
            variant="soft",
            on_click=InventoryState.clear_inventory_filters,
        ),
        spacing="3",
        wrap="wrap",
        align_items="flex-end",
    )


def inventory_table() -> rx.Component:
    """Tabla con el resumen de inventario por producto y bodega."""
    headers = [
        "ID Producto",
        "Producto",
        "ID Bodega",
        "Bodega",
        "Stock actual",
    ]

    def render_row(r: dict):
        return rx.table.row(
            rx.table.cell(r["product_id"]),
            rx.table.cell(r["NombreProducto"]),
            rx.table.cell(r["warehouse_id"]),
            rx.table.cell(r["warehouse_nombre"]),
            rx.table.cell(r["stock_actual"]),
        )

    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[rx.table.column_header_cell(h) for h in headers],
                )
            ),
            rx.table.body(
                rx.foreach(InventoryState.inventory_rows, render_row),
            ),
        ),
        width="100%",
        overflow_x="auto",
        bg="white",
        padding="1rem",
        border_radius="1rem",
        box_shadow="0 8px 16px rgba(15,23,42,0.08)",
    )


def inventory_pagination() -> rx.Component:
    """Botones de paginación para el inventario."""
    return rx.hstack(
        rx.button("← Anterior", on_click=InventoryState.prev_page),
        rx.button("Siguiente →", on_click=InventoryState.next_page),
        spacing="4",
        margin_top="0.5rem",
    )


def stock_panel() -> rx.Component:
    """Panel para consultar stock puntual por producto y bodega."""
    return rx.box(
        rx.vstack(
            rx.heading("Consulta de stock puntual", size="4", color="orange.9"),
            rx.text(
                "Consulta el stock actual de un producto en una bodega específica.",
                font_size="0.85rem",
                color="gray.9",
            ),
            rx.hstack(
                rx.input(
                    placeholder="ID producto",
                    value=InventoryState.stock_product_id,
                    on_change=InventoryState.set_stock_product_id,
                    width="10rem",
                ),
                rx.input(
                    placeholder="ID bodega",
                    value=InventoryState.stock_warehouse_id,
                    on_change=InventoryState.set_stock_warehouse_id,
                    width="10rem",
                ),
                rx.button(
                    "Consultar",
                    color_scheme="orange",
                    on_click=InventoryState.check_stock,
                ),
                spacing="3",
                wrap="wrap",
            ),
            rx.cond(
                InventoryState.stock_result_text != "",
                rx.text(
                    InventoryState.stock_result_text,
                    color="orange.10",
                    font_size="0.9rem",
                ),
            ),
            spacing="3",
        ),
        bg="white",
        padding="1.25rem",
        border_radius="1.25rem",
        box_shadow="0 8px 16px rgba(15,23,42,0.08)",
        width="100%",
    )


def movement_panel() -> rx.Component:
    """Panel para registrar movimientos de inventario."""
    return rx.box(
        rx.vstack(
            rx.heading("Movimiento de inventario", size="4", color="orange.9"),
            rx.text(
                "Registra entradas (IN) o salidas (OUT) de inventario.",
                font_size="0.85rem",
                color="gray.9",
            ),
            rx.hstack(
                rx.input(
                    placeholder="ID producto",
                    value=InventoryState.mov_product_id,
                    on_change=InventoryState.set_mov_product_id,
                    width="10rem",
                ),
                rx.input(
                    placeholder="ID bodega",
                    value=InventoryState.mov_warehouse_id,
                    on_change=InventoryState.set_mov_warehouse_id,
                    width="10rem",
                ),
                rx.input(
                    placeholder="ID empleado",
                    value=InventoryState.mov_empleado_id,
                    on_change=InventoryState.set_mov_empleado_id,
                    width="10rem",
                ),
                spacing="3",
                wrap="wrap",
            ),
            rx.hstack(
                rx.input(
                    placeholder="Cantidad",
                    value=InventoryState.mov_cantidad,
                    on_change=InventoryState.set_mov_cantidad,
                    width="8rem",
                ),
                rx.select(
                    items=["IN", "OUT"],
                    value=InventoryState.mov_tipo,
                    on_change=InventoryState.set_mov_tipo,
                    width="8rem",
                ),
                spacing="3",
                wrap="wrap",
            ),
            rx.button(
                "Registrar movimiento",
                color_scheme="orange",
                on_click=InventoryState.registrar_movimiento,
            ),
            rx.cond(
                InventoryState.mov_message != "",
                rx.text(
                    InventoryState.mov_message,
                    color="orange.10",
                    font_size="0.9rem",
                ),
            ),
            spacing="3",
        ),
        bg="#fff8f0",
        padding="1.25rem",
        border_radius="1.25rem",
        border="1px solid #fed7aa",
        width="100%",
    )


# ==========================================================
# Página principal
# ==========================================================

def inventory_page() -> rx.Component:
    """Vista principal del módulo Inventario & Logística."""
    return rx.vstack(
        rx.heading("Inventario & Logística", size="6", color="orange.9"),
        rx.text(
            "Consulta el stock por producto y bodega, y registra movimientos de inventario.",
        ),
        rx.cond(
            InventoryState.message != "",
            rx.text(
                InventoryState.message,
                color="gray.9",
                font_size="0.85rem",
            ),
        ),
        rx.divider(margin_y="0.5rem"),
        inventory_filters_bar(),
        inventory_table(),
        inventory_pagination(),
        rx.divider(margin_y="1rem"),
        rx.hstack(
            stock_panel(),
            movement_panel(),
            spacing="4",
            align_items="flex-start",
            wrap="wrap",
            width="100%",
        ),
        spacing="4",
        width="100%",
        on_mount=InventoryState.load_inventory,
    )
