# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, _

def update_data(cr):
    cr.execute('''CREATE OR REPLACE FUNCTION public.generar_basicos(integer, integer)
    RETURNS text
    LANGUAGE plpgsql
AS $function$

DECLARE
    lead ALIAS FOR $1;
    usuario ALIAS FOR $2;
    x RECORD;
    y RECORD;
    num INTEGER;
    idcombo INTEGER;
BEGIN   

    FOR x IN (SELECT * FROM crm_basico_relacion cbr WHERE cbr.lead_id = lead
                 AND EXISTS(SELECT * FROM crm_basico_line cbl WHERE cbl.LEAD_ID = cbr.LEAD_ID AND cbr.COL1 = cbl.COL1) AND cbr.COMBO_ID IS NULL) LOOP
        SELECT COUNT(*) INTO num FROM crm_basico_line cbl JOIN crm_basico_relacion cb ON cbl.COL1 = cb.COL1 WHERE cbl.relacion_id = x.ID;
        
        IF num = 0 THEN
            INSERT INTO product_combo (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, NAME)
                 VALUES (usuario, usuario, NOW(), NOW(), x.COL1)
                RETURNING ID INTO idcombo;
            FOR y IN (SELECT cbl.ID, cbl.COL5::FLOAT, cbl.COL6::FLOAT, pp.ID IDPROD 
                        FROM crm_basico_line cbl JOIN crm_input_line cil ON cbl.COL1 = cil.COL1 AND cbl.LEAD_ID = cil.LEAD_ID 
                                                 JOIN product_product pp ON cil.INPUT_ID = pp.PRODUCT_TMPL_ID
                       WHERE cbl.relacion_id = x.ID) LOOP
                INSERT INTO product_combo_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, COMBO_ID, PRODUCT_ID, EXTRA_PRICE, COMBO_QTY)
                     VALUES (usuario, usuario, NOW(), NOW(), idcombo, y.IDPROD, y.COL6, y.COL5);
                UPDATE crm_basico_line SET COMBO_ID = idcombo, COMBO_EX = True WHERE ID = y.ID;
            END LOOP;
            UPDATE crm_basico_relacion SET COMBO_ID = idcombo WHERE id = x.ID;
        END IF;
    END LOOP;

    FOR x IN (SELECT * FROM crm_basico_relacion cbr WHERE cbr.lead_id = lead
                 AND EXISTS(SELECT * FROM crm_basico_line cbl WHERE cbl.LEAD_ID = cbr.LEAD_ID AND cbr.COL1 = cbl.COL1) AND cbr.COMBO_ID IS NULL) LOOP
        INSERT INTO product_combo (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, NAME)
             VALUES (usuario, usuario, NOW(), NOW(), x.COL1)
            RETURNING ID INTO idcombo;
        FOR y IN (SELECT cbl.ID, cbl.COL5::FLOAT, cbl.COL6::FLOAT, pp.ID IDPROD 
                    FROM crm_basico_line cbl JOIN crm_input_line cil ON cbl.COL1 = cil.COL1 AND cbl.LEAD_ID = cil.LEAD_ID 
                                             JOIN product_product pp ON cil.INPUT_ID = pp.PRODUCT_TMPL_ID
                   WHERE cbl.relacion_id = x.ID) LOOP
            INSERT INTO product_combo_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, COMBO_ID, PRODUCT_ID, EXTRA_PRICE, COMBO_QTY)
                 VALUES (usuario, usuario, NOW(), NOW(), idcombo, y.IDPROD, y.COL6, y.COL5);
            UPDATE crm_basico_line SET COMBO_ID = idcombo, COMBO_EX = True WHERE ID = y.ID;
        END LOOP;
        UPDATE crm_basico_relacion SET COMBO_ID = idcombo WHERE id = x.ID;
    END LOOP;

    FOR x IN (SELECT * FROM crm_basico_relacion cbr WHERE cbr.lead_id = lead AND cbr.COMBO_ID IS NULL) LOOP
        INSERT INTO product_combo (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, NAME)
             VALUES (usuario, usuario, NOW(), NOW(), x.COL1)
            RETURNING ID INTO idcombo;
        FOR y in (SELECT cbr.COMBO_ID, cbl.COL5::FLOAT, cbl.COL6::FLOAT FROM crm_basico_line cbl JOIN crm_basico_relacion cbr ON cbl.COL1 = cbr.COL1 
                   WHERE cbl.RELACION_ID = x.ID) LOOP
            INSERT INTO product_combo_line (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, COMBO_ID, COMBOS_ID, COMBO_QTY, PRICE)
                 VALUES (usuario, usuario, NOW(), NOW(), idcombo, y.COMBO_ID, y.COL5, y.COL6);
        END LOOP;

        FOR y IN (SELECT cbl.ID, cbl.COL5::FLOAT, cbl.COL6::FLOAT, pp.ID IDPROD 
                    FROM crm_basico_line cbl JOIN crm_input_line cil ON cbl.COL1 = cil.COL1 AND cbl.LEAD_ID = cil.LEAD_ID 
                                             JOIN product_product pp ON cil.INPUT_ID = pp.PRODUCT_TMPL_ID
                   WHERE cbl.relacion_id = x.ID) LOOP
            INSERT INTO product_combo_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, COMBO_ID, PRODUCT_ID, EXTRA_PRICE, COMBO_QTY)
                 VALUES (usuario, usuario, NOW(), NOW(), idcombo, y.IDPROD, y.COL6, y.COL5);
            UPDATE crm_basico_line SET COMBO_ID = idcombo, COMBO_EX = True WHERE ID = y.ID;
        END LOOP;
        UPDATE crm_basico_relacion SET COMBO_ID = idcombo WHERE id = x.ID;
    END LOOP;
    RETURN 'OK';
END;
    $function$ ; ''')


    cr.execute('''CREATE OR REPLACE FUNCTION public.generar_combos(integer, integer)
    RETURNS text
    LANGUAGE plpgsql
AS $function$

DECLARE
    lead ALIAS FOR $1;
    usuario ALIAS FOR $2;
    x RECORD;
    y RECORD;
    num INTEGER;
    idcombo INTEGER;
BEGIN   
    FOR x IN (SELECT pt.DEFAULT_CODE, ccl.CONCEPT_ID FROM crm_combo_line ccl JOIN product_template pt ON ccl.CONCEPT_ID = pt.ID 
               WHERE ccl.lead_id = lead AND ccl.COMBO_EX IS FALSE GROUP BY 1, 2 ORDER BY 1) LOOP
        INSERT INTO product_combo (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, NAME)
             VALUES (usuario, usuario, NOW(), NOW(), x.DEFAULT_CODE)
            RETURNING ID INTO idcombo;
        -- Basicos
        FOR y in (SELECT cbr.COMBO_ID, ccl.ID, ccl.COL6::FLOAT, ccl.COL7::FLOAT FROM crm_combo_line ccl JOIN crm_basico_relacion cbr ON ccl.COL1 = cbr.COL1 
                   WHERE ccl.CONCEPT_ID = x.CONCEPT_ID) LOOP
            INSERT INTO product_combo_line (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, COMBO_ID, COMBOS_ID, COMBO_QTY, PRICE)
                 VALUES (usuario, usuario, NOW(), NOW(), idcombo, y.COMBO_ID, y.COL6, y.COL7);
            UPDATE crm_combo_line SET COMBO_EX = True WHERE ID = y.ID;
        END LOOP;
        -- Conceptos
        FOR y IN (SELECT ccl.ID, ccl.COL4::FLOAT, ccl.COL6::FLOAT, ccl.COL7::FLOAT, pp.ID IDPROD 
                    FROM crm_combo_line ccl JOIN crm_input_line cil ON ccl.COL1 = cil.COL1 AND ccl.LEAD_ID = cil.LEAD_ID 
                                            JOIN product_product pp ON cil.INPUT_ID = pp.PRODUCT_TMPL_ID
                   WHERE ccl.CONCEPT_ID = x.CONCEPT_ID ) LOOP
            INSERT INTO product_combo_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, COMBO_ID, PRODUCT_ID, EXTRA_PRICE, COMBO_QTY)
                 VALUES (usuario, usuario, NOW(), NOW(), idcombo, y.IDPROD, y.COL7, y.COL6);
            UPDATE crm_combo_line SET COMBO_EX = True WHERE ID = y.ID;
        END LOOP;
        -- Indirectos
        FOR y IN (SELECT ccl.ID, ccl.COL4::FLOAT, ccl.COL6::FLOAT, ccl.COL7::FLOAT, pp.ID IDPROD 
                    FROM crm_combo_line ccl JOIN product_template pt ON (CASE WHEN UPPER(ccl.COL2) LIKE '%INDIRECTO%' THEN 'CI' 
                                                WHEN UPPER(ccl.COL2) LIKE '%FINANCIAMIENTO%' THEN 'CF' WHEN UPPER(ccl.COL2) LIKE '%UTILIDAD%' THEN 'CU' 
                                                ELSE 'CA' END) = pt.DEFAULT_CODE 
                                            JOIN product_product pp ON pt.ID = pp.PRODUCT_TMPL_ID
                   WHERE ccl.COL1 IS NULL AND ccl.CONCEPT_ID = x.CONCEPT_ID ) LOOP
            INSERT INTO product_combo_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, COMBO_ID, PRODUCT_ID, EXTRA_PRICE, COMBO_QTY)
                 VALUES (usuario, usuario, NOW(), NOW(), idcombo, y.IDPROD, y.COL7, y.COL6);
            UPDATE crm_combo_line SET COMBO_EX = True WHERE ID = y.ID;
        END LOOP;
        INSERT INTO product_combo_product_template_rel VALUES (x.CONCEPT_ID, idcombo);
        UPDATE crm_concept_line SET COMBO_EX = True WHERE CONCEPT_ID = x.CONCEPT_ID;
    END LOOP;
    RETURN 'OK';
END;
    $function$ ; ''')


def migrate(cr, version):
    if not version:
        return
    update_data(cr)