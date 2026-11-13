# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class crmLeadPresupuesto(models.Model):
    _inherit = 'crm.lead'

    base_ids = fields.One2many('gestion.obra.presupuesto.base', 'lead_id', string='Presupuesto Base')

    #models_crm
    def action_advance_stage(self):
        if self.stage_name == 'Inscripción/Compra de bases':
            if self.bases_pay:
                if not self.oc_ids.filtered(lambda u: u.state != 'cancel' and u.type_purchase == 'bases'):
                    raise ValidationError('Favor de realizar la orden de compra antes de avanzar la etapa') 
                if not self.bases_doc:
                    raise ValidationError('Falta cargar las Bases correspondientes') 
            else:
                if not self.bases_doc:
                    raise ValidationError('Falta cargar las Bases correspondientes')
            if not self.bases_abstinencia_anticipo and self.bases_anticipo_porcentaje == 0:
                raise ValidationError('Falta agregar el % de anticipo')
            if self.bases_anticipo_porcentaje > 100:
                raise ValidationError('% de anticipo no valido')

        if self.stage_name == 'Visita de Obra':
            if not self.visita_acta:
                raise ValidationError('Falta cargar el Acta de la Visita')

        if self.stage_name == 'Junta de Aclaración de Dudas':
            if self.junta_line_ids:
                for junta in self.junta_line_ids:
                    if junta.asistente_ids and not junta.acta_junta:
                        raise ValidationError('Falta cargar el Acta de la Junta "%s" (Junta de Aclaración de Dudas).'% (junta.descripcion or junta.fecha_hora))

        if self.stage_name == 'Cotización de insumos y trabajos especiales':
            if not self.no_cotizar_insumos:
                if not self.input_ids:
                    raise ValidationError('Falta cargar información de los conceptos de trabajo y/o insumos. '
                                        'Si no es requerido cotizar, marque la casilla "No se necesita cotizar insumos".')

                count = len(self.oc_ids.filtered(lambda u: u.type_purchase == 'ins'))
                if self.input_ids and count == 0:
                    raise ValidationError('No se han creado cotizaciones de insumos. '
                                        'Si no es requerido cotizar, marque la casilla "No se necesita cotizar insumos".')

        if self.stage_name == 'Propuesta Técnica':
            self.check_doctos('tecnica')
            self.check_revisions('tecnica')

        if self.stage_name == 'Propuesta Económica':
            self.check_doctos('economica')
            if not self.pe_revision_ids.filtered(lambda r: r.autorizado):
                raise ValidationError('Debe tener al menos una revisión AUTORIZADA en Propuesta Económica para avanzar de etapa.')
            if not self.pe_presupuesto_autorizado:
                raise ValidationError('Debe AUTORIZAR el presupuesto de la propuesta económica para avanzar de etapa. '
                                    'Capture el Subtotal, marque como Revisado y luego Autorice.')
            if not self.doctoconcept_nombre:
                raise ValidationError('La plantilla del documento de presupuesto debe de ser capturada.')
            self.generate_presupuesto()

        if self.stage_name == 'Junta de Apertura de Propuestas':
            if self.apertura_obligatoria and not self.apertura_acta:
                raise ValidationError('Falta cargar el Acta de la Junta de Apertura de Propuestas.')

        if self.stage_name == 'Junta de Fallo':
            if not self.fallo_acta:
                raise ValidationError('Falta cargar el Acta de Fallo.')
            if not self.fallo_ganado:
                raise ValidationError('Debe marcar la casilla "Ganado" para avanzar a la siguiente etapa. '
                    'Si la licitación no fue ganada, use el botón "Marcar como Perdido".')
            if not self.fallo_notif_directores_manual_sent and not self.fallo_notif_directores_auto_sent:
                raise ValidationError('Debe enviar la notificación a los directores antes de avanzar a etapa Ganado.')

        sequence = self.stage_id.sequence
        reason = self.env['crm.revert.reason'].search([('name','=','Avance')])
        if self.origen_id.name == 'Privado' and not self.with_project:
            new_stage = self.env['crm.stage'].search([('name','=','Ganado')], limit=1, order='sequence')
        else:
            new_stage = self.env['crm.stage'].search([('sequence','>',sequence), ('origen_ids','in',[self.origen_id.id])], limit=1, order='sequence')

        if not new_stage:
            raise ValidationError('Existe un error en el flujo de las etapas, favor de revisar las configuraciones')

        self._log_stage_change(self.stage_id, new_stage, reason.id, 'Avance de etapa')
        self.stage_previous = self.stage_id.name
        old_stage_name = self.stage_name
        self.stage_id = new_stage.id
        if old_stage_name == 'Junta de Fallo' and self.fallo_ganado:
            return self.action_set_won_rainbowman()

    def generate_presupuesto(self):
        _logger.warning('Aqui 94........')
        raise ValidationError('Estoy haciendo pruebas')


