# -*- coding: utf-8 -*-
# Pruebas de nómina para PERSONAL DE OFICINA (current_project_name == 'OFICINA').
# Cubre los dos gates añadidos en hr_employee.py:
#   GATE 1 (_preprocess_work_hours_data): oficina NO genera línea OVERTIME.
#   GATE 2 (_compute_amount, rama LEAVE1200): oficina cobra incapacidad al 100% (sin tramo 60%).
# Y guarda no-regresión para OBRA en ambos casos.
#
# Datos verificados contra producción (odoo18_prod, jun-2026):
#   - hr.leave.type enfermedad: 'Incapacidad por enfermedad (IMSS)'
#   - action_approve EXCLUYE domingos (weekday()==6) al generar hr.leave.disease
#   - regla: contador c<3 -> 100%, c>=3 -> 60% (c acumula incapacidades previas encadenadas)
#   - contract types reales: 'Permanent' (oficina, sin obra), 'Obra determinada' (obra)
#   - structure_type: 'Mexico: Employee'; calendario: ref resource.resource_calendar_std
#   - sueldo de oficina vive en daily_wage/hourly_wage (no en wage mensual)

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'office_payroll')
class TestOfficePayroll(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.calendar = env.ref('resource.resource_calendar_std')
        cls.dept = env['hr.department'].create({'name': 'QA DEPTO OFICINA'})
        cls.job = env['hr.job'].create({'name': 'QA PUESTO OFICINA'})
        cls.project = env['project.project'].create({'name': 'QA OBRA PROJECT'})

        cls.struct_type = env['hr.payroll.structure.type'].search(
            [('name', '=', 'Mexico: Employee')], limit=1)
        cls.type_oficina = env['hr.contract.type'].search(
            [('name', '=', 'Permanent')], limit=1)            # oficina: NO lleva obra
        cls.type_obra = env['hr.contract.type'].search(
            [('name', '=', 'Obra determinada')], limit=1)
        cls.status_incap = env['hr.leave.type'].search(
            [('name', '=', 'Incapacidad por enfermedad (IMSS)')], limit=1)

        assert cls.struct_type, "Falta structure_type 'Mexico: Employee'"
        assert cls.type_oficina and cls.type_obra, "Faltan contract types"
        assert cls.status_incap, "Falta hr.leave.type de incapacidad"

        # --- OFICINA: sin hr.employee.obra -> current_project_name == 'OFICINA' ---
        cls.partner_ofi = env['res.partner'].create({
            'name': 'QA OFICINA UNO', 'company_type': 'person',
            'is_employee': True})
        cls.emp_ofi = env['hr.employee'].create({
            'name': 'QA OFICINA UNO', 'legal_name': 'QA OFICINA UNO',
            'work_contact_id': cls.partner_ofi.id, 'encargado_nomina': 'quincenal'})

        # --- OBRA: con hr.employee.obra abierta -> current_project_name == project.name ---
        cls.partner_obr = env['res.partner'].create({
            'name': 'QA OBRA UNO', 'company_type': 'person',
            'is_employee': True})
        cls.emp_obr = env['hr.employee'].create({
            'name': 'QA OBRA UNO', 'legal_name': 'QA OBRA UNO',
            'work_contact_id': cls.partner_obr.id, 'encargado_nomina': 'quincenal'})
        env['hr.employee.obra'].create({
            'employee_id': cls.emp_obr.id, 'project_id': cls.project.id,
            'fecha_inicio': '2026-06-01', 'hourly_wage': 50.0})

        # Forzar recompute del discriminador
        (cls.emp_ofi | cls.emp_obr)._compute_current_project()

        common = {
            'wage_type': 'hourly', 'wage': 0.0, 'schedule_pay': 'semi-monthly',
            'structure_type_id': cls.struct_type.id, 'date_start': '2026-01-01',
            'state': 'open', 'resource_calendar_id': cls.calendar.id,
            'department_id': cls.dept.id, 'job_id': cls.job.id,
            'work_entry_source': 'attendance',
            # Campos l10n_mx requeridos para que el SDI (regla INT_DAY_WAGE_BASE)
            # supere el salario mínimo. Un contrato real de oficina los trae poblados.
            'l10n_mx_holiday_bonus_rate': 10.0, 'l10n_mx_holidays_count': 12.0,
            'l10n_mx_savings_fund': 10.0, 'l10n_mx_schedule_pay': 'monthly'}
        # Sueldo REAL en daily_wage (confirmado: oficina cobra por daily_wage, no wage)
        cls.contract_ofi = env['hr.contract'].create({
            **common, 'name': 'QA Contrato Oficina', 'employee_id': cls.emp_ofi.id,
            'hourly_wage': 75.0, 'daily_wage': 600.0,
            'contract_type_id': cls.type_oficina.id})
        cls.contract_obr = env['hr.contract'].create({
            **common, 'name': 'QA Contrato Obra', 'employee_id': cls.emp_obr.id,
            'hourly_wage': 50.0, 'daily_wage': 400.0,
            'contract_type_id': cls.type_obra.id, 'project_id': cls.project.id})

    # ----------------- helpers -----------------
    def _make_payslip(self, emp, contract, dfrom='2026-06-01', dto='2026-06-15'):
        slip = self.env['hr.payslip'].create({
            'name': 'QA Payslip %s' % emp.name,
            'employee_id': emp.id, 'contract_id': contract.id,
            'date_from': dfrom, 'date_to': dto})
        slip.compute_sheet()
        return slip

    def _wd(self, slip, code):
        return slip.worked_days_line_ids.filtered(lambda l: l.code == code)

    def _att(self, emp, ci, co):
        return self.env['hr.attendance'].create({
            'employee_id': emp.id, 'project_id': self.project.id,
            'check_in': ci, 'check_out': co, 'hourly_wage': 50.0})

    def _incap(self, emp, dfrom, dto):
        """Crea incapacidad por enfermedad, la confirma y aprueba.
        action_approve genera los hr.leave.disease (excluye domingos)."""
        lv = self.env['hr.leave'].create({
            'employee_id': emp.id, 'holiday_status_id': self.status_incap.id,
            'request_date_from': dfrom, 'request_date_to': dto})
        # action_approve exige state == 'confirm' (lo forzamos directo en test)
        lv.write({'state': 'confirm'})
        lv.action_approve()
        return lv

    # ----------------- TESTS -----------------
    def test_discriminador_oficina(self):
        """El empleado sin obra resuelve a OFICINA; el de obra al nombre del proyecto."""
        self.assertEqual(self.emp_ofi.current_project_name, 'OFICINA')
        self.assertNotEqual(self.emp_obr.current_project_name, 'OFICINA')

    def test_block_overtime_office(self):
        """GATE 1 — T2: oficina con jornada larga NO genera línea OVERTIME."""
        # Jornada de un solo día para no disparar el warning de >16h ni cruce de medianoche.
        self._att(self.emp_ofi, '2026-06-03 13:00:00', '2026-06-04 00:00:00')  # 11h, mismo día local
        slip = self._make_payslip(self.emp_ofi, self.contract_ofi)
        self.assertFalse(self._wd(slip, 'OVERTIME'),
                         'Oficina NO debe generar línea OVERTIME')

    def test_overtime_obra_no_regresion(self):
        """GATE 1 — T3 (no-regresión): obra con jornada larga SÍ genera OVERTIME."""
        self._att(self.emp_obr, '2026-06-03 13:00:00', '2026-06-04 00:00:00')
        slip = self._make_payslip(self.emp_obr, self.contract_obr)
        ot = self._wd(slip, 'OVERTIME')
        self.assertTrue(ot, 'Obra debe conservar la línea OVERTIME')

    def test_incapacity_100_office(self):
        """GATE 2 — T4: incapacidad 4 días hábiles en oficina = 100% real.
        Lun 1 a Jue 4 jun 2026 (sin domingo) -> 4 hr.leave.disease, todos 100% por el gate."""
        self._incap(self.emp_ofi, '2026-06-01', '2026-06-04')
        dis = self.env['hr.leave.disease'].search([('employee_id', '=', self.emp_ofi.id)])
        # action_approve generó 4 (sin domingo en el rango): días 1-3 a 100, día 4 a 60
        self.assertEqual(len(dis), 4, 'Deben generarse 4 incapacidades (sin domingo)')
        slip = self._make_payslip(self.emp_ofi, self.contract_ofi)
        incap = self._wd(slip, 'LEAVE1200')
        self.assertTrue(incap, 'Debe existir línea LEAVE1200')
        # Gate: oficina paga TODOS los días al 100% -> daily_wage * 4
        self.assertAlmostEqual(incap.amount, 600.0 * 4, places=2,
                               msg='Oficina debe cobrar incapacidad 100% (4 días)')

    def test_incapacity_split_obra_no_regresion(self):
        """GATE 2 — T5 (no-regresión): incapacidad 4 días hábiles en obra = 3@100% + 1@60%."""
        self._incap(self.emp_obr, '2026-06-01', '2026-06-04')
        dis = self.env['hr.leave.disease'].search([('employee_id', '=', self.emp_obr.id)])
        self.assertEqual(len(dis.filtered(lambda d: d.percentage == 100)), 3,
                         'Obra: primeros 3 días al 100%')
        self.assertEqual(len(dis.filtered(lambda d: d.percentage == 60)), 1,
                         'Obra: día 4 al 60%')
        slip = self._make_payslip(self.emp_obr, self.contract_obr)
        incap = self._wd(slip, 'LEAVE1200')
        # daily_wage=400 -> 400*3 (100%) + 400*1*0.6 (60%) = 1200 + 240 = 1440
        self.assertAlmostEqual(incap.amount, 400.0 * 3 + 400.0 * 1 * 0.6, places=2,
                               msg='Obra debe mantener el split 100/60')

    def test_incapacity_3days_equivalence(self):
        """GATE 2 — T6: 3 días hábiles -> oficina y obra cobran igual (sin tramo 60%)."""
        # Mar 2 a Jue 4 jun 2026 (3 días, sin domingo) -> los 3 a 100% en ambos casos
        self._incap(self.emp_ofi, '2026-06-02', '2026-06-04')
        dis = self.env['hr.leave.disease'].search([('employee_id', '=', self.emp_ofi.id)])
        self.assertEqual(len(dis), 3)
        self.assertTrue(all(d.percentage == 100 for d in dis),
                        '<=3 días: todos al 100% incluso sin el gate')
        slip = self._make_payslip(self.emp_ofi, self.contract_ofi)
        incap = self._wd(slip, 'LEAVE1200')
        self.assertAlmostEqual(incap.amount, 600.0 * 3, places=2)

    def test_sdi_below_minimum_rejected(self):
        """T9: la regla MX INT_DAY_WAGE_BASE rechaza un SDI por debajo del mínimo.
        Con daily_wage=0 el SDI cae bajo el mínimo diario -> UserError esperado."""
        from odoo.exceptions import UserError
        self.contract_ofi.write({'hourly_wage': 0.0, 'daily_wage': 0.0})
        with self.assertRaises(UserError):
            self._make_payslip(self.emp_ofi, self.contract_ofi)
