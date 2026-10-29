# -*- coding: utf-8 -*-


def pre_init_hook(env):
    """ Adopta los planes, cuentas y reglas ya creados a mano con el mismo nombre para que el módulo no los duplique. """
    n1 = env.ref('analytic.analytic_plan_projects')
    Imd = env['ir.model.data']
    adoptar = [
        ('plan_n2_frente', 'account.analytic.plan', [('name', '=', 'N2 FRENTE'), ('parent_id', '=', False)]),
        ('plan_n3_partida', 'account.analytic.plan', [('name', '=', 'N3 PARTIDA'), ('parent_id', '=', False)]),
        ('plan_n4_concepto', 'account.analytic.plan', [('name', '=', 'N4 CONCEPTO'), ('parent_id', '=', False)]),
        ('plan_n5_insumo', 'account.analytic.plan', [('name', '=', 'N5 INSUMO'), ('parent_id', '=', False)]),
    ]
    for dominio in ('purchase_order', 'bill', 'timesheet', 'stock_picking', 'stock_move'):
        adoptar.append((f'regla_n1_{dominio}', 'account.analytic.applicability',
                        [('analytic_plan_id', '=', n1.id), ('business_domain', '=', dominio)]))
    adoptar += [
        ('cuenta_hospital_n1', 'account.analytic.account', [('name', '=', 'HOSPITAL CIVIL ORIENTE'), ('plan_id', '=', n1.id)]),
        ('cuenta_hospital_n2_f1', 'account.analytic.account', [('name', '=', 'HOSPITAL CIVIL ORIENTE F1'), ('plan_id.name', '=', 'N2 FRENTE')]),
        ('cuenta_hospital_n3_a21', 'account.analytic.account', [('name', '=', 'A2.1 CIMENTACION'), ('plan_id.name', '=', 'N3 PARTIDA')]),
    ]
    for nombre, modelo, dom in adoptar:
        if env.ref(f'analytic_kontrol.{nombre}', raise_if_not_found=False):
            continue
        rec = env[modelo].search(dom, limit=1)
        if rec:
            Imd.create({'module': 'analytic_kontrol', 'name': nombre, 'model': modelo, 'res_id': rec.id, 'noupdate': True})
