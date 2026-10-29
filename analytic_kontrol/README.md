# analytic_kontrol (T0110)

Configuración de la contabilidad analítica para el presupuesto Kontrol.

## Qué hace al instalarse
- Renombra el plan analítico `Project` a **N1 OBRA** (conserva sus cuentas y movimientos).
- Crea los planes raíz **N2 FRENTE**, **N3 PARTIDA**, **N4 CONCEPTO** y **N5 INSUMO**; cada uno con su propia columna analítica, de modo que los 5 niveles pueden usarse a la vez en una distribución.
- Hace **N1 obligatorio** en pedidos de compra, facturas de proveedor, partes de horas, albaranes y movimientos de stock. N2 a N5 no son obligatorios.
- Carga el ejemplo **HOSPITAL CIVIL ORIENTE / HOSPITAL CIVIL ORIENTE F1 / A2.1 CIMENTACION** (`data/ejemplo_data.xml`). Es solo demostrativo: quitarlo del `__manifest__.py` antes de producción.

## Requisitos
Depende de `analytic`, `account`, `purchase`, `hr_timesheet` y `stock_analytic` (este último viene en la carpeta `addons`).

## Instalación
Actualizar primero los módulos de `addons` (`-u`) y después instalar:

    odoo -d <base> -i analytic_kontrol --stop-after-init

Es idempotente: `-u analytic_kontrol` no duplica planes, reglas ni cuentas. Si la base ya tenía los planes o reglas creados a mano con esos mismos nombres, el módulo los adopta en lugar de duplicarlos.

## Producción
La obligatoriedad de N1 bloqueará documentos de compra, factura, horas y almacén sin cuenta N1. Confirmarlo antes de instalar ahí.
