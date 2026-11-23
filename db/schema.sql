-- Esquema de CaféDMC (SQLite 3.37+, tablas STRICT).
-- Dinero en céntimos (INTEGER). Fechas en TEXT ISO-8601 UTC.
-- IMPORTANTE: SQLite trae las claves foráneas apagadas por defecto; la aplicación
-- debe ejecutar `PRAGMA foreign_keys = ON;` en CADA conexión que abra.
PRAGMA foreign_keys = ON;

-- ============================================================================
-- Módulo Catálogo (dueño: app/catalogo/repositorio.py)
-- ============================================================================

CREATE TABLE IF NOT EXISTS categoria (
    id     INTEGER PRIMARY KEY,
    nombre TEXT    NOT NULL COLLATE NOCASE UNIQUE
                   CHECK (length(trim(nombre)) > 0)
) STRICT;

CREATE TABLE IF NOT EXISTS producto (
    id              INTEGER PRIMARY KEY,
    categoria_id    INTEGER NOT NULL
                    REFERENCES categoria (id) ON DELETE RESTRICT,
    nombre          TEXT    NOT NULL COLLATE NOCASE UNIQUE
                    CHECK (length(trim(nombre)) > 0),
    precio_centimos INTEGER NOT NULL CHECK (precio_centimos > 0),
    stock           INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
) STRICT;

-- Ver productos por categoría, ya ordenados por nombre.
CREATE INDEX IF NOT EXISTS ix_producto_categoria_nombre
    ON producto (categoria_id, nombre);

-- ============================================================================
-- Módulo Pedidos (dueño: app/pedidos/repositorio.py)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cliente (
    id        INTEGER PRIMARY KEY,
    nombre    TEXT    NOT NULL CHECK (length(trim(nombre)) > 0),
    -- Opcional; UNIQUE admite varios NULL en SQLite.
    email     TEXT    COLLATE NOCASE UNIQUE,
    creado_en TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

CREATE TABLE IF NOT EXISTS pedido (
    id         INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL
               REFERENCES cliente (id) ON DELETE RESTRICT,
    -- Las transiciones válidas las controla app/pedidos/servicio.py.
    estado     TEXT    NOT NULL DEFAULT 'pendiente'
               CHECK (estado IN ('pendiente', 'pagado', 'entregado', 'anulado')),
    creado_en  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

-- Historial de pedidos de un cliente.
CREATE INDEX IF NOT EXISTS ix_pedido_cliente_creado
    ON pedido (cliente_id, creado_en);

-- Pedidos por estado (pendientes del cajero, ventas pagadas/entregadas).
CREATE INDEX IF NOT EXISTS ix_pedido_estado_creado
    ON pedido (estado, creado_en);

-- El total del pedido no se guarda: SUM(cantidad * precio_unitario_centimos).
CREATE TABLE IF NOT EXISTS pedido_item (
    pedido_id                INTEGER NOT NULL
                             REFERENCES pedido (id) ON DELETE CASCADE,
    producto_id              INTEGER NOT NULL
                             REFERENCES producto (id) ON DELETE RESTRICT,
    cantidad                 INTEGER NOT NULL CHECK (cantidad > 0),
    -- Precio congelado al momento del pedido.
    precio_unitario_centimos INTEGER NOT NULL CHECK (precio_unitario_centimos > 0),
    PRIMARY KEY (pedido_id, producto_id)
) STRICT;

-- Ranking de productos más vendidos.
CREATE INDEX IF NOT EXISTS ix_pedido_item_producto
    ON pedido_item (producto_id);
