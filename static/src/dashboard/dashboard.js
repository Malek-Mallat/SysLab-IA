/** @odoo-module **/
/*
 * Tableau de bord SysLab (composant OWL, Odoo 17).
 * Les chiffres sont calcules cote serveur par syslab.dashboard.get_data() ;
 * chaque carte est cliquable et ouvre la liste filtree correspondante.
 */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class SyslabDashboard extends Component {
    static template = "syslab.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("syslab.dashboard", "get_data", []);
        this.state.loading = false;
    }

    // Ouvre une liste filtree (liste + formulaire, ou kanban pour les demandes)
    open(model, name, domain = [], views = [[false, "list"], [false, "form"]]) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            domain,
            views,
            target: "current",
        });
    }

    openDemandes(name, domain = []) {
        this.open("syslab.demande", name, domain, [
            [false, "list"], [false, "kanban"], [false, "form"],
        ]);
    }

    openResultats(name, domain = []) {
        this.open("syslab.resultat", name, domain);
    }

    openDemande(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "syslab.demande",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

// Enregistre l'action client "syslab_dashboard" (utilisee par ir.actions.client)
registry.category("actions").add("syslab_dashboard", SyslabDashboard);
