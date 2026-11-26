# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectTaskPartida(models.Model):
    _inherit = 'project.task'

    # T0110: cada tarea (partida de la obra) lleva su subcuenta analítica; las horas que se registran en ella la toman sola
    frente_account_id = fields.Many2one('account.analytic.account', string='Frente (N2)', tracking=True, index='btree_not_null',
        compute='_compute_frente_account_id', store=True, readonly=False, recursive=True,
        domain=lambda self: [('root_plan_id', '=', self.env.ref('gestion_obras.plan_n2_frente', raise_if_not_found=False).id or 0)])
    partida_account_id = fields.Many2one('account.analytic.account', string='Partida (N3)', tracking=True, index='btree_not_null',
        compute='_compute_partida_account_id', store=True, readonly=False, recursive=True,
        domain=lambda self: [('root_plan_id', '=', self.env.ref('gestion_obras.plan_n3_partida', raise_if_not_found=False).id or 0)])

    # La subtarea hereda el frente y la partida de su tarea padre mientras no se le asignen otros.
    # Un cómputo por campo: si compartieran método, dar uno al crear dejaría sin calcular el otro.
    @api.depends('parent_id.frente_account_id')
    def _compute_frente_account_id(self):
        for task in self:
            task.frente_account_id = task.frente_account_id or task.parent_id.frente_account_id

    @api.depends('parent_id.partida_account_id')
    def _compute_partida_account_id(self):
        for task in self:
            task.partida_account_id = task.partida_account_id or task.parent_id.partida_account_id

    def _cuentas_partida_por_columna(self):
        """ {columna de la línea analítica: id de cuenta} con el frente y la partida de la tarea. """
        self.ensure_one()
        res = {}
        for cuenta in (self.frente_account_id, self.partida_account_id):
            if cuenta:
                res[cuenta.root_plan_id._column_name()] = cuenta.id
        return res

    @api.constrains('frente_account_id', 'partida_account_id', 'company_id')
    def _check_cuentas_partida(self):
        planes = {'frente_account_id': self.env.ref('gestion_obras.plan_n2_frente', raise_if_not_found=False),
                  'partida_account_id': self.env.ref('gestion_obras.plan_n3_partida', raise_if_not_found=False)}
        for task in self:
            for campo, plan in planes.items():
                cuenta = task[campo]
                if not cuenta:
                    continue
                if plan and cuenta.root_plan_id != plan:
                    raise ValidationError(f'La cuenta "{cuenta.display_name}" no pertenece al plan {plan.name} (tarea "{task.name}").')
                if cuenta.company_id and task.company_id and cuenta.company_id != task.company_id:
                    raise ValidationError(f'La cuenta "{cuenta.display_name}" es de otra empresa que la tarea "{task.name}".')

    def write(self, vals):
        res = super().write(vals)
        if 'frente_account_id' in vals or 'partida_account_id' in vals:
            # Las horas aún no validadas de la tarea pasan a la nueva partida; las validadas no se tocan
            lineas = self.env['account.analytic.line'].sudo().search([('task_id', 'in', self.ids), ('project_id', '!=', False)])
            if 'validated' in lineas._fields:
                lineas = lineas.filtered(lambda l: not l.validated)
            for task in self:
                cuentas = task._cuentas_partida_por_columna()
                columnas = {task.env.ref('gestion_obras.plan_n2_frente')._column_name(): False,
                            task.env.ref('gestion_obras.plan_n3_partida')._column_name(): False}
                columnas.update(cuentas)
                lineas_task = lineas.filtered(lambda l: l.task_id == task)
                if lineas_task:
                    lineas_task.write(columnas)
        return res


class AccountAnalyticLinePartida(models.Model):
    _inherit = 'account.analytic.line'

    def _timesheet_preprocess_get_accounts(self, vals):
        # T0110: el frente y la partida de la tarea completan las cuentas que Odoo toma del proyecto
        res = super()._timesheet_preprocess_get_accounts(vals)
        task = self.env['project.task'].sudo().browse(vals.get('task_id'))
        if task:
            for columna, cuenta_id in task._cuentas_partida_por_columna().items():
                if not vals.get(columna):
                    res[columna] = cuenta_id
                    vals.pop(columna, None)
        return res
