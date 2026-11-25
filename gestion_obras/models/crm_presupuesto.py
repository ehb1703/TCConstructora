# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
import base64
import io
import openpyxl
import json

_logger = logging.getLogger(__name__)


class crmLeadPresupuesto(models.Model):
    _inherit = 'crm.lead'

    base_ids = fields.One2many('gestion.obra.presupuesto.base', 'lead_id', string='Presupuesto Base')
    analytic_id = fields.Many2one('account.analytic.account', string='Analítica', readonly=True)

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

            self.generate_preoperativo()

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

            count = len(self.concept_ids.filtered(lambda u: not u.concept_ex))
            if count != 0:
                raise ValidationError('Existen conceptos sin cargar, revise la información.')

            """count = len(self.concept_ids.filtered(lambda u: not u.account_ex))
            if count != 1:
                raise ValidationError('Existen conceptos sin información contable, revise la información.')"""

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
        if new_stage.name == 'Inscripción/Compra de bases':
            if not self.analytic_id:
                plan = self.env['account.analytic.plan'].search([], order='id asc', limit=1)
                analitica = self.env['account.analytic.account'].create({'name': self.nombre_interno or self.name, 'plan_id': plan.id})
                self.write({'analytic_id': analitica.id})

        if old_stage_name == 'Junta de Fallo' and self.fallo_ganado:
            if self.origen_id.name == 'Público':
                for rec in self.base_ids:
                    if rec.state != 'authorized':
                        raise ValidationError('No existe presupuesto autorizado para la obra, favor de consultar con el área correspondiente.')
            
            return self.action_set_won_rainbowman()

    def _get_presupuesto_base_from_group(self, grupo):
        emails = set()
        group = self.env.ref(grupo, raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())
        return sorted(e for e in emails if '@' in e)


    def generate_presupuesto(self):
        name = self.env['ir.sequence'].next_by_code('gestion.obra.presupuesto.base')
        presupuesto = self.env['gestion.obra.presupuesto.base'].create({'lead_id': self.id, 'name': name})
        for rec in self.concept_ids:
            rec.write({'base_id': presupuesto.id})
        correos_list = self._get_presupuesto_base_from_group('gestion_obras.group_tc_budget_control')
        template = self.env.ref('gestion_obras.mail_tmpl_presupuesto_base', raise_if_not_found=False)

        if not correos_list:
            raise ValidationError(_('No hay usuarios configurados con permiso para autorizar (o no tienen correo).'))
        if not template:
            raise ValidationError(_('No se encontró la plantilla de correo para solicitud de bases.'))

        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'gestion.obra.presupuesto.base', 'email_to': correos}
            template.send_mail(presupuesto.id, force_send=True, email_values=email_values)
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))

        presupuesto.action_cargar_presupuesto()


    def get_orden_default_values(self, lead=False):
        if not self.partner_id.id:
            raise ValidationError('No se ha capturado información de contacto')

        if not self.origen_id.product_id.id:
            raise ValidationError('Falta configurar el concepto a pagar')

        if not self.env.user.has_group('project_extra.group_conv_authorizer'):
            raise ValidationError('Solo usuarios autorizadores pueden aprobar la compra de bases.')

        if not self.bases_pay:
            raise ValidationError('La licitación no necesita orden de compra')

        if not self.bases_cost or self.bases_cost == 0.00:
            raise ValidationError('Capturar el costo de la requisición.')

        if self.oc_ids.filtered(lambda u: u.state != 'cancel' and u.type_purchase == 'bases'):
            raise ValidationError('Ya existe Orden de pago ligada.')

        self.ensure_one()
        sequence = self.env['ir.sequence'].next_by_code('purchase.order')
        price = self.bases_cost
        
        orders = []
        order_lines = []
        taxes = []
        fpos = self.env['account.fiscal.position'].with_company(self.company_id)._get_fiscal_position(self.partner_id)
        taxes = self.origen_id.product_id.supplier_taxes_id._filter_taxes_by_company(self.company_id)

        name = self.origen_id.product_id.name
        if self.no_licitacion:
            name += ' ' + self.no_licitacion
        origin = 'Base - ' + self.name

        distribution = {self.analytic_id.id: 100}

        order_lines.append((0, 0, {
            'name': name, 'product_uom': self.origen_id.product_id.uom_po_id.id, 'product_id': self.origen_id.product_id.id, 'company_id': self.company_id.id,
            'partner_id': self.partner_id.id, 'currency_id': self.origen_id.product_id.currency_id.id, 'state': 'purchase', 'product_qty': 1, 
            'price_unit': price, 'taxes_id': fpos.map_tax(taxes), 'analytic_distribution': distribution},))
        values = {'lead_id': self.id, 'name': sequence, 'partner_id': self.partner_id.id, 'company_id': self.company_id.id, 'origin': origin,
            'currency_id': self.origen_id.product_id.currency_id.id, 'user_id': self.env.uid, 'state': 'purchase', 'invoice_status': 'no', 
            'type_purchase': 'bases', 'order_line': order_lines}
        orders.append(values)
        return orders


    def generate_preoperativo(self):
        name = self.env['ir.sequence'].next_by_code('gestion.obra.presupuesto.preoperativo')
        presupuesto = self.env['gestion.obra.presupuesto.preoperativo'].create({'lead_id': self.id, 'name': name, 'analytic_id': self.analytic_id.id, 
            'date_start': self.bases_fecha_inicio_trabajos, 'date_expiration': self.bases_fecha_terminacion_trabajos})
        lista = []
        for rec in self.oc_ids.filtered(lambda u: u.type_purchase == 'bases'):
            for line in rec.order_line:
                registro = {'preoperativo_id': presupuesto.id, 'product_id': line.product_id.id, 'analytic_id': self.analytic_id.id, 
                    'name': line.product_id.name, 'amount_budgeted': line.price_total_cc}
                lista.append((0, 0, registro))

        presupuesto.write({'line_ids': lista})
        
        correos_list = self._get_presupuesto_base_from_group('gestion_obras.group_tc_budget_control')
        template = self.env.ref('gestion_obras.mail_tmpl_presupuesto_preoperativo', raise_if_not_found=False)

        if not correos_list:
            raise ValidationError(_('No hay usuarios configurados con permiso para autorizar (o no tienen correo).'))
        if not template:
            raise ValidationError(_('No se encontró la plantilla de correo para solicitud de bases.'))

        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'gestion.obra.presupuesto.preoperativo', 'email_to': correos}
            template.send_mail(presupuesto.id, force_send=True, email_values=email_values)
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))


