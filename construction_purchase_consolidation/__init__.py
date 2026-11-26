# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_init_hook(env):
    # Estados nuevos de la requisición (T0135): Enviado -> En Autorización; Aprobado (ya con cotizaciones) -> Enviado a Compras
    env.cr.execute("UPDATE requisition_materials SET state = 'in_approval' WHERE state = 'send'")
    env.cr.execute("UPDATE requisition_materials SET state = 'sent_purchase' WHERE state = 'aprobado'")
    # Las requisiciones que ya generaron sus cotizaciones con el proceso anterior no quedan pendientes de consolidar
    env.cr.execute("""UPDATE requisition_materials_line l SET x_atendida_anterior = TRUE
                      FROM requisition_materials r WHERE r.id = l.req_id AND r.state = 'sent_purchase'
                      AND EXISTS (SELECT 1 FROM purchase_order po WHERE po.materials_id = r.id)""")
    env['requisition.materials.line'].search([])._compute_x_pendiente_cotizar()
    # Regla 5 (umbral de $100,000 MXN): la validación dispara cuando la orden pasa a 'Por aprobar', que solo existe con la
    # aprobación de órdenes en dos pasos (Compras > Ajustes > Aprobación de órdenes) a partir de ese monto
    env['res.company'].search([]).write({'po_double_validation': 'two_step', 'po_double_validation_amount': 100000.0})
