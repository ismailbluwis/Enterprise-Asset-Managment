sap.ui.define([], function () {
    "use strict";

    var BACKEND = "https://asset-intel-srv-smart-eland-qh.cfapps.us10-001.hana.ondemand.com";

    function getAssetId() {
        var m = window.location.hash.match(/Assets\((?:'([^']+)'|([^)]+))\)/);
        return m ? (m[1] || m[2]) : null;
    }

    function parseSection(text, heading) {
        // Try several heading formats the AI might use
        var patterns = [
            // **HEADING**: content  (bold markdown)
            new RegExp("\\*\\*" + heading + "\\*\\*[:\\s]*([\\s\\S]*?)(?=\\n\\*\\*[A-Z]|\\n#+\\s|$)", "i"),
            // ## Heading  (markdown h2/h3)
            new RegExp("#{1,3}\\s*" + heading + "[:\\s]*([\\s\\S]*?)(?=\\n#{1,3}\\s|\\n\\*\\*[A-Z]|$)", "i"),
            // Heading: content  (plain label)
            new RegExp("(?:^|\\n)" + heading + "[:\\s]+([\\s\\S]*?)(?=\\n[A-Z][A-Za-z ]+:|\\n#{1,3}|\\n\\*\\*|$)", "i")
        ];
        for (var i = 0; i < patterns.length; i++) {
            var m = text.match(patterns[i]);
            if (m && m[1].trim()) return m[1].trim();
        }
        return "";
    }

    function showOverlay(assetId) {
        var existing = document.getElementById("_aiOverlay");
        if (existing) existing.remove();

        var overlay = document.createElement("div");
        overlay.id = "_aiOverlay";
        overlay.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:99999;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif;";

        var box = document.createElement("div");
        box.style.cssText = "background:#fff;border-radius:8px;width:65%;max-height:85vh;overflow-y:auto;padding:24px;box-shadow:0 4px 20px rgba(0,0,0,0.4);";
        box.innerHTML =
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">' +
            '<h2 style="margin:0;color:#0854a0;">AI Insights — ' + assetId + '</h2>' +
            '<button onclick="document.getElementById(\'_aiOverlay\').remove()" style="background:#0854a0;color:#fff;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;">Close</button>' +
            '</div>' +
            '<div id="_aiContent" style="color:#555;">Analysing asset data, please wait…</div>';

        overlay.appendChild(box);
        document.body.appendChild(overlay);
        overlay.addEventListener("click", function (e) { if (e.target === overlay) overlay.remove(); });

        fetch(BACKEND + "/asset/askAI", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                assetId: assetId,
                question: "Provide a full health analysis for asset " + assetId
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var text = data.answer || "";
            if (!text) {
                document.getElementById("_aiContent").innerHTML = '<p style="color:#c00;">Backend returned an empty answer. Check the backend logs.</p>';
                return;
            }
            var sections = [
                ["Health Score", "HEALTH SCORE"],
                ["Health Status", "HEALTH STATUS"],
                ["Corrective Actions", "CORRECTIVE ACTIONS"],
                ["Preventive Actions", "PREVENTIVE ACTIONS"],
                ["Financial Summary", "FINANCIAL SUMMARY"]
            ];
            var parsed = sections.map(function (pair) {
                return { title: pair[0], content: parseSection(text, pair[1]) };
            });
            var anyParsed = parsed.some(function (s) { return s.content; });
            var html = "";
            if (!anyParsed) {
                // Show raw response so we can see the format
                html = '<div style="margin-bottom:12px;border:1px solid #e0e0e0;border-radius:6px;padding:14px;">' +
                    '<h3 style="margin:0 0 8px;color:#c00;font-size:14px;">Raw AI Response (section parsing failed — check format)</h3>' +
                    '<p style="margin:0;white-space:pre-wrap;font-size:12px;line-height:1.5;">' + text + "</p>" +
                    "</div>";
            } else {
                parsed.forEach(function (s) {
                    html += '<div style="margin-bottom:12px;border:1px solid #e0e0e0;border-radius:6px;padding:14px;">' +
                        '<h3 style="margin:0 0 8px;color:#0854a0;font-size:14px;">' + s.title + "</h3>" +
                        '<p style="margin:0;white-space:pre-wrap;font-size:13px;line-height:1.5;">' + (s.content || "No data available.") + "</p>" +
                        "</div>";
                });
            }
            document.getElementById("_aiContent").innerHTML = html;
        })
        .catch(function (err) {
            document.getElementById("_aiContent").innerHTML = '<p style="color:red;">Error: ' + err.message + "</p>";
        });
    }

    // Intercept clicks on the "Generate AI Analysis" button or "AI Insights" header action
    document.addEventListener("click", function (e) {
        var el = e.target;
        for (var i = 0; i < 6; i++) {
            if (!el) break;
            var txt = (el.innerText || el.textContent || "").trim();
            if (txt.indexOf("Generate AI Analysis") !== -1 || txt === "AI Insights") {
                var assetId = getAssetId();
                if (assetId) {
                    showOverlay(assetId);
                    e.stopPropagation();
                    e.preventDefault();
                    return;
                }
            }
            el = el.parentElement;
        }
    }, true);

    return {};
});