class gestionPresupuestoBase(models.Model):
    _name = 'gestion.obra.presupuesto.base'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Presupuesto Base'

    lead_id = fields.Many2one('crm.lead', string='Oportunidad', required=True, readonly=True)
    name = fields.Char(string='Nombre', readonly=True)
    presupuesto = fields.Float(string='Prespuesto')
    concept_ids = fields.One2many('crm.concept.line', 'base_id', string='Conceptos de trabajo')
    budget_ids = fields.One2many('crm.budget.line', 'base_id', string='Partidas presupestales')
    partida_ids = fields.One2many('crm.budget.total', 'base_id', string='Todas las partidas')
    baseprep_ids = fields.One2many('gestion.obra.presupuesto.base.partidas', 'base_id', string='Partidas Presupuesto Base')
    line_ids = fields.One2many('gestion.obra.presupuesto.base.line', 'base_id', string='Líneas')
    state = fields.Selection(selection=[('draft','Borrador'), ('authorized','Generado'), ('win','Autorizado'), ('cancel','Cancelado')],
        string='Estatus', default='draft', tracking=True)

    def action_cargar_presupuesto(self):
        registros = []
        total = 0
        for rec in self.concept_ids:
            price = float(rec.col6.replace(',','').replace('$',''))
            total += price
            registro = {'budget_id': rec.concept_id.budget_id.id, 'concept_id': rec.concept_id.id, 'uom_id': rec.concept_id.uom_id.id, 
                'cantidad': rec.col4.replace(',',''), 'price_unit': rec.col5.replace(',','').replace('$',''), 'price': price}
            registros.append((0, 0, registro))

        if self.lead_id.origen_id.name == 'Público':
            state = 'authorized'
        else:
            state = 'win'

        self.write({'line_ids': registros, 'state': state, 'presupuesto': total})
        self.env.cr.execute('SELECT budget_id, sum(price) price FROM gestion_obra_presupuesto_base_line WHERE base_id = ' + str(self.id) + ' GROUP BY 1')
        lineas = self.env.cr.dictfetchall()
        lista = []
        for x in lineas:
            lista.append((0, 0, {'base_id': self.id, 'budget_id': x['budget_id'], 'price': x['price']}))
        self.write({'baseprep_ids': lista})


    def cancelar_presupuesto(self):
        for rec in self.concept_ids:
            rec.write({'lead_id': False})
        for rec in self.budget_ids:
            rec.write({'lead_id': False})
        for rec in self.partida_ids:
            rec.write({'lead_id': False})
        self.write({'state': 'cancel'})

        if self.state in ['authorized', 'win']:
            self.env.cr.execute('DELETE FROM product_budget_item_line WHERE lead_id = ' + str(self.lead_id.id))


