# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    """El encabezado ahora se reconoce por su texto ('Código'), no por ser el primer renglón: el cargador original no guarda el
    encabezado, así que en las licitaciones ya cargadas el primer renglón es un insumo real y no debe ocultarse."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    lineas = env['crm.input.line'].search([])
    lineas._compute_es_encabezado()
    lineas.flush_recordset(['es_encabezado'])
