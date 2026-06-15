sap.ui.define([], function () {
    "use strict";
    var BACKEND = "https://asset-intel-srv-smart-eland-qh.cfapps.us10-001.hana.ondemand.com";
    function parseSection(text, heading) {
        var re = new RegExp("\\*\\*" + heading + "\\*\\*[:\\s]*([\\s\\S]*?)(?=\\n\\*\\*[A-Z]|$)", "i");
        var m = text.match(re);
        return m ? m[1].trim() : "";
    }
    function getAssetId() {
        var m = window.location.hash.match(/Assets\((?:'([^']+)'|([^)]+))\)/);
        return m ? (m[1] || m[2]) : null;
    }
    return {
        run: function (oEvent) {
            console.log("InsightsHandler.run called");
            var oButton = oEvent.getSource();
            var sAssetId = getAssetId();
            if (!sAssetId) { sap.m.MessageToast.show("Navigate to an asset first."); return; }
            var oHBox = oButton.getParent();
            var oMainVBox = oHBox.getParent();
            var oBusy = oHBox.getItems()[1];
            var oResults = oMainVBox.getItems()[1];
            oButton.setEnabled(false);
            if (oBusy) oBusy.setVisible(true);
            if (oResults) oResults.setVisible(false);
            fetch(BACKEND + "/asset/askAI", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ assetId: sAssetId, question: "Provide a full health analysis for asset " + sAssetId })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                oButton.setEnabled(true);
                if (oBusy) oBusy.setVisible(false);
                var s = data.answer || "";
                function getText(i) { return oResults.getItems()[i].getContent()[0]; }
                getText(0).setText(parseSection(s, "HEALTH SCORE") || "No data.");
                getText(1).setText(parseSection(s, "HEALTH STATUS") || "No data.");
                getText(2).setText(parseSection(s, "CORRECTIVE ACTIONS") || "No data.");
                getText(3).setText(parseSection(s, "PREVENTIVE ACTIONS") || "No data.");
                getText(4).setText(parseSection(s, "FINANCIAL SUMMARY") || "No data.");
                if (oResults) oResults.setVisible(true);
            })
            .catch(function (err) {
                oButton.setEnabled(true);
                if (oBusy) oBusy.setVisible(false);
                sap.m.MessageToast.show("Error: " + err.message);
            });
        }
    };
});
