# -*- coding: utf-8 -*-
{
    'name': 'Consolidación de Compras y Requisiciones Multi-Frente',
    'version': '18.0.1.0.0',
    'summary': 'Requisiciones por Proyecto Global y Frente, compras consolidadas por volumen e imputación analítica por frente (T0135)',
    'description': """
Tarea 0135 - Consolidación de Compras y Requisiciones
=====================================================
Implementa la especificación técnica "Consolidación de Compras y Requisiciones Multi-Frente en Odoo 18" y la
"Matriz de validaciones y permisos por perfil de usuario" de Grupo Constructor TC:

- Campos del catálogo técnico: x_proyecto_id, x_frente_id, x_tipo_requerimiento, x_motivo_extraordinario
  (y los que usan las reglas: x_orden_cambio_id, x_aprobado_direccion, x_precio_limite_frente).
- Estados de la requisición de materiales: Borrador, En Autorización, Autorizado (por Costos) y Enviado a Compras.
- Consolidación en Compras: una Solicitud de Cotización por proveedor con las requisiciones de varios frentes del
  mismo Proyecto Global, una línea por insumo y frente con su cuenta analítica, y el precio negociado propagado.
- Reglas de validación como Acciones Automatizadas (base.automation), según la guía de configuración del documento.
    """,
    'category': 'Purchases',
    'depends': ['requisition_residents', 'gestion_obras', 'purchase', 'base_automation', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'views/requisicion_views.xml',
        'views/compras_views.xml',
        'wizard/crear_rfq_views.xml',
        'data/base_automation.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
