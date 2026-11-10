"""Tools de escritura del agente de operaciones.

Principio del laboratorio: el LLM conversa, el código decide lo que es regla.
- Las validaciones (cliente existe, hay stock, cantidad razonable) están aquí, no en el prompt.
- Ninguna venta se registra sin que una persona la apruebe en adk web.
- Cada decisión (aprobada o rechazada) queda en la tabla acciones_agente.

Escriben con DATABASE_URL (la misma base de Neon). El MCP sigue en solo lectura: leer por MCP,
escribir solo por tools propias con reglas y aprobación.
"""
import json
from decimal import Decimal

from google.adk.tools import ToolContext
from sqlalchemy import text

from src.repositories.database import get_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_UNIDADES_PEDIDO = 20
UMBRAL_AJUSTE = 10

_DDL = """
CREATE TABLE IF NOT EXISTS acciones_agente (
    id         SERIAL PRIMARY KEY,
    creado_en  TIMESTAMP NOT NULL DEFAULT NOW(),
    agente     VARCHAR(50) NOT NULL,
    accion     VARCHAR(50) NOT NULL,
    estado     VARCHAR(20) NOT NULL,
    detalle    JSONB NOT NULL
)"""
_listo = False


def _engine():
    global _listo
    eng = get_engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL no configurado")
    if not _listo:
        with eng.begin() as con:
            con.execute(text(_DDL))
        _listo = True
    return eng


def _auditar(con, accion: str, estado: str, detalle: dict) -> None:
    con.execute(
        text("INSERT INTO acciones_agente (agente, accion, estado, detalle) VALUES ('operaciones', :a, :e, CAST(:d AS JSONB))"),
        {"a": accion, "e": estado, "d": json.dumps(detalle, ensure_ascii=False, default=str)},
    )


def buscar_producto(texto: str) -> dict:
    """Busca productos por nombre (búsqueda parcial). Devuelve id, descripción, precio y stock.

    Args:
        texto: parte del nombre del producto, por ejemplo "laptop" o "monitor".
    """
    try:
        with _engine().connect() as con:
            filas = con.execute(
                text("SELECT id, descripcion, precio, stock FROM productos WHERE descripcion ILIKE :t ORDER BY id LIMIT 5"),
                {"t": f"%{texto}%"},
            ).mappings().all()
        if not filas:
            return {"error": f"No hay productos que contengan '{texto}'."}
        return {"productos": [{**f, "precio": float(f["precio"])} for f in filas]}
    except Exception as exc:
        return {"error": f"No se pudo consultar productos: {exc}"}


