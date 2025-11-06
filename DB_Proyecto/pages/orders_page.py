import reflex as rx
from .. import db

class OrdersState(rx.State):
    """Estado para manejar el listado y detalle de órdenes."""

    # --- Datos y paginación ---
    orders: list[dict] = []
    page: int = 0
    page_size: int = 10

    # --- Mensajes ---
    message: str = ""

    # --- Filtros ---
    filter_customer_id: str = ""
    filter_status: str = ""
    filter_date_from: str = ""  # formato YYYY-MM-DD
    filter_date_to: str = ""    # formato YYYY-MM-DD

    # --- Detalle de orden seleccionada ---
    selected_order_id: int | None = None
    order_header: dict | None = None
    order_items: list[dict] = []
    order_devoluciones: list[dict] = []

    # --- Formulario para crear orden simple (SP) ---
    form_customer_id: str = ""
    form_product_id: str = ""
    form_quantity: str = ""
    form_empleado_id: str = ""
    form_warehouse_id: str = ""
    
    form_total: str = ""
    form_metodo_pago: str = "EFECTIVO"  # EFECTIVO / TARJETA / TRANSFERENCIA
    # ==========================================================
    # Filtros y listado
    # ==========================================================

    def set_filter_date_from(self, value: str):
        """Setter explícito para evitar warning de auto-setters."""
        self.filter_date_from = value

    def set_filter_date_to(self, value: str):
        """Setter explícito para evitar warning de auto-setters."""
        self.filter_date_to = value

    def load_orders(self):
        """Carga las órdenes con filtros y paginación."""
        customer_id = None
        if self.filter_customer_id.strip() != "":
            try:
                customer_id = int(self.filter_customer_id)
            except ValueError:
                customer_id = None

        status = self.filter_status or None
        fecha_desde = self.filter_date_from or None
        fecha_hasta = self.filter_date_to or None

        self.orders = db.get_orders(
            customer_id=customer_id,
            status=status,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            page=self.page,
            page_size=self.page_size,
        )

    def next_page(self):
        """Paginación siguiente."""
        self.page += 1
        self.load_orders()

    def prev_page(self):
        """Paginación anterior."""
        if self.page > 0:
            self.page -= 1
        self.load_orders()

    def clear_filters(self):
        """Reinicia filtros y recarga."""
        self.filter_customer_id = ""
        self.filter_status = ""
        self.filter_date_from = ""
        self.filter_date_to = ""
        self.page = 0
        self.load_orders()

    # ==========================================================
    # Detalle de orden
    # ==========================================================

    def select_order(self, order_id: int):
        """Carga el detalle de una orden específica."""
        detail = db.get_order_detail(order_id)
        self.selected_order_id = order_id
        self.order_header = detail.get("order")
        self.order_items = detail.get("items", [])
        self.order_devoluciones = detail.get("devoluciones", [])

    def clear_selected_order(self):
        """Limpia el detalle."""
        self.selected_order_id = None
        self.order_header = None
        self.order_items = []
        self.order_devoluciones = []

    # ==========================================================
    # Crear orden simple (SP sp_crear_orden_simple)
    # ==========================================================

    def create_order_simple(self):
        """Crea una orden usando el SP sp_crear_orden_simple."""
        try:
            customer_id = int(self.form_customer_id)
            product_id = int(self.form_product_id)
            quantity = int(self.form_quantity)
            employee_id = int(self.form_empleado_id)
            warehouse_id = int(self.form_warehouse_id)
        except ValueError:
            self.message = "Todos los IDs y la cantidad deben ser numéricos."
            return

        ok, msg = db.create_order_simple(
            customer_id=customer_id,
            product_id=product_id,
            quantity=quantity,
            employee_id=employee_id,
            warehouse_id=warehouse_id,
        )

        if not ok and msg:
            self.message = msg
        else:
            self.message = "Orden creada correctamente."
            # limpia formulario, recarga listado
            self.form_customer_id = ""
            self.form_product_id = ""
            self.form_quantity = ""
            self.form_empleado_id = ""
            self.form_warehouse_id = ""
            self.load_orders()


# ===============================
# COMPONENTES DE UI
# ===============================