class crmConceptLine(models.Model):
    _inherit = 'crm.concept.line'
    
    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)


class crmBudgetTotal(models.Model):
    _inherit = 'crm.budget.total'
    
    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)


class crmBudgetLine(models.Model):
    _inherit = 'crm.budget.line'
    
    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)


class gestionPresupuestoBaseLine(models.Model):
    _name = 'gestion.obra.presupuesto.base.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Líneas Presupuesto Base'

    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)
    budget_id = fields.Many2one(comodel_name='product.budget.item', string='Partida')
    concept_id = fields.Many2one('product.template', string='Conceptos', tracking=True)
    uom_id = fields.Many2one('uom.uom', string='UDM')
    cantidad = fields.Float(string='Cantidad')
    price_unit = fields.Float(string='Precio unitario')
    price = fields.Float(string='Precio')


class gestionPresupuestoBasePartidas(models.Model):
    _name = 'gestion.obra.presupuesto.base.partidas'
    _description = 'Líneas Partidas Presupuesto Base'

    base_id = fields.Many2one(comodel_name='gestion.obra.presupuesto.base', string='Presupuesto Base', readonly=True)
    budget_id = fields.Many2one(comodel_name='product.budget.item', string='Partida')
    price = fields.Float(string='Precio')
    name_lead = fields.Char(string='Nombre de la partida', compute='_compute_name_lead')

    @api.depends('base_id.lead_id', 'budget_id.line_ids.lead_id', 'budget_id.line_ids.name')
    def _compute_name_lead(self):
        for record in self:
            nombre = False
            if record.base_id.lead_id and record.budget_id:
                linea = record.budget_id.line_ids.filtered(lambda l: l.lead_id == record.base_id.lead_id and l.item_id == record.budget_id)[:1]
                nombre = linea.name if linea else False

            record.name_lead = nombre


