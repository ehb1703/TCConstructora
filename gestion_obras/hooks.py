# -*- coding: utf-8 -*-

DOCUMENTOS = {
    'doc_csf': 'Constancia de Situación Fiscal (CSF)', 'doc_opinion_cumplimiento': 'Opinión de Cumplimiento',
    'doc_acta_constitutiva': 'Acta Constitutiva', 'doc_estado_cuenta': 'Estado de cuenta bancario', 'doc_repse': 'REPSE',
    'doc_csf_infonavit': 'CSF Infonavit', 'doc_siroc': 'SIROC', 'doc_retencion_isr': 'Comprobantes de Retención de ISR',
    'doc_programa_seguridad': 'Programa de Seguridad y Salud', 'doc_fianzas': 'Fianzas (cumplimiento y vicios ocultos)',
}
TIPOS = {'tipo_suministro': 'Suministro', 'tipo_subcontrato': 'Subcontrato'}


def pre_init_hook(env):
    """Adopta los documentos y tipos de contratista capturados a mano con el mismo nombre, para no duplicarlos al instalar."""
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