def orders_filters_bar() -> rx.Component:
    """Barra de filtros para órdenes."""
    return rx.vstack(
        rx.hstack(
            rx.input(
                placeholder="ID de cliente...",
                value=OrdersState.filter_customer_id,
                on_change=OrdersState.set_filter_customer_id,
                width="10rem",
            ),
            rx.select(
                items=[
                    "PENDIENTE",
                    "ENVIADO",
                    "ENTREGADO",
                    "REGRESADO",
                ],
                value=OrdersState.filter_status,
                on_change=OrdersState.set_filter_status,
                placeholder="Estado de orden",
                width="12rem",
            ),
            rx.input(
                placeholder="Desde (YYYY-MM-DD)",
                value=OrdersState.filter_date_from,
                on_change=OrdersState.set_filter_date_from,
                width="12rem",
            ),
            rx.input(
                placeholder="Hasta (YYYY-MM-DD)",
                value=OrdersState.filter_date_to,
                on_change=OrdersState.set_filter_date_to,
                width="12rem",
            ),
            rx.button(
                "Filtrar",
                color_scheme="orange",
                on_click=OrdersState.load_orders,
            ),
            rx.button(
                "Limpiar",
                variant="soft",
                on_click=OrdersState.clear_filters,
            ),
            spacing="3",
            wrap="wrap",
        ),
        align_items="flex-start",
        spacing="2",
        width="100%",
    )


def orders_table() -> rx.Component:
    """Tabla principal de órdenes."""
    headers = [
        "ID",
        "Fecha",
        "Cliente",
        "Estado",
        "Total",
        "Pago",
        "Envío",
        "Acciones",
    ]

    def render_row(o: dict):
        return rx.table.row(
            rx.table.cell(o["ID"]),
            rx.table.cell(o["FechaOrden"]),
            rx.table.cell(
                f'{o["NombreCliente"]} {o["ApellidoCliente"]}'
            ),
            rx.table.cell(o["Status"]),
            rx.table.cell(f'Q {o["Total"]}'),
            rx.table.cell(o["MetodoPago"]),
            rx.table.cell(o["EstadoEnvio"]),
            rx.table.cell(
                rx.button(
                    "Ver detalle",
                    size="1",
                    variant="soft",
                    color_scheme="orange",
                    on_click=lambda: OrdersState.select_order(o["ID"]),
                )
            ),
        )

    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[rx.table.column_header_cell(h) for h in headers],
                )
            ),
            rx.table.body(
                rx.foreach(OrdersState.orders, render_row)
            ),
        ),
        width="100%",
        overflow_x="auto",
        bg="white",
        padding="1rem",
        border_radius="1rem",
        box_shadow="0 8px 16px rgba(15,23,42,0.08)",
    )


def orders_pagination() -> rx.Component:
    """Botones de paginación."""
    return rx.hstack(
        rx.button("← Anterior", on_click=OrdersState.prev_page),
        rx.button("Siguiente →", on_click=OrdersState.next_page),
        spacing="4",
    )


def order_detail_panel() -> rx.Component:
    """Panel que muestra el detalle de la orden seleccionada."""
    return rx.cond(
        OrdersState.selected_order_id != None,
        _order_detail_box(),
    )


