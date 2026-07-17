/*
 * pystrider live playgrounds — run the real engine in the browser (Pyodide, no server).
 *
 * Two directions, both powered by demos/playground/web_api.py running under Pyodide:
 *   - GENERATE   : edit the CNL, turn the knobs -> the derived decisions + the EMITTED Textual source.
 *   - UNDERSTAND : paste Python -> the value-building aspects each loop statement has, + what it assigns.
 *
 * On first Run we load Pyodide once, micropip-install the ugm + pystrider wheels (built in CI from the
 * two repos), fetch brew.py + web_api.py onto the virtual FS, and import web_api. Everything after is a
 * direct call into the same functions verified under CPython. Document-level event delegation keeps this
 * working under Material's navigation.instant page swaps.
 */
(function () {
  "use strict";

  var PYODIDE_VERSION = "0.26.4";
  var PYODIDE_BASE = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";

  // The library port (textual + bridge) is fixed context; the GENERATE page lets you edit the
  // *decisions* (business + ux). These defaults are the demos/playground/*.cnl blocks, verbatim.
  var TEXTUAL_CNL = [
    "modal_confirm supported_by textual",
    "styled_label  supported_by textual",
    "input_value   supported_by textual",
    "button_widget supported_by textual",
  ].join("\n");

  var BRIDGE_CNL = [
    "confirmation_step    realized_by modal_confirm",
    "highlighted_discount realized_by styled_label",
    "?feat admitted_for ?cart when ?cart requires_feature ?feat and ?feat realized_by ?cap and ?cap supported_by textual",
  ].join("\n");

  var enginePromise = null; // shared across every playground on the page

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = function () { reject(new Error("Could not load " + src)); };
      document.head.appendChild(s);
    });
  }

  function abs(rel) {
    return new URL(rel, document.baseURI).href;
  }

  // Load Pyodide once, install the wheels, put the two .py modules on the FS, import web_api.
  function getEngine(onProgress) {
    if (enginePromise) return enginePromise;
    enginePromise = (async function () {
      onProgress("Waking the engine (downloading Pyodide, one-time)…");
      await loadScript(PYODIDE_BASE + "pyodide.js");
      var pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });

      onProgress("Loading the reasoning engine (ugm + pystrider)…");
      await pyodide.loadPackage("micropip");
      var micropip = pyodide.pyimport("micropip");

      // The wheel filenames (versioned) are listed in a manifest CI writes next to them. Install the
      // whole set in one call so pystrider's dependency on ugm resolves from the provided wheel, never
      // a PyPI lookup (ugm is not published to PyPI).
      var manifest = await (await fetch(abs("wheels/manifest.json"))).json();
      var urls = manifest.map(function (n) { return abs("wheels/" + n); });
      await micropip.install(urls);

      onProgress("Loading the playground…");
      var brewSrc = await (await fetch(abs("play/brew.py"))).text();
      var apiSrc = await (await fetch(abs("play/web_api.py"))).text();
      pyodide.FS.mkdirTree("/play");
      pyodide.FS.writeFile("/play/brew.py", brewSrc);
      pyodide.FS.writeFile("/play/web_api.py", apiSrc);
      pyodide.runPython("import sys; sys.path.insert(0, '/play')");
      var api = pyodide.pyimport("web_api");
      return { pyodide: pyodide, api: api };
    })().catch(function (err) {
      enginePromise = null; // allow retry on a later click
      throw err;
    });
    return enginePromise;
  }

  // --- small DOM helpers ---------------------------------------------------

  function q(container, sel) { return container.querySelector(sel); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function chips(host, label, items, cls) {
    var row = el("div", "ps-row");
    row.appendChild(el("span", "ps-label", label));
    if (!items.length) {
      row.appendChild(el("span", "ps-chip ps-chip-empty", "—"));
    } else {
      items.forEach(function (t) { row.appendChild(el("span", "ps-chip " + (cls || ""), t)); });
    }
    host.appendChild(row);
  }

  // --- render the two result shapes ---------------------------------------

  function renderGenerate(host, r) {
    host.innerHTML = "";
    if (r.error) { host.appendChild(el("div", "ps-error", r.error)); return; }
    chips(host, "grants discount", [r.granted ? "yes (" + r.rate + "% off)" : "no"], r.granted ? "ps-yes" : "ps-no");
    chips(host, "admitted features", r.features, "ps-feat");
    chips(host, "screen shape", [r.screen], "ps-screen");
    if (r.why && r.why.length) {
      var w = el("details", "ps-why");
      w.appendChild(el("summary", null, "why the discount is a benefit the UI must show"));
      w.appendChild(el("pre", "ps-whytrace", r.why.join("\n")));
      host.appendChild(w);
    }
    host.appendChild(el("div", "ps-out-title", "Generated Textual app (" + r.source.split("\n").length + " lines) — verified by driving it:"));
    var pre = el("pre", "ps-code");
    var code = el("code", "language-python");
    code.textContent = r.source;
    pre.appendChild(code);
    host.appendChild(pre);
  }

  function renderUnderstand(host, r) {
    host.innerHTML = "";
    if (r.error) { host.appendChild(el("div", "ps-error", r.error)); return; }
    var summary = r.total
      ? r.recognized + " of " + r.total + " loop statements are nameable value-aspects" +
        (r.guarded ? " (" + r.guarded + " under a guard)" : "")
      : "no loops found — nothing to recognize";
    host.appendChild(el("div", "ps-out-title", summary));
    chips(host, "loops", [String(r.loops)], "ps-screen");
    chips(host, "assigns", r.assigned, "ps-feat");
    chips(host, "value aspects (proven)", r.value_aspects, "ps-yes");
    chips(host, "residual (honest, not guessed)", r.residual, "ps-no");
  }

  // --- run ----------------------------------------------------------------

  async function run(container) {
    var mode = container.getAttribute("data-mode");
    var out = q(container, ".ps-out");
    var button = q(container, ".ps-run");
    button.disabled = true;
    out.innerHTML = "";
    var status = el("div", "ps-status", "Thinking…");
    out.appendChild(status);

    try {
      var eng = await getEngine(function (m) { status.textContent = m; });
      var json;
      if (mode === "understand") {
        json = eng.api.understand(q(container, ".ps-code").value);
      } else {
        var tier = q(container, ".ps-tier").value;
        var spend = parseFloat(q(container, ".ps-spend").value || "0");
        var irrev = q(container, ".ps-irrev").checked;
        json = eng.api.generate(
          q(container, ".ps-business").value, q(container, ".ps-ux").value,
          TEXTUAL_CNL, BRIDGE_CNL, tier, spend, irrev
        );
      }
      var r = JSON.parse(json);
      if (mode === "understand") renderUnderstand(out, r);
      else renderGenerate(out, r);
    } catch (err) {
      out.innerHTML = "";
      out.appendChild(el("div", "ps-error",
        "Something went wrong starting the engine: " + (err && err.message ? err.message : err) +
        " — check your connection and press Run to try again."));
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!(t instanceof Element)) return;
    var btn = t.closest(".ps-run");
    if (btn) {
      var c = btn.closest(".ps-playground");
      if (c) run(c);
    }
  });
})();
