/** @odoo-module **/
// En las pantallas del módulo Destajistas (contexto mostrar_destajistas) no se ofrece "Solicitar firma" en el engrane:
// no aplica a destajistas. El elemento lo agrega la app Firma si está instalada; se envuelve si existe o cuando se registre.
import { registry } from "@web/core/registry";

const cogMenu = registry.category("cogMenu");
const CLAVE = "sign-request-menu";

function envolver(item) {
    if (!item || item.__sinDestajistas) {
        return;
    }
    const original = item.isDisplayed;
    item.isDisplayed = async (env) => {
        if (env.searchModel?.globalContext?.mostrar_destajistas) {
            return false;
        }
        return original ? original(env) : true;
    };
    item.__sinDestajistas = true;
}

envolver(cogMenu.get(CLAVE, null));
cogMenu.addEventListener("UPDATE", (ev) => {
    if (ev.detail?.key === CLAVE && ev.detail?.operation === "add") {
        envolver(ev.detail.value);
    }
});
