# -*- coding: utf-8 -*-
from odoo import _
from odoo.exceptions import UserError

# T0120: matriz jerárquica de autorizaciones (cada nivel hereda al inferior)
NIVEL_4 = 'gestion_obras.group_tc_budget_control'
NIVEL_3 = 'gestion_obras.group_tc_contracts_manager'
NIVEL_2 = 'gestion_obras.group_tc_director_operativo'
NIVEL_1 = 'gestion_obras.group_tc_director_general'
NOMBRE_NIVEL = {NIVEL_4: 'Nivel 4: Control Presupuestal y Cambios', NIVEL_3: 'Nivel 3: Gerencia de Operaciones y Contratos',
                NIVEL_2: 'Nivel 2: Director Operativo', NIVEL_1: 'Nivel 1: Director General'}


def exigir_nivel(env, grupo, accion):
    """El candado va en el servidor: ocultar el botón no basta porque la acción se puede llamar por otras vías."""
    if not env.su and not env.user.has_group(grupo):
        raise UserError(_('No tiene permiso para %(accion)s. Se requiere %(nivel)s.', accion=accion, nivel=NOMBRE_NIVEL[grupo]))