def registrar_pedido(dni_cliente: str, dni_vendedor: str, producto_id: int, cantidad: int, tool_context: ToolContext) -> dict:
    """Registra un pedido de venta (estado pendiente) y descuenta el stock. Siempre requiere aprobación humana.

    Args:
        dni_cliente: DNI de 8 dígitos del cliente.
        dni_vendedor: DNI de 8 dígitos del vendedor que atiende.
        producto_id: id del producto (obtenlo con buscar_producto).
        cantidad: unidades, entre 1 y 20.
    """
    # 1. Reglas de negocio en código: se validan ANTES de molestar a una persona
    if not 1 <= int(cantidad) <= MAX_UNIDADES_PEDIDO:
        return {"error": f"La cantidad debe estar entre 1 y {MAX_UNIDADES_PEDIDO}. Pedidos mayores van por el área comercial."}
    try:
        eng = _engine()
        with eng.connect() as con:
            cli = con.execute(text("SELECT id, nombres FROM clientes WHERE dni = :d"), {"d": dni_cliente}).mappings().first()
            ven = con.execute(text("SELECT id, nombres FROM vendedores WHERE dni = :d"), {"d": dni_vendedor}).mappings().first()
            prod = con.execute(text("SELECT id, descripcion, precio, stock FROM productos WHERE id = :i"), {"i": producto_id}).mappings().first()
    except Exception as exc:
        return {"error": f"No se pudo validar el pedido: {exc}"}
    if not cli:
        return {"error": f"No existe un cliente con DNI {dni_cliente}."}
    if not ven:
        return {"error": f"No existe un vendedor con DNI {dni_vendedor}."}
    if not prod:
        return {"error": f"No existe el producto {producto_id}."}
    if prod["stock"] < cantidad:
        return {"error": f"Stock insuficiente: hay {prod['stock']} unidades de {prod['descripcion']}."}

    total = Decimal(prod["precio"]) * cantidad
    resumen = {
        "cliente": cli["nombres"], "vendedor": ven["nombres"], "producto": prod["descripcion"],
        "cantidad": cantidad, "precio_unitario": float(prod["precio"]), "total": float(total),
        "stock_despues": prod["stock"] - cantidad,
    }

    # 2. Human-in-the-loop: la primera vez, pausa y muestra a la persona lo que va a aprobar
    confirmacion = tool_context.tool_confirmation
    if confirmacion is None:
        tool_context.request_confirmation(
            hint=(f"Aprobar pedido: {cantidad} x {prod['descripcion']} para {cli['nombres']} "
                  f"(vendedor {ven['nombres']}). Total S/ {total:,.2f}. Stock queda en {resumen['stock_despues']}."),
            payload={"aprobado_por": "", "comentario": ""},
        )
        return {"estado": "pendiente_de_aprobacion", "resumen": resumen}

    datos_aprobacion = confirmacion.payload if isinstance(confirmacion.payload, dict) else {}
    if not confirmacion.confirmed:
        with eng.begin() as con:
            _auditar(con, "registrar_pedido", "rechazado", {**resumen, **datos_aprobacion})
        return {"estado": "rechazado", "mensaje": "La persona responsable rechazó el pedido. No se registró nada."}

    # 3. Escritura en una sola transacción: venta, detalle, stock y auditoría
    with eng.begin() as con:
        venta_id = con.execute(
            text("INSERT INTO ventas (fecha_venta, id_cliente, total_venta, estado, id_vendedor) "
                 "VALUES (CURRENT_DATE, :c, :t, 'pendiente', :v) RETURNING id"),
            {"c": cli["id"], "t": total, "v": ven["id"]},
        ).scalar()
        con.execute(
            text("INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario, subtotal) VALUES (:v, :p, :q, :pu, :s)"),
            {"v": venta_id, "p": prod["id"], "q": cantidad, "pu": prod["precio"], "s": total},
        )
        con.execute(text("UPDATE productos SET stock = stock - :q WHERE id = :p"), {"q": cantidad, "p": prod["id"]})
        _auditar(con, "registrar_pedido", "aprobado", {**resumen, "venta_id": venta_id, **datos_aprobacion})
    logger.info("pedido_registrado", extra={"venta_id": venta_id, "total": float(total)})
    return {"estado": "registrado", "venta_id": venta_id, "resumen": resumen}


def ajustar_stock(producto_id: int, delta: int, motivo: str, tool_context: ToolContext) -> dict:
    """Suma (delta positivo) o resta (delta negativo) unidades al stock de un producto.
    Ajustes de más de 10 unidades piden aprobación humana.

    Args:
        producto_id: id del producto.
        delta: unidades a sumar o restar, entre -100 y 100.
        motivo: por qué se ajusta, por ejemplo "llegó reposición" o "producto dañado".
    """
    if not -100 <= int(delta) <= 100 or delta == 0:
        return {"error": "El ajuste debe estar entre -100 y 100 y no puede ser 0."}
    if len(motivo.strip()) < 5:
        return {"error": "Indica un motivo claro para el ajuste."}
    # Umbral de riesgo: los ajustes pequeños pasan solos, los grandes los aprueba una persona
    aprobacion = {}
    if abs(int(delta)) > UMBRAL_AJUSTE:
        conf = tool_context.tool_confirmation
        if conf is None:
            tool_context.request_confirmation(
                hint=f"Aprobar ajuste de stock del producto {producto_id}: {delta:+d} unidades. Motivo: {motivo}.",
                payload={"aprobado_por": ""},
            )
            return {"estado": "pendiente_de_aprobacion", "producto_id": producto_id, "delta": delta}
        if not conf.confirmed:
            return {"estado": "rechazado", "mensaje": "La persona responsable rechazó el ajuste."}
        aprobacion = conf.payload if isinstance(conf.payload, dict) else {}
    try:
        with _engine().begin() as con:
            prod = con.execute(text("SELECT descripcion, stock FROM productos WHERE id = :i FOR UPDATE"), {"i": producto_id}).mappings().first()
            if not prod:
                return {"error": f"No existe el producto {producto_id}."}
            nuevo = prod["stock"] + delta
            if nuevo < 0:
                return {"error": f"El stock no puede quedar negativo (hay {prod['stock']})."}
            con.execute(text("UPDATE productos SET stock = :n WHERE id = :i"), {"n": nuevo, "i": producto_id})
            _auditar(con, "ajustar_stock", "aplicado", {"producto": prod["descripcion"], "antes": prod["stock"], "despues": nuevo, "motivo": motivo, **aprobacion})
        return {"estado": "aplicado", "producto": prod["descripcion"], "stock_antes": prod["stock"], "stock_despues": nuevo}
    except Exception as exc:
        return {"error": f"No se pudo ajustar el stock: {exc}"}
