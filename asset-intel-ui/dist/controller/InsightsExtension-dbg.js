sap.ui.define([
    "sap/ui/core/mvc/ControllerExtension"
], function (ControllerExtension) {
    "use strict";
    return ControllerExtension.extend("assetintelui.controller.InsightsExtension", {
        override: {
            onInit: function () {
                console.log("InsightsExtension onInit fired");
            }
        }
    });
});