class gestionPresupuestoPreoperativo(models.Model):
    _name = 'gestion.obra.presupuesto.preoperativo'
    _description = 'Presupuesto Preoperativo'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Folio Preoperativo', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'))
    lead_id = fields.Many2one('crm.lead', string='Oportunidad', tracking=True)
    project_id = fields.Many2one('project.project', string='Proyecto / Obra', tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Responsable / Residente', default=lambda self: self.env.user, tracking=True)
    date_start = fields.Date(string='Fecha de Apertura', default=fields.Date.today, required=True)
    date_expiration = fields.Date(string='Fecha Límite', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('gestion.obra.presupuesto.preoperativo.line', 'preoperativo_id', string='Líneas Directas')
    indirect_ids = fields.One2many('gestion.obra.presupuesto.preoperativo.indirecto', 'preoperativo_id', string='Líneas Indirectas')
    gastos = fields.Float(string='Gastos autorizados')
    amount_total_budget = fields.Float(string='Monto Total Presupuestado', compute='_compute_totals', store=True)
    amount_total_available = fields.Float(string='Saldo Total Disponible', compute='_compute_totals', store=True)
    """amount_total_committed = fields.Float(string='Monto Total Comprometido', compute='_compute_totals', store=True)
    amount_total_incurred = fields.Float(string='Monto Total Incurrido', compute='_compute_totals', store=True) """
    analytic_id = fields.Many2one('account.analytic.account', string='Analítica', readonly=True)
    state = fields.Selection([('draft', 'Borrador'), ('approved', 'Autorizado'), ('transferring', 'En Traslado'), ('reconciled', 'Conciliado / Cerrado'),
        ('cancel', 'Cancelado')], 
        string='Estatus', default='draft', tracking=True)

    _sql_constraints = [('leadprep_uniq','unique(lead_id)','Solo debe de exister un presupuesto preoperativo por oportunidad.')]

    @api.onchange('lead_id')
    def onchange_name(self):
        if self.lead_id:
            project = self.env['project.project'].search([('lead_id', '=', self.lead_id.id)])
            self.project_id = project
            self.analytic_id = project.account_id

    @api.depends('gastos', 'line_ids.amount_budgeted') #, 'line_ids.amount_committed', 'line_ids.amount_incurred'
    def _compute_totals(self):
        for rec in self:
            rec.amount_total_budget = sum(rec.line_ids.mapped('amount_budgeted')) + sum(rec.indirect_ids.mapped('amount_budgeted'))
            rec.amount_total_available = rec.gastos - rec.amount_total_budget

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_open_transfer_wizard(self):
        return {
            'name': _('Asistente de Traslado y Compensación'),
            'type': 'ir.actions.act_window',
            'res_model': 'presupuesto.preoperativo.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_preoperative_budget_id': self.id}}


class gestionPresupuestoPreoperativoLine(models.Model):
    _name = 'gestion.obra.presupuesto.preoperativo.line'
    _description = 'Línea de Partida Preoperativa'

    @api.depends('preoperativo_id')
    def _compute_domain_budget(self):
        lista = []
        for record in self:
            if record.preoperativo_id.lead_id.base_ids:
                for rec in record.preoperativo_id.lead_id.base_ids.filtered(lambda u: u.state == 'win'):
                    base = rec

                if base:
                    self.env.cr.execute('SELECT budget_id FROM gestion_obra_presupuesto_base_line WHERE base_id = ' + str(base.id) + ' GROUP BY 1')
                    lineas = self.env.cr.dictfetchall()
                    for x in lineas:
                        lista.append(x['budget_id'])
            record.budget_domain = json.dumps([('id', 'in', lista)])

    preoperativo_id = fields.Many2one('gestion.obra.presupuesto.preoperativo', string='Presupuesto Preoperativo', ondelete='cascade')
    currency_id = fields.Many2one(related='preoperativo_id.currency_id')
    #category_id = fields.Many2one('product.category', string='Categoría de Insumo Global')
    product_id = fields.Many2one('product.product', string='Producto / Insumo Global', required=True)
    analytic_id = fields.Many2one(related='preoperativo_id.analytic_id') 
    budget_id = fields.Many2one(comodel_name='product.budget.item', string='Partida')
    budget_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_budget)
    name = fields.Char(string='Descripción de Trabajos Iniciales', required=True)
    amount_budgeted = fields.Float(string='Monto Presupuestado Autorizado', required=True)
    # Revisar que se necesita para importes se ne
    """amount_committed = fields.Float(string='Monto Comprometido (OC)', compute='_compute_amounts', store=True)
    amount_incurred = fields.Float(string='Monto Real Incurrido', compute='_compute_amounts', store=True)
    amount_available = fields.Float(string='Saldo Disponible Remanente', compute='_compute_amounts', store=True) """
    is_transferred = fields.Boolean(string='Partida Trasladada / Conciliada', default=False)

    """@api.onchange('amount_budgeted')
    def _compute_amounts(self):
        for line in self:
            committed = 0.0
            incurred = 0.0
            if line.analytic_id:
                _logger.warning('Aqui 321..........')
                po_lines = self.env['purchase.order.line'].search([('analytic_distribution', 'like', str(line.analytic_id.id)), 
                    ('order_id.state', 'in', ['purchase', 'done'])])
                committed = sum(po_lines.mapped('price_subtotal'))
            line.amount_committed = committed
            _logger.warning('Aqui 326..........')
            line.amount_incurred = incurred            
            line.amount_available = line.amount_budgeted - line.amount_committed """


