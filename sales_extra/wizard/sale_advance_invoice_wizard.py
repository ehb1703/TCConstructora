# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import formatLang, frozendict
import logging

_logger = logging.getLogger(__name__)

class SaleAdvanceInvoiceWizard(models.TransientModel):
    _name = 'sale.advance.invoice.wizard'
    _description = 'Wizard para Factura de Anticipo'

    sale_order_id = fields.Many2one('sale.order', string='Orden de Venta', required=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', related='sale_order_id.partner_id', readonly=True)
    amount_total = fields.Monetary(string='Monto Total de la Orden', related='sale_order_id.amount_total', readonly=True)
    currency_id = fields.Many2one('res.currency', related='sale_order_id.currency_id', readonly=True)
    anticipo_porcentaje = fields.Float(string='Porcentaje de Anticipo (%)', readonly=True)
    anticipo_importe_con_iva = fields.Monetary(string='Importe del Anticipo (con IVA)', currency_field='currency_id', readonly=True)
    anticipo_importe_sin_iva = fields.Monetary(string='Importe del Anticipo (sin IVA)', currency_field='currency_id', readonly=True)
    anticipo_iva = fields.Monetary(string='IVA del Anticipo', currency_field='currency_id', readonly=True)
    tiene_anticipo = fields.Boolean(string='Tiene Anticipo', readonly=True)
    contrato_referencia = fields.Char(string='Referencia del Contrato', readonly=True)
    count = fields.Integer(string="Order Count", compute='_compute_count')
    company_id = fields.Many2one(comodel_name='res.company', compute='_compute_company_id', store=True)

    @api.depends('sale_order_id')
    def _compute_count(self):
        for wizard in self:
            wizard.count = len(wizard.sale_order_id)

    @api.depends('sale_order_id')
    def _compute_company_id(self):
        self.company_id = False
        for wizard in self:
            if wizard.count == 1:
                wizard.company_id = wizard.sale_order_id.company_id
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Obtener la orden de venta del contexto
        sale_order_id = self._context.get('active_id')
        if sale_order_id:
            sale_order = self.env['sale.order'].browse(sale_order_id)
            res['sale_order_id'] = sale_order_id
            res['tiene_anticipo'] = False
            res['anticipo_porcentaje'] = 0
            res['anticipo_importe_con_iva'] = 0
            res['anticipo_importe_sin_iva'] = 0
            res['anticipo_iva'] = 0
            
            if sale_order.opportunity_id:
                opp = sale_order.opportunity_id
                contrato_ref = opp.contrato_documento_name or opp.name
                tiene_anticipo = not opp.bases_abstinencia_anticipo and opp.bases_anticipo_porcentaje > 0
                importe_con_iva = opp.importe_anticipo if tiene_anticipo else 0                
                tasa_iva = 0.16
                importe_sin_iva = importe_con_iva / (1 + tasa_iva) if importe_con_iva else 0
                iva = importe_con_iva - importe_sin_iva
                res['tiene_anticipo'] = tiene_anticipo
                res['anticipo_porcentaje'] = opp.bases_anticipo_porcentaje if tiene_anticipo else 0
                res['anticipo_importe_con_iva'] = importe_con_iva
                res['anticipo_importe_sin_iva'] = round(importe_sin_iva, 2)
                res['anticipo_iva'] = round(iva, 2)
                if contrato_ref and '.' in contrato_ref:
                    contrato_ref = contrato_ref.rsplit('.', 1)[0]
                res['contrato_referencia'] = contrato_ref
        return res


    def action_confirm_with_invoice(self):
        # Confirmar orden de venta Y generar factura de anticipo
        self.ensure_one()
        if self.sale_order_id.factura_anticipo_generada:
            raise UserError(_('Ya se generó una factura de anticipo para esta orden.\n Puede verla en el botón "Facturas" de la orden de venta.'))
        
        skip_confirmation = self._context.get('skip_confirmation', False)
        # Si no se debe saltar la confirmación, confirmar la orden
        """if not skip_confirmation and self.sale_order_id.state == 'draft':
            self.sale_order_id.with_context(skip_advance_wizard=True).action_confirm() """
        
        # Generar la factura de anticipo
        if self.tiene_anticipo and self.anticipo_importe_sin_iva > 0:
            invoice = self._create_invoices()
            self.sale_order_id.with_context(skip_advance_wizard=True).action_confirm()
            # return self.sale_order_id.action_view_invoice(invoices=invoice)


    def action_confirm_without_invoice(self):
        # Solo confirmar la orden de venta sin generar factura
        self.ensure_one()
        skip_confirmation = self._context.get('skip_confirmation', False)
        
        if not skip_confirmation and self.sale_order_id.state == 'draft':
            self.sale_order_id.with_context(skip_advance_wizard=True).action_confirm()
        return {'type': 'ir.actions.act_window_close'}


    def _prepare_down_payment_section_values(self, order):
        return {'product_uom_qty': 0.0, 'order_id': order.id, 'display_type': 'line_section', 'is_downpayment': True, 
            'sequence': order.order_line and order.order_line[-1].sequence + 1 or 10,}

    def _prepare_base_downpayment_line_values(self, order):
        self.ensure_one()
        return {'product_uom_qty': 0.0, 'order_id': order.id, 'discount': 0.0, 'is_downpayment': True, 
            'sequence': order.order_line and order.order_line[-1].sequence + 1 or 10,}

    def _prepare_down_payment_lines_values(self, order):
        AccountTax = self.env['account.tax']
        ratio = self.anticipo_porcentaje / 100
        order_lines = order.order_line.filtered(lambda l: not l.display_type and not l.is_downpayment)
        down_payment_values = []
        for line in order_lines:
            base_line_values = line._prepare_base_line_for_taxes_computation(special_mode='total_excluded')
            product_account = line['product_id'].product_tmpl_id.get_product_accounts(fiscal_pos=order.fiscal_position_id)
            account = product_account.get('downpayment') or product_account.get('income')
            AccountTax._add_tax_details_in_base_line(base_line_values, order.company_id)
            tax_details = base_line_values['tax_details']

            taxes = line.tax_id.flatten_taxes_hierarchy()
            fixed_taxes = taxes.filtered(lambda tax: tax.amount_type == 'fixed')
            down_payment_values.append([taxes - fixed_taxes, base_line_values['analytic_distribution'], tax_details['raw_total_excluded_currency'], account,])
            for fixed_tax in fixed_taxes:
                if fixed_tax.price_include:
                    continue

                if fixed_tax.include_base_amount:
                    pct_tax = taxes[list(taxes).index(fixed_tax) + 1:].filtered(lambda t: t.is_base_affected and t.amount_type != 'fixed')
                else:
                    pct_tax = self.env['account.tax']
                down_payment_values.append([pct_tax, base_line_values['analytic_distribution'], base_line_values['quantity'] * fixed_tax.amount, account])

        downpayment_line_map = {}
        analytic_map = {}
        base_downpayment_lines_values = self._prepare_base_downpayment_line_values(order)
        for tax_id, analytic_distribution, price_subtotal, account in down_payment_values:
            grouping_key = frozendict({'tax_id': tuple(sorted(tax_id.ids)), 'account_id': account,})
            downpayment_line_map.setdefault(grouping_key, {**base_downpayment_lines_values, 'tax_id': grouping_key['tax_id'], 'product_uom_qty': 0.0,
                'price_unit': 0.0,})
            downpayment_line_map[grouping_key]['price_unit'] += price_subtotal
            if analytic_distribution:
                analytic_map.setdefault(grouping_key, [])
                analytic_map[grouping_key].append((price_subtotal, analytic_distribution))

        lines_values = []
        accounts = []
        for key, line_vals in downpayment_line_map.items():
            if order.currency_id.is_zero(line_vals['price_unit']):
                continue
            if analytic_map.get(key):
                line_analytic_distribution = {}
                for price_subtotal, account_distribution in analytic_map[key]:
                    for account, distribution in account_distribution.items():
                        line_analytic_distribution.setdefault(account, 0.0)
                        line_analytic_distribution[account] += price_subtotal / line_vals['price_unit'] * distribution
                line_vals['analytic_distribution'] = line_analytic_distribution
            line_vals['price_unit'] = order.currency_id.round(line_vals['price_unit'] * ratio)
            lines_values.append(line_vals)
            accounts.append(key['account_id'])
        return lines_values, accounts

    def _get_down_payment_description(self, order):
        self.ensure_one()
        context = {'lang': order.partner_id.lang}
        name = _("Anticipo del %s%% \n Contrato: %s", formatLang(self.env(context=context), self.anticipo_porcentaje), self.contrato_referencia)
        del context
        return name

    def _prepare_invoice_values(self, order, so_lines, accounts):
        self.ensure_one()
        return {**order._prepare_invoice(),
            'invoice_line_ids': [Command.create(
                line._prepare_invoice_line(name=self._get_down_payment_description(order), quantity=1.0, **({'account_id': account.id} if account else {}),)
                ) for line, account in zip(so_lines, accounts)],}

    def _create_invoices(self):
        self.ensure_one()        
        self.sale_order_id.ensure_one()
        self = self.with_company(self.company_id)
        order = self.sale_order_id
        SaleOrderline = self.env['sale.order.line'].with_context(sale_no_log_for_new_lines=True)
        if not any(line.display_type and line.is_downpayment for line in order.order_line):
            SaleOrderline.create(self._prepare_down_payment_section_values(order))

        values, accounts = self._prepare_down_payment_lines_values(order)
        down_payment_lines = SaleOrderline.create(values)
        invoice = self.env['account.move'].sudo().create(self._prepare_invoice_values(order, down_payment_lines, accounts))
        invoice = invoice.sudo(self.env.su)
        poster = self.env.user._is_internal() and self.env.user.id or SUPERUSER_ID
        invoice.with_user(poster).message_post_with_source('mail.message_origin_link', render_values={'self': invoice, 'origin': order}, 
            subtype_xmlid='mail.mt_note',)
        title = _("Down payment invoice")
        order.with_user(poster).message_post(body=_("%s has been created", invoice._get_html_link(title=title)),)
        return invoice