# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, _

def update_data(cr):
    menus = {
        508: 'Permisos',           # Tiempo personal (raíz)
        509: 'Mis Permisos',       # Mi tiempo
        511: 'Mis Permisos',       # Mi tiempo personal
        515: 'Permisos',           # Tiempo personal (Gestión)
        522: 'Tipos de permisos',  # Tipos de tiempo personal
        559: 'Permisos por reportar',  # Tiempo personal por reportar
    }

    actions = {
        841: 'Mis permisos',           # Mi tiempo personal
        840: 'Solicitud de permisos',  # Solicitud de tiempo personal
        842: 'Todos los permisos',     # Todo el tiempo personal
        859: 'Todos los permisos',     # Todo el tiempo personal (dashboard)
        843: 'Permisos',              # Tiempo personal (asignaciones)
        917: 'Permisos',              # Tiempo personal (nómina)
        916: 'Permisos por diferir',  # Tiempo personal por diferir
        857: 'Análisis de permisos',  # Análisis de tiempo personal
        858: 'Análisis de permisos',  # Análisis de tiempo personal
        844: 'Análisis de permisos',  # Análisis de tiempo personal
        853: 'Resumen de permisos',   # Resumen de tiempo personal
        845: 'Tipos de permisos',     # Tipos de tiempo personal
    }

    for menu_id, new_name in menus.items():
        cr.execute("UPDATE ir_ui_menu SET name = jsonb_set(COALESCE(name, '{}')::jsonb, '{es_MX}', %s::jsonb) WHERE id = %s ", (f'"{new_name}"', menu_id))
        
    for action_id, new_name in actions.items():
        cr.execute("UPDATE ir_act_window SET name = jsonb_set(COALESCE(name, '{}')::jsonb, '{es_MX}', %s::jsonb) WHERE id = %s", (f'"{new_name}"', action_id))


def migrate(cr, version):
    if not version:
        return
    update_data(cr)