class gestionPresupuestoPreoperativoIndirectos(models.Model):
    _name = 'gestion.obra.presupuesto.preoperativo.indirecto'
    _description = 'Línea de Partida Preoperativa'

    @api.depends('preoperativo_id')
    def _compute_domain_budget(self):
        lista = []
        for record in self:
            if record.preoperativo_id.lead_id.base_ids:
                for rec in record.preoperativo_id.lead_id.base_ids.filtered(lambda u: u.state == 'win'):
                    base = rec

                if base:
                    self.env.cr.execute('SELECT budget_id FROM gestion_obra_presupuesto_base_line WHERE base_id = ' + str(base.id) + ' GROUP BY 1')
                    lineas = self.env.cr.dictfetchall()
                    for x in lineas:
                        lista.append(x['budget_id'])
            record.budget_domain = json.dumps([('id', 'in', lista)])

    preoperativo_id = fields.Many2one('gestion.obra.presupuesto.preoperativo', string='Presupuesto Preoperativo', ondelete='cascade')
    currency_id = fields.Many2one(related='preoperativo_id.currency_id')
    product_id = fields.Many2one('product.product', string='Producto / Insumo Global', required=True)
    analytic_id = fields.Many2one(related='preoperativo_id.analytic_id') 
    budget_id = fields.Many2one(comodel_name='product.budget.item', string='Partida')
    budget_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_budget)
    name = fields.Char(string='Descripción de Trabajos Iniciales', required=True)
    amount_budgeted = fields.Float(string='Monto Presupuestado Autorizado', required=True)
    # Revisar que se necesita para importes se ne
    """amount_committed = fields.Float(string='Monto Comprometido (OC)', compute='_compute_amounts', store=True)
    amount_incurred = fields.Float(string='Monto Real Incurrido', compute='_compute_amounts', store=True)
    amount_available = fields.Float(string='Saldo Disponible Remanente', compute='_compute_amounts', store=True) """
    is_transferred = fields.Boolean(string='Partida Trasladada / Conciliada', default=False)

    """@api.onchange('amount_budgeted')
    def _compute_amounts(self):
        for line in self:
            committed = 0.0
            incurred = 0.0
            if line.analytic_id:
                _logger.warning('Aqui 321..........')
                po_lines = self.env['purchase.order.line'].search([('analytic_distribution', 'like', str(line.analytic_id.id)), 
                    ('order_id.state', 'in', ['purchase', 'done'])])
                committed = sum(po_lines.mapped('price_subtotal'))
            line.amount_committed = committed
            _logger.warning('Aqui 326..........')
            line.amount_incurred = incurred            
            line.amount_available = line.amount_budgeted - line.amount_committed """
