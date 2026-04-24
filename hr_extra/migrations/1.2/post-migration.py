# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, _

def update_data(cr):
    # T0084: Revocar grupos que pudieron haberse otorgado en intentos previos. La nueva solución usa check_access_rights en hr.contract, no grupos de Odoo.
    grupos_a_revocar_xmlids = [('base', 'group_erp_manager'), ('account', 'group_account_manager'), ('hr_payroll', 'group_hr_payroll_manager'),
        ('hr', 'group_hr_manager'), ('purchase', 'group_purchase_manager'),]

    # Obtener usuarios con encargado_nomina para verificar si se les otorgaron grupos
    cr.execute('''SELECT DISTINCT rr.user_id
        FROM hr_employee he JOIN resource_resource rr ON rr.id = he.resource_id
        WHERE he.encargado_nomina IN ('semanal', 'quincenal', 'ambas')
          AND rr.user_id IS NOT NULL
          AND he.active = true ''')
    user_ids = [row[0] for row in cr.fetchall()]
    for module, name in grupos_a_revocar_xmlids:
        cr.execute("SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = 'res.groups' ", (module, name))
        row = cr.fetchone()
        if not row:
            continue

        grupo_id = row[0]
        for user_id in user_ids:
            cr.execute('DELETE FROM res_groups_users_rel WHERE gid = %s AND uid = %s ', (grupo_id, user_id))


def migrate(cr, version):
    if not version:
        return

    update_data(cr)