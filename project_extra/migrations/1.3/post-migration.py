# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    # La columna vieja fue renombrada a capacidad_old por el pre-migration.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'requisition_acarreos' AND column_name = 'capacidad_old'
    """)
    if not cr.fetchone():
        return

    # Crear la columna FK nueva 'capacidad' (integer) manualmente, porque el modelo
    # de requisition_residents que la define aun no se ha cargado en este punto
    # (Odoo procesa project_extra completo antes que requisition_residents).
    # requisition_residents luego reconocera esta columna y le agregara la constraint FK.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'requisition_acarreos' AND column_name = 'capacidad'
    """)
    if not cr.fetchone():
        cr.execute("ALTER TABLE requisition_acarreos ADD COLUMN capacidad integer")

    env = api.Environment(cr, SUPERUSER_ID, {})

    mapping = {
        '7': 'project_extra.capacidad_7m3',
        '14': 'project_extra.capacidad_14m3',
        '24': 'project_extra.capacidad_24m3',
    }

    for old_value, xmlid in mapping.items():
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            cr.execute(
                "UPDATE requisition_acarreos SET capacidad = %s WHERE capacidad_old = %s",
                (record.id, old_value)
            )

    cr.execute("ALTER TABLE requisition_acarreos DROP COLUMN capacidad_old")
