# -*- coding: utf-8 -*-
from odoo import api, fields, models
from .seguridad import NIVEL_1, exigir_nivel


class AccountPaymentOrdenacion(models.Model):
    _inherit = 'account.payment'

    # T0120: la ordenación de pagos (pagos a proveedores) es exclusiva del Nivel 1; los cobros a clientes no cambian
    puede_ordenar_pago = fields.Boolean(compute='_compute_puede_ordenar_pago')

    @api.depends_context('uid')
    @api.depends('payment_type')
    def _compute_puede_ordenar_pago(self):
        es_n1 = self.env.su or self.env.user.has_group(NIVEL_1)
        for pago in self:
            pago.puede_ordenar_pago = es_n1 or pago.payment_type != 'outbound'

    def _check_ordenacion_pago(self):
        if any(pago.payment_type == 'outbound' for pago in self):
            exigir_nivel(self.env, NIVEL_1, 'autorizar pagos a proveedores (ordenación de pagos)')

    def action_post(self):
        self._check_ordenacion_pago()
        return super().action_post()

    def action_validate(self):
        self._check_ordenacion_pago()
        return super().action_validate()


class AccountBatchPaymentOrdenacion(models.Model):
    _inherit = 'account.batch.payment'

    puede_ordenar_pago = fields.Boolean(compute='_compute_puede_ordenar_pago')

    @api.depends_context('uid')
    @api.depends('batch_type')
    def _compute_puede_ordenar_pago(self):
        es_n1 = self.env.su or self.env.user.has_group(NIVEL_1)
        for lote in self:
            lote.puede_ordenar_pago = es_n1 or lote.batch_type != 'outbound'

    def validate_batch(self):
        if any(lote.batch_type == 'outbound' for lote in self):
            exigir_nivel(self.env, NIVEL_1, 'validar lotes de pago bancarios')
        return super().validate_batch()
