# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, _

def update_data(cr):
    cr.execute('''CREATE OR REPLACE FUNCTION public.carga_partidas(integer, integer, integer)
 RETURNS text
 LANGUAGE plpgsql
AS $function$

DECLARE    
    
    lead ALIAS FOR $1;
    usuario ALIAS FOR $2;
    company ALIAS FOR $3;
    x RECORD;
    y RECORD;
    counter INTEGER = 1;
    i INTEGER;
    idpart INTEGER;
    item INTEGER;
   
BEGIN
    FOR x IN (SELECT cbl.*, COALESCE(pbi.ID, 0) IDBUD FROM crm_budget_line cbl LEFT JOIN product_budget_item pbi ON cbl.COL1 = pbi.CODE 
               WHERE cbl.LEAD_ID = lead AND cbl.PARENT IS NULL) LOOP
        IF x.IDBUD = 0 THEN
            INSERT INTO product_budget_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, LEVEL, CODE, NAME, ACTIVE)
                VALUES (usuario, usuario, NOW(), NOW(), x.NO_CHAR, x.COL1, x.COL2, True)
            RETURNING ID INTO idpart;
        ELSE
            idpart = x.IDBUD;
        END IF;

        INSERT INTO product_budget_item_line (ITEM_ID, COMPANY_ID, LEAD_ID, CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, NAME)
             VALUES (idpart, company, lead, usuario, usuario, NOW(), NOW(), x.COL2);
        UPDATE crm_budget_line SET BUDGET_ID = idpart WHERE ID = x.ID;
    END LOOP;

    SELECT MAX(NO_CHAR) INTO i FROM crm_budget_line WHERE LEAD_ID = lead;
    WHILE counter < i LOOP
        FOR x IN (SELECT * FROM crm_budget_line WHERE lead_id = lead AND no_char = counter) LOOP
            FOR y IN (SELECT cbl.*, COALESCE(pbi.ID, 0) IDBUD FROM crm_budget_line cbl LEFT JOIN product_budget_item pbi ON cbl.COL1 = pbi.CODE 
                       WHERE cbl.LEAD_ID = x.LEAD_ID AND cbl.PARENT = x.COL1) LOOP
                IF y.IDBUD = 0 THEN
                    INSERT INTO product_budget_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, LEVEL, CODE, NAME, PARENT_ID, ACTIVE)
                        VALUES (usuario, usuario, NOW(), NOW(), y.NO_CHAR, y.COL1, y.COL2, x.BUDGET_ID, True)
                    RETURNING ID INTO idpart;
                ELSE
                    idpart = y.IDBUD;
                END IF;
                SELECT COUNT(*) INTO item FROM product_budget_item_line WHERE LEAD_ID = lead AND COMPANY_ID = company;
                IF item = 0 THEN
                    INSERT INTO product_budget_item_line (ITEM_ID, COMPANY_ID, LEAD_ID, CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, NAME)
                        VALUES (idpart, company, lead, usuario, usuario, NOW(), NOW(), y.COL2);
                END IF;
                UPDATE crm_budget_line SET BUDGET_ID = idpart where ID = y.ID;
            END LOOP;
        END LOOP;
        counter = counter + 1;
    END LOOP;
     
    RETURN 'OK';
END;
    $function$ ;   ''')

    cr.execute('''INSERT INTO project_blocks (create_uid, write_uid, create_date, write_date, active, block_id)
SELECT create_uid, write_uid, now(), now(), true, id from project_bloque pb;

UPDATE project_project pp SET block_id = t1.id
  FROM (SELECT pp.id clid, pb1.id 
          FROM project_bloque pb JOIN crm_lead cl ON pb.id = cl.bloque_id 
                                 JOIN project_project pp ON cl.id = pp.lead_id JOIN project_blocks pb1 ON pb.id = pb1.id) as t1
 WHERE pp.id = t1.clid; ''')


def migrate(cr, version):
    if not version:
        return
    update_data(cr)
