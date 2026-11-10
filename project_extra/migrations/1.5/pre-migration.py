# -*- coding: utf-8 -*-

# T0110 pasa de project_extra a gestion_obras: antes de que project_extra suelte sus datos, los registros
# cambian de dueño para que la actualización no borre planes, reglas, cuentas, campos ni vistas.
NOMBRES = ['plan_n2_frente', 'plan_n3_partida', 'plan_n4_concepto', 'plan_n5_insumo',
           'regla_n1_purchase_order', 'regla_n1_bill', 'regla_n1_timesheet', 'regla_n1_stock_picking', 'regla_n1_stock_move',
           'cuenta_hospital_n1', 'cuenta_hospital_n2_f1', 'cuenta_hospital_n3_a21',
           'field_project_task__frente_account_id', 'field_project_task__partida_account_id',
           'view_task_form_partida_analitica', 'view_task_list_partida_analitica']


def migrate(cr, version):
    cr.execute("""UPDATE ir_model_data SET module = 'gestion_obras'
                   WHERE module IN ('project_extra', 'analytic_kontrol') AND name = ANY(%s)
                     AND name NOT IN (SELECT name FROM ir_model_data WHERE module = 'gestion_obras')""", (NOMBRES,))