def _order_detail_box() -> rx.Component:
    header = OrdersState.order_header

    # Tabla de items
    def render_item_row(it: dict):
        return rx.table.row(
            rx.table.cell(it["NombreProducto"]),
            rx.table.cell(it["Cantidad"]),
            rx.table.cell(f'Q {it["PrecioUnidad"]}'),
            rx.table.cell(f'Q {it["Subtotal"]}'),
            rx.table.cell(
                rx.cond(
                    it["Devoluciones_ID"] != None,
                    "Sí",
                    "No",
                )
            ),
        )

    items_table = rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Producto"),
                rx.table.column_header_cell("Cantidad"),
                rx.table.column_header_cell("Precio unidad"),
                rx.table.column_header_cell("Subtotal"),
                rx.table.column_header_cell("¿Devuelto?"),
            )
        ),
        rx.table.body(
            rx.foreach(OrdersState.order_items, render_item_row)
        ),
    )

    # Lista de devoluciones
    devoluciones_box = rx.cond(
        (OrdersState.order_devoluciones != []),
        rx.vstack(
            rx.heading("Devoluciones", size="4", color="orange.9"),
            rx.foreach(
                OrdersState.order_devoluciones,
                lambda d: rx.box(
                    rx.text(
                        f'#{d["ID"]} - {d["Razon"]} '
                        f'({d["FechaDevolucion"]}) - Reembolso Q {d["Reembolso"]}'
                    ),
                    bg="#fef3c7",
                    padding="0.5rem 0.75rem",
                    border_radius="0.75rem",
                ),
            ),
            spacing="2",
        ),
    )

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(
                    f"Detalle de orden #{OrdersState.selected_order_id}",
                    size="5",
                    color="orange.9",
                ),
                rx.spacer(),
                rx.button(
                    "Cerrar detalle",
                    variant="ghost",
                    on_click=OrdersState.clear_selected_order,
                ),
                spacing="3",
                align_items="center",
            ),
            rx.cond(
                header != None,
                rx.vstack(
                    rx.text(
                        f'Cliente: {header["NombreCliente"]} {header["ApellidoCliente"]} '
                        f'({header["EmailCliente"]})'
                    ),
                    rx.text(
                        f'Fecha orden: {header["FechaOrden"]} | '
                        f'Pago: {header["MetodoPago"]} ({header["FechaPago"]})'
                    ),
                    rx.text(
                        f'Envío: {header["FechaEnvio"]} → {header["FechaEntrega"]} '
                        f'[{header["EstadoEnvio"]}]'
                    ),
                    rx.text(f'Total: Q {header["Total"]}'),
                    spacing="1",
                ),
            ),
            rx.box(
                items_table,
                bg="white",
                padding="1rem",
                border_radius="1rem",
                box_shadow="0 8px 16px rgba(15,23,42,0.08)",
            ),
            devoluciones_box,
            spacing="4",
        ),
        bg="#fff8f0",
        border="1px solid #fed7aa",
        border_radius="1.25rem",
        padding="1.5rem",
        width="100%",
    )

def create_order_form() -> rx.Component:
    """Formulario simple para crear una orden via stored procedure."""
    return rx.box(
        rx.vstack(
            rx.heading("Crear orden simple (SP)", size="5", color="orange.9"),
            rx.text(
                "Crea una orden con un solo producto, ligada a un cliente, empleado y bodega.",
                font_size="0.85rem",
                color="gray.9",
            ),
            rx.hstack(
                rx.input(
                    placeholder="ID de cliente",
                    value=OrdersState.form_customer_id,
                    on_change=OrdersState.set_form_customer_id,
                    width="10rem",
                ),
                rx.input(
                    placeholder="ID de producto",
                    value=OrdersState.form_product_id,
                    on_change=OrdersState.set_form_product_id,
                    width="10rem",
                ),
                rx.input(
                    placeholder="Cantidad",
                    value=OrdersState.form_quantity,
                    on_change=OrdersState.set_form_quantity,
                    width="8rem",
                ),
                spacing="3",
                wrap="wrap",
            ),
            rx.hstack(
                rx.input(
                    placeholder="ID de empleado",
                    value=OrdersState.form_empleado_id,
                    on_change=OrdersState.set_form_empleado_id,
                    width="10rem",
                ),
                rx.input(
                    placeholder="ID de bodega (warehouse)",
                    value=OrdersState.form_warehouse_id,
                    on_change=OrdersState.set_form_warehouse_id,
                    width="12rem",
                ),
                spacing="3",
                wrap="wrap",
            ),
            rx.button(
                "Crear orden",
                color_scheme="orange",
                on_click=OrdersState.create_order_simple,  # ✅ nombre correcto del método
            ),
            rx.cond(
                OrdersState.message != "",
                rx.text(
                    OrdersState.message,
                    color="orange.10",
                    font_size="0.85rem",
                ),
            ),
            spacing="3",
        ),
        bg="white",
        padding="1.5rem",
        border_radius="1.25rem",
        box_shadow="0 8px 16px rgba(15,23,42,0.12)",
        width="100%",
    )


# ===============================
# PÁGINA PRINCIPAL
# ===============================

def orders_page() -> rx.Component:
    """Vista principal del módulo Órdenes con detalle."""
    return rx.vstack(
        rx.heading("Órdenes", size="6", color="orange.9"),
        rx.text("Consulta, filtra y revisa el detalle de las órdenes de LootBox."),
        rx.divider(margin_y="0.5rem"),
        orders_filters_bar(),
        rx.cond(
            OrdersState.message != "",
            rx.text(
                OrdersState.message,
                color="orange.10",
                font_size="0.85rem",
            ),
        ),
        orders_table(),
        orders_pagination(),
        rx.divider(margin_y="1rem"),
        order_detail_panel(),
        rx.divider(margin_y="1rem"),
        create_order_form(),
        spacing="4",
        width="100%",
        on_mount=OrdersState.load_orders,
    )
