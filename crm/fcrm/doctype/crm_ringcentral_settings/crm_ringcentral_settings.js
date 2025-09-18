// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt


frappe.ui.form.on("CRM RingCentral Settings", {
    refresh(frm) {
      if (frm.doc.enabled) {
        frm.add_custom_button(__("Connect to RingCentral"), function () {
          frappe.call({
            method: 'crm.integrations.ringcentral.ringcentral_handler.RingCentralHandler.get_authorize_url',
            callback: function (r) {
              if (r.message) {
                window.open(r.message, "_blank");
              }
            }
          });
        });
      }
    }
  });
  