# -*- coding: utf-8 -*-


def migrate(cr, version):
    # Destajistas ya dados de alta: su contacto queda marcado "Es destajista" y su tipo de empleado pasa a Contratista
    cr.execute("""UPDATE res_partner p SET es_destajista = TRUE FROM hr_employee e
                  WHERE e.work_contact_id = p.id AND e.tipo_personal = 'destajista' AND p.es_destajista IS NOT TRUE""")
    cr.execute("UPDATE hr_employee SET employee_type = 'contractor' WHERE tipo_personal = 'destajista' AND employee_type = 'employee'")