class gestionPresupuestoBase(models.Model):
    _name = 'gestion.obra.presupuesto.base'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Presupuesto Base'

    lead_id = fields.Many2one('crm.lead', string='Oportunidad', required=True, readonly=True)
    #name = fields.Char(string='Nombre', compute='_compute_name', readonly=True)
    presupuesto = fields.Float(string='Prespuesto')
    concept_ids = fields.One2many('crm.concept.line', 'base_id', string='Conceptos de trabajo')
    budget_ids = fields.One2many('crm.budget.line', 'base_id', string='Partidas presupestales')
    partida_ids = fields.One2many('crm.budget.total', 'base_id', string='Todas las partidas')
    state = fields.Selection(selection=[('draft','Borrador'), ('authorized','Autorizado'), ('win','Ganado'), ('cancel','Cancelado')],
        string='Estatus', default='activo', tracking=True)

    def action_cargar_concept(self):
        for record in self:
            docto = self.env['documents.document'].search([('id','=',self.lead_id.doctoconcept_nombre.id)])
            if not docto:
                raise ValidationError('El documento no se encuentra cargado en CRM, favor de revisar con el área correspondiente.')

            if docto.file_extension in ['xlsx', 'xls', 'xlsm']:
                record.__leer_carga_concept(docto)
            else:
                raise ValidationError('Seleccione un archivo tipo xlsx, xls, xlsm')


    def __leer_carga_concept(self, docto):
        for record in self:
            attachment = docto.attachment_id.sudo()
            decoded_data = base64.b64decode(attachment.datas)
            workbook = openpyxl.load_workbook(filename=io.BytesIO(decoded_data), data_only=True)
            sheet = workbook.active
            c = 1
            colpart = 2
            registros = [(5, 0, 0)]
            partidas = [(5, 0, 0)]
            for row in sheet.iter_rows(values_only=True):
                row = tuple(c.strip() if isinstance(c, str) else c for c in row)
                if c == 1:
                    c += 1
                else:
                    if c == 2:
                        c += 1
                        if record.lead_id.empresa_concursante_id.name.upper() != row[0].upper():
                            raise ValidationError('La Empresa concursante no coincide con la empresa del archivo.')
                        if record.lead_id.nombre_interno.upper() != row[1].upper():
                            raise ValidationError('La oportunidad no coincide con el archivo. ')
                        if row[4] != None and row[6] == row[8] == row[10] == None:
                            colpart = 4
                        if row[6] != None and row[8] == row[10] == None:
                            colpart = 6
                        if row[8] != None and row[10] == None:
                            colpart = 8
                        if row[10] != None:
                            colpart = 10
                    
                    if row[12] == row[13] == row[14] == row[15] == None:
                        _logger.warning('No se guarda la información')
                    else:
                        registro = {'col1': row[12], 'col2': row[13], 'col3': row[14], 'col4': row[15], 'col5': row[16], 'col6': row[17], 'col8': row[colpart]}
                        registros.append((0, 0, registro))

                        registro = {'level1': row[2], 'desc1': row[3], 'level2': row[4], 'desc2': row[5], 'level3': row[6], 'desc3': row[7], 'level4': row[8], 
                            'desc4': row[9], 'level5': row[10], 'desc5': row[11]}
                        partidas.append((0, 0, registro))

            record.write({'concept_ids': registros, 'partida_ids': partidas})
            
            self.env.cr.execute('DELETE FROM crm_budget_line WHERE base_id = ' + str(record.id) + ''';
                INSERT INTO crm_budget_line (no_char, parent, col1, col2, create_date, write_date, base_id, create_uid, write_uid) 
                    SELECT *, NOW(), NOW(), ''' + str(record.id) + ', ' + str(self.env.user.id) + ', ' + str(self.env.user.id) + 
                    ' FROM (SELECT 1, NULL, level1, desc1 FROM crm_budget_total WHERE lead_id = ''' + str(record.id) + 
                    ' GROUP BY 1, 2, 3, 4 UNION ALL SELECT 2, level1, level2, desc2 FROM crm_budget_total WHERE base_id = ' + str(record.id) + 
                    ' GROUP BY 1, 2, 3, 4 UNION ALL SELECT 3, level2, level3, desc3 FROM crm_budget_total WHERE base_id = ' + str(record.id) + 
                    ' GROUP BY 1, 2, 3, 4 UNION ALL SELECT 4, level3, level4, desc4 FROM crm_budget_total WHERE base_id = ' + str(record.id) + 
                    ' GROUP BY 1, 2, 3, 4 UNION ALL SELECT 5, level4, level5, desc5 FROM crm_budget_total WHERE base_id = ' + str(record.id) + 
                    ' GROUP BY 1, 2, 3, 4) as t1 WHERE level1 IS NOT NULL ORDER BY 1, 2, 3; ')


    def action_genera_partidas(self):
        count = len(self.budget_ids.filtered(lambda u: not u.budget_id))
        if count == 0:
            raise UserError('Las partidas fueron cargadas correctamente, favor de continuar con la carga de conceptos')
        else:
            self.env.cr.execute('SELECT carga_partidas(' + str(self.id) + ', ' + str(self.env.user.id) + ', ' + str(self.empresa_concursante_id.id) + ')')
            partidas = self.env.cr.dictfetchall()

    def action_genera_concept(self):
        count = len(self.budget_ids.filtered(lambda u: not u.budget_id))
        if count != 0:
            raise UserError('Las partidas no han sido cargadas, favor de realizar la carga')

        iva = self.env['account.tax'].search([('amount','=',16), ('type_tax_use','=','sale')])
        # Cuando el archivo NO trae partidas presupuestales (no son necesarias en esta obra), los
        # conceptos se generan igual: se crea/enlaza el product.template con budget_id vacío. Con
        # partidas cargadas el comportamiento es idéntico al anterior (sin regresión).
        sin_partidas = not self.budget_ids
        partida = 0
        encabezados_sin_match = []
        conceptos_huerfanos = 0
        for rec in self.concept_ids.filtered(lambda u: not u.concept_ex):
            partida_id = self.env['crm.budget.line'].search([('lead_id','=',rec.lead_id.id), ('col1','=',rec.col8)])
            if partida_id:
                partida = partida_id.budget_id.id

            if sin_partidas:
                budget_val = False
            else:
                budget_val = partida
            
            concept_id = self.env['product.template'].search([('budget_id','=',budget_val), ('default_code','=',rec.col1)])
            if concept_id:
                """ El producto ya existía (p.ej. de una carga previa): normalizarlo como servicio de obra para que al confirmar la OV genere su tarea. 
                Sin esto, un producto con service_tracking distinto deja el concepto fuera de la obra. """
                norm = {}
                if concept_id.service_tracking != 'task_in_project':
                    norm['service_tracking'] = 'task_in_project'
                if not concept_id.sale_ok:
                    norm['sale_ok'] = True
                if norm:
                    concept_id.write(norm)
                if concept_id.property_account_income_id:
                    rec.write({'concept_ex': True, 'concept_id': concept_id.id, 'account_ex': True})
                else:
                    rec.write({'concept_ex': True, 'concept_id': concept_id.id})
            else:
                statement = ('''SELECT cil.col1 code, cil.col2 name, uu.id uom, pc.id cat, REPLACE(cil.col4, ',', '') qty,
                        (CASE WHEN cil.col5 = '' THEN '0.0' ELSE REPLACE(cil.col5, ',', '') END)::float importe
                    FROM crm_concept_line cil JOIN uom_uom uu ON lower(cil.col3) = lower(uu.name->>'en_US') JOIN product_category pc ON pc.NAME = 'All'
                    WHERE cil.id = ''' + str(rec.id))
                self.env.cr.execute(statement)
                info = self.env.cr.dictfetchall()
                if info:
                    insumo = self.env['product.template'].create({'categ_id': info[0]['cat'], 'uom_id': info[0]['uom'], 'uom_po_id': info[0]['uom'],
                        'type': 'service', 'default_code': info[0]['code'], 'name': info[0]['name'], 'purchase_ok': False, 'sale_ok': True,
                        'taxes_id': [(6, 0, iva.ids)], 'standard_price': info[0]['importe'], 'list_price': info[0]['importe'],
                        'service_tracking': 'task_in_project', 'active': True, 'budget_id': budget_val})
                    rec.write({'concept_ex': True, 'concept_id': insumo.id})

        for rec in self.concept_ids.filtered(lambda u: u.concept_ex):
            if rec.concept_id.property_account_income_id:
                rec.write({'account_ex': True})


class crmConceptLine(models.Model):
    _inherit = 'crm.concept.line'
    
    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)


class crmBudgetTotal(models.Model):
    _inherit = 'crm.budget.total'
    
    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)


class crmBudgetLine(models.Model):
    _inherit = 'crm.budget.line'
    
    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)