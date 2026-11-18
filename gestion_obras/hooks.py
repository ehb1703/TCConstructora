# -*- coding: utf-8 -*-

DOCUMENTOS = {
    'doc_csf': 'Constancia de Situación Fiscal (CSF)', 'doc_opinion_cumplimiento': 'Opinión de Cumplimiento',
    'doc_acta_constitutiva': 'Acta Constitutiva', 'doc_estado_cuenta': 'Estado de cuenta bancario', 'doc_repse': 'REPSE',
    'doc_csf_infonavit': 'CSF Infonavit', 'doc_siroc': 'SIROC', 'doc_retencion_isr': 'Comprobantes de Retención de ISR',
    'doc_programa_seguridad': 'Programa de Seguridad y Salud', 'doc_fianzas': 'Fianzas (cumplimiento y vicios ocultos)',
}
TIPOS = {'tipo_suministro': 'Suministro', 'tipo_subcontrato': 'Subcontrato'}
PLANES = {'plan_n2_frente': 'N2 FRENTE', 'plan_n3_partida': 'N3 PARTIDA', 'plan_n4_concepto': 'N4 CONCEPTO', 'plan_n5_insumo': 'N5 INSUMO'}
DOMINIOS = ('purchase_order', 'bill', 'timesheet', 'stock_picking', 'stock_move')


# T0120: usuarios de la matriz de autorizaciones (por usuario de Odoo; Ignacio y Carlos Curiel por nombre cuando tengan usuario)
USUARIOS_MATRIZ = {
    'group_tc_budget_control': {'logins': ['yperez', 'jesau', 'amedina'], 'nombres': []},
    'group_tc_contracts_manager': {'logins': ['sdelrio', 'scortes'], 'nombres': []},
    # Nombre completo: 'IGNACIO%CURIEL' también coincidiría con CARLOS IGNACIO CURIEL y lo haría Director General
    'group_tc_director_operativo': {'logins': [], 'nombres': ['CARLOS IGNACIO CURIEL']},
    'group_tc_director_general': {'logins': [], 'nombres': ['IGNACIO JAVIER CURIEL']},
}
# Grupos de la versión anterior y el nivel que los sustituye
GRUPOS_ANTERIORES = {'group_aprobacion_tecnica': 'group_tc_budget_control', 'group_activar_contrato': 'group_tc_director_operativo',
                     'group_aprobacion_direccion': 'group_tc_director_operativo'}


def asignar_matriz_autorizaciones(env):
    """Asigna los usuarios a su nivel. Solo agrega: nunca quita a nadie de un grupo."""
    Users = env['res.users'].with_context(active_test=False)
    for xmlid, quien in USUARIOS_MATRIZ.items():
        grupo = env.ref(f'gestion_obras.{xmlid}')
        usuarios = Users.search([('login', 'in', quien['logins']), ('active', '=', True)])
        for patron in quien['nombres']:
            usuarios |= Users.search([('name', '=ilike', f'{patron}%'), ('share', '=', False), ('active', '=', True)])
        if usuarios:
            grupo.write({'users': [(4, u.id) for u in usuarios]})
    # El Administrador es quien registra hoy los pagos a proveedores: queda en Nivel 1 para no dejar sin quién autorizarlos
    env.ref('gestion_obras.group_tc_director_general').write({'users': [(4, env.ref('base.user_admin').id)]})
    for anterior, nuevo in GRUPOS_ANTERIORES.items():
        viejo = env.ref(f'gestion_obras.{anterior}', raise_if_not_found=False)
        if viejo and viejo.users:
            env.ref(f'gestion_obras.{nuevo}').write({'users': [(4, u.id) for u in viejo.users]})


def post_init_hook(env):
    asignar_matriz_autorizaciones(env)


def adoptar_kontrol(env):
    """T0110: deja los planes N1-N5 y la obligatoriedad de N1 a nombre de gestion_obras sin duplicar nada."""
    cr = env.cr
    # 1) Lo que ya instalaron analytic_kontrol o project_extra (versiones anteriores de T0110) cambia de dueño
    nombres = list(PLANES) + [f'regla_n1_{d}' for d in DOMINIOS] + ['cuenta_hospital_n1', 'cuenta_hospital_n2_f1', 'cuenta_hospital_n3_a21',
        'field_project_task__frente_account_id', 'field_project_task__partida_account_id', 'view_task_form_partida_analitica', 'view_task_list_partida_analitica']
    cr.execute("""UPDATE ir_model_data SET module = 'gestion_obras'
                   WHERE module IN ('project_extra', 'analytic_kontrol') AND name = ANY(%s)
                     AND name NOT IN (SELECT name FROM ir_model_data WHERE module = 'gestion_obras')""", (nombres,))
    env.registry.clear_cache()  # los xml_id cambiaron por SQL: que env.ref no use lo que tenía en caché
    # 2) El plan 'Project' pasa a ser N1 OBRA en todos los idiomas (conserva sus cuentas y movimientos).
    #    Va aquí y no en XML: su xml_id es noupdate en analytic y un -u no lo reescribe.
    n1 = env.ref('analytic.analytic_plan_projects')
    for lang in env['res.lang'].search([]).mapped('code'):
        n1.with_context(lang=lang).write({'name': 'N1 OBRA', 'description': 'Proyecto / Obra'})
    # 3) Lo capturado a mano con el mismo nombre se adopta
    IMD = env['ir.model.data']
    adoptar = [(xmlid, env['account.analytic.plan'].search([('name', '=', nombre), ('parent_id', '=', False)], order='id', limit=1)) for xmlid, nombre in PLANES.items()]
    adoptar += [(f'regla_n1_{d}', env['account.analytic.applicability'].search([('analytic_plan_id', '=', n1.id), ('business_domain', '=', d)], order='id', limit=1)) for d in DOMINIOS]
    for xmlid, registro in adoptar:
        if registro and not env.ref(f'gestion_obras.{xmlid}', raise_if_not_found=False):
            IMD.create({'module': 'gestion_obras', 'name': xmlid, 'model': registro._name, 'res_id': registro.id, 'noupdate': True})


def pre_init_hook(env):
    """Adopta los documentos y tipos de contratista capturados a mano con el mismo nombre, para no duplicarlos al instalar."""
    adoptar_kontrol(env)
    IMD = env['ir.model.data']

    def adoptar(xmlid, registro):
        if registro and not IMD.search_count([('module', '=', 'gestion_obras'), ('name', '=', xmlid)]):
            IMD.create({'module': 'gestion_obras', 'name': xmlid, 'model': registro._name, 'res_id': registro.id, 'noupdate': True})

    Doc = env['project.docsrequeridos'].with_context(active_test=False)
    for xmlid, nombre in DOCUMENTOS.items():
        adoptar(xmlid, Doc.search([('nombre_archivo', '=ilike', nombre), ('model_id.model', '=', 'res.partner')], order='active desc, id', limit=1))
    Tipo = env['partner.contractor.type'].with_context(active_test=False)
    for xmlid, nombre in TIPOS.items():
        tipo = Tipo.search([('name', '=ilike', nombre)], order='active desc, id', limit=1)
        adoptar(xmlid, tipo)
        # los datos los vuelven requeridos: si estaban como no requeridos chocaría la validación de documentos repetidos
        nuestros = IMD.search([('module', '=', 'gestion_obras'), ('model', '=', 'project.docsrequeridos')]).mapped('res_id')
        if tipo and tipo.docto_noreq_ids.filtered(lambda d: d.id in nuestros):
            tipo.docto_noreq_ids = [(3, i) for i in nuestros if i in tipo.docto_noreq_ids.ids]
