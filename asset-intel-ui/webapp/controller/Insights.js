sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/Dialog",
    "sap/m/Button",
    "sap/m/VBox",
    "sap/m/Panel",
    "sap/m/Text",
    "sap/m/Title",
    "sap/m/BusyIndicator",
    "sap/m/MessageToast"
], function (Controller, Dialog, Button, VBox, Panel, Text, Title, BusyIndicator, MessageToast) {
    "use strict";
    var BACKEND = "https://asset-intel-srv-smart-eland-qh.cfapps.us10-001.hana.ondemand.com";
    function parseSection(text, heading) {
        var re = new RegExp("\\*\\*" + heading + "\\*\\*[:\\s]*([\\s\\S]*?)(?=\\n\\*\\*[A-Z]|$)", "i");
        var m = text.match(re);
        return m ? m[1].trim() : "";
    }
    function getAssetId(oView) {
        var ctx = oView.getBindingContext();
        if (ctx) return ctx.getProperty("ASSET_ID");
        var m = window.location.hash.match(/Assets\((?:'([^']+)'|([^)]+))\)/);
        return m ? (m[1] || m[2]) : null;
    }
    return Controller.extend("assetintelui.controller.Insights", {
        onLoadAnalysis: function () {
            var assetId = getAssetId(this.getView());
            if (!assetId) { MessageToast.show("Could not determine asset ID."); return; }
            var oBusy = new BusyIndicator({ size: "2rem" });
            var oContent = new VBox({ items: [oBusy] });
            var oDialog = new Dialog({
                title: "AI Insights — " + assetId,
                contentWidth: "60%",
                content: [oContent],
                buttons: [new Button({ text: "Close", press: function () { oDialog.close(); oDialog.destroy(); } })]
            });
            oDialog.open();
            fetch(BACKEND + "/asset/askAI", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ assetId: assetId, question: "Provide a full health analysis for asset " + assetId })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var s = data.answer || "";
                oContent.destroyItems();
                [
                    { title: "Health Score", key: "HEALTH SCORE" },
                    { title: "Health Status", key: "HEALTH STATUS" },
                    { title: "Corrective Actions", key: "CORRECTIVE ACTIONS" },
                    { title: "Preventive Actions", key: "PREVENTIVE ACTIONS" },
                    { title: "Financial Summary", key: "FINANCIAL SUMMARY" }
                ].forEach(function (item) {
                    oContent.addItem(new Panel({
                        headerText: item.title,
                        expandable: false,
                        content: [new Text({ text: parseSection(s, item.key) || "No data.", wrapping: true }).addStyleClass("sapUiSmallMargin")]
                    }).addStyleClass("sapUiSmallMarginBottom"));
                });
            })
            .catch(function (err) {
                oContent.destroyItems();
                oContent.addItem(new Text({ text: "Error: " + err.message }));
            });
        },
        onAskAI: function () {
            var oView = this.getView();
            var assetId = getAssetId(oView);
            if (!assetId) { MessageToast.show("Could not determine asset ID."); return; }
            var sQuestion = oView.byId("questionInput").getValue();
            if (!sQuestion.trim()) { MessageToast.show("Please enter a question."); return; }
            var oBusy = oView.byId("busyIndicator");
            var oPanel = oView.byId("answerPanel");
            var oText = oView.byId("answerText");
            oBusy.setVisible(true);
            oPanel.setVisible(false);
            fetch(BACKEND + "/asset/askAI", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ assetId: assetId, question: sQuestion })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                oBusy.setVisible(false);
                oText.setText(data.answer || "No response.");
                oPanel.setVisible(true);
            })
            .catch(function (err) {
                oBusy.setVisible(false);
                oText.setText("Error: " + err.message);
                oPanel.setVisible(true);
            });
        }
    });
});
