# -*- coding: utf-8 -*-


def migrate(cr, version):
    # 1) Eliminar la metadata vieja del Selection 'capacidad' de requisition.acarreos.
    # Al cambiar el campo de Selection a Many2one, estos ir.model.fields.selection
    # quedan huerfanos y Odoo revienta al procesarlos en _process_end
    # ((field.ondelete or {}).get(...) falla porque Many2one.ondelete es str, no dict).
    cr.execute("""
        SELECT s.id FROM ir_model_fields_selection s
        JOIN ir_model_fields f ON s.field_id = f.id
        WHERE f.model = 'requisition.acarreos' AND f.name = 'capacidad'
    """)
    sel_ids = [r[0] for r in cr.fetchall()]
    if sel_ids:
        # Borrar ir.model.data que apunta a estos registros de selection
        cr.execute(
            "DELETE FROM ir_model_data WHERE model = 'ir.model.fields.selection' AND res_id = ANY(%s)",
            (sel_ids,)
        )
        cr.execute(
            "DELETE FROM ir_model_fields_selection WHERE id = ANY(%s)",
            (sel_ids,)
        )

    # 2) Renombrar la columna 'capacidad' (varchar) a 'capacidad_old' para preservar
    # los datos historicos antes de que se cree la nueva columna Many2one (integer FK).
    cr.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'requisition_acarreos' AND column_name = 'capacidad'
    """)
    row = cr.fetchone()
    if row and row[1] in ('character varying', 'text'):
        cr.execute("ALTER TABLE requisition_acarreos RENAME COLUMN capacidad TO capacidad_old")
