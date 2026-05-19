# -*- coding: utf-8 -*-

# rhino_panel.py
# ──────────────────────────────────────────────────────────────────────────────
# Facade Performance Analyzer — Rhino Dockable Side Panel
#
# HOW TO USE:
#   1. Start the API in terminal:  python api.py
#   2. In Rhino 8, open EditPythonScript
#   3. Open this file and click Run
#   The panel will dock into Rhino's side panel — Rhino stays fully usable.
# ──────────────────────────────────────────────────────────────────────────────

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import Rhino.UI
import Eto.Forms as forms
import Eto.Drawing as drawing
import System
import System.Net
import System.IO
import System.Text
import json


# ── HTTP via .NET (bypasses macOS sandbox) ────────────────────────────────────
def http_post(url, payload):
    try:
        json_str = json.dumps(payload)
        body     = System.Text.Encoding.UTF8.GetBytes(json_str)

        req = System.Net.HttpWebRequest.Create(url)
        req.Method        = "POST"
        req.ContentType   = "application/json"
        req.ContentLength = body.Length

        stream = req.GetRequestStream()
        stream.Write(body, 0, body.Length)
        stream.Close()

        resp   = req.GetResponse()
        reader = System.IO.StreamReader(resp.GetResponseStream())
        result_str = reader.ReadToEnd()
        reader.Close()

        print("STATUS OK")
        print(result_str)

        return json.loads(result_str)

    except System.Net.WebException as e:
        if e.Response:
            reader = System.IO.StreamReader(e.Response.GetResponseStream())
            error_text = reader.ReadToEnd()
            reader.Close()
            print("ERROR RESPONSE:")
            print(error_text)
            raise Exception(error_text)
        else:
            raise


API_BASE = "http://localhost:5001"


def calculate_wwr():
    srfs1 = rs.GetObjects("Select WALL surfaces", rs.filter.surface)
    if not srfs1:
        return None
    srfs2 = rs.GetObjects("Select WINDOW surfaces", rs.filter.surface)
    if not srfs2:
        return None
    area1 = sum(rs.SurfaceArea(srf)[0] for srf in srfs1)
    area2 = sum(rs.SurfaceArea(srf)[0] for srf in srfs2)
    if area1 == 0:
        return None
    return round((area2 / area1) * 100, 2)


# ── Constants ─────────────────────────────────────────────────────────────────
GLASS_PRESETS = {
    "Standard (VLT 0.80)":         {"Glass_VLT": 0.80, "Glass_SHGC": 0.71, "Glass_U": 1.81},
    "High Performance (VLT 0.40)": {"Glass_VLT": 0.40, "Glass_SHGC": 0.28, "Glass_U": 1.26},
}
GEOMETRY_OPTIONS    = ["NoPanel - Bare Facade", "C01 - Circular", "T01 - Triangular", "H01 - Hexagonal"]
GEOMETRY_KEYS       = ["NoPanel", "C01", "T01", "H01"]
ORIENTATION_OPTIONS = ["N - North", "E - East", "S - South", "W - West"]
ORIENTATION_KEYS    = ["N", "E", "S", "W"]

# ── Colors ────────────────────────────────────────────────────────────────────
COLOR_HIGH  = drawing.Color.FromArgb(107, 203, 119)
COLOR_PASS  = drawing.Color.FromArgb(76,  201, 240)
COLOR_FAIL  = drawing.Color.FromArgb(255, 107, 107)
COLOR_WARN  = drawing.Color.FromArgb(255, 217,  61)
COLOR_GREY  = drawing.Color.FromArgb(150, 150, 150)
COLOR_WHITE = drawing.Color.FromArgb(230, 230, 230)
COLOR_DIM   = drawing.Color.FromArgb(100, 100, 100)

# ── Suggestion -> parameter mapping ──────────────────────────────────────────
# NOTE: strings must match predict.py facade_recommendation() exactly (ASCII only)
SUGGESTION_ACTIONS = {
    "Increase WWR to improve daylight access":
        ("WWR", "up"),
    "Increase facade porosity (larger gaps between panels)":
        ("Porosity", "up"),
    "Reduce shading density (smaller panels or less overlap)":
        ("Panel_Size", "down"),
    "Optimize WWR or porosity to reach higher daylight performance (target sDA >= 75%)":
        ("WWR", "up"),
    "Reduce WWR to limit direct solar exposure":
        ("WWR", "down"),
    "Increase shading using larger panels or reduced porosity":
        ("Panel_Size", "up"),
    "Increase panel rotation to block direct sunlight":
        ("Rotation", "up"),
    "Increase daylight by adjusting WWR or porosity":
        ("Porosity", "up"),
    "Reduce daylight using shading strategies (rotation, panel density, or lower WWR)":
        ("Rotation", "up"),
}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class FacadeDialog(forms.Form):
    def __init__(self):
        forms.Form.__init__(self)
        self.Title       = "Facade Analyzer"
        self.ClientSize  = drawing.Size(420, 640)
        self.MinimumSize = drawing.Size(300, 400)

        # State
        self._last_result     = None
        self._last_inputs     = None
        self._history         = []      # list of (name, inputs_dict, result_dict)
        self._suggestion_btns = []
        self._analyzing       = False   # re-entrancy guard

        self.setup_ui()

    # ── UI Construction ───────────────────────────────────────────────────────
    def setup_ui(self):

        # ════════════════════════════════
        # TAB 1 — PARAMETERS
        # ════════════════════════════════
        t1      = forms.TabPage()
        t1.Text = "Parameters"

        p1         = forms.DynamicLayout()
        p1.Padding = drawing.Padding(10)
        p1.Spacing = drawing.Size(4, 8)

        # ── Title ─────────────────────────────────────────────────────────────
        title           = forms.Label()
        title.Text      = "Facade Performance Analyzer"
        title.Font      = drawing.Font(drawing.SystemFont.Bold, 13)
        title.TextColor = COLOR_WHITE
        p1.AddRow(title)

        subtitle           = forms.Label()
        subtitle.Text      = "Rhino ML Tool  |  LEED v4 Daylighting"
        subtitle.TextColor = COLOR_DIM
        p1.AddRow(subtitle)
        p1.AddRow(self._spacer())

        # ── STEP 1: BASE PARAMETERS ───────────────────────────────────────────
        p1.AddRow(self._section("1  BASE PARAMETERS"))

        p1.AddRow(self._label("Window-to-Wall Ratio (WWR)"))
        self.wwr_slider = self._slider(10, 90, 30)
        self.wwr_val    = self._val_label("0.30")
        self.wwr_slider.ValueChanged += self._on_wwr_changed
        p1.AddRow(self._slider_row(self.wwr_slider, self.wwr_val))

        self.wwr_btn       = forms.Button()
        self.wwr_btn.Text  = "Calculate WWR from Model"
        self.wwr_btn.Click += self._on_calculate_wwr
        p1.AddRow(self.wwr_btn)

        p1.AddRow(self._label("Orientation"))
        self.orientation_dd = self._dropdown(ORIENTATION_OPTIONS, 2)
        p1.AddRow(self.orientation_dd)

        p1.AddRow(self._label("Glass Material"))
        self.glass_dd = self._dropdown(list(GLASS_PRESETS.keys()), 0)
        p1.AddRow(self.glass_dd)

        p1.AddRow(self._spacer())

        # ── STEP 2: DOUBLE SKIN FACADE PANEL ──────────────────────────────────
        p1.AddRow(self._section("2  DOUBLE SKIN FACADE PANEL"))

        p1.AddRow(self._label("Panel Type"))
        self.geom_dd = self._dropdown(GEOMETRY_OPTIONS, 0)
        p1.AddRow(self.geom_dd)

        p1.AddRow(self._label("Panel Size (cm)"))
        self.size_dd = self._dropdown(["20 cm - Fine", "40 cm - Medium", "60 cm - Large"], 1)
        p1.AddRow(self.size_dd)

        p1.AddRow(self._label("Porosity  (gap between panels)"))
        self.porosity_slider = self._slider(0, 40, 10)
        self.porosity_val    = self._val_label("0.10")
        self.porosity_slider.ValueChanged += self._on_porosity_changed
        p1.AddRow(self._slider_row(self.porosity_slider, self.porosity_val))

        p1.AddRow(self._label("Panel Rotation (degrees)"))
        self.rotation_slider = self._slider(0, 60, 0)
        self.rotation_val    = self._val_label("0 deg")
        self.rotation_slider.ValueChanged += self._on_rotation_changed
        p1.AddRow(self._slider_row(self.rotation_slider, self.rotation_val))

        p1.AddRow(self._spacer())

        # ── ANALYZE BUTTON ─────────────────────────────────────────────────────
        self.analyze_btn        = forms.Button()
        self.analyze_btn.Text   = "Analyze Facade"
        self.analyze_btn.Click += self._on_analyze
        p1.AddRow(self.analyze_btn)

        self.status_lbl           = forms.Label()
        self.status_lbl.Text      = "Ready - press Analyze to run."
        self.status_lbl.TextColor = COLOR_GREY
        p1.AddRow(self.status_lbl)

        p1.AddRow(self._spacer())

        # Set layout directly as tab content — no Scrollable inside TabPage
        # (Scrollable inside TabPage produces a gap on macOS Eto)
        t1.Content = p1

        # ════════════════════════════════
        # TAB 2 — RESULTS
        # ════════════════════════════════
        t2      = forms.TabPage()
        t2.Text = "Results"

        p2         = forms.DynamicLayout()
        p2.Padding = drawing.Padding(10)
        p2.Spacing = drawing.Size(4, 8)

        # ── STEP 3: PERFORMANCE RESULTS ───────────────────────────────────────
        p2.AddRow(self._section("3  PERFORMANCE RESULTS"))

        self.overall_lbl      = forms.Label()
        self.overall_lbl.Text = "-"
        self.overall_lbl.Font = drawing.Font(drawing.SystemFont.Bold, 12)
        p2.AddRow(self.overall_lbl)

        metrics         = forms.DynamicLayout()
        metrics.Spacing = drawing.Size(10, 4)

        self.sda_val  = forms.Label(); self.sda_val.Text  = "-"
        self.ase_val  = forms.Label(); self.ase_val.Text  = "-"
        self.lux_val  = forms.Label(); self.lux_val.Text  = "-"
        self.rad_val  = forms.Label(); self.rad_val.Text  = "-"
        self.sda_stat = forms.Label(); self.sda_stat.Text = ""
        self.ase_stat = forms.Label(); self.ase_stat.Text = ""
        self.lux_stat = forms.Label(); self.lux_stat.Text = ""

        metrics.AddRow(self._label("sDA  (Daylight Autonomy)"), self.sda_val, self.sda_stat)
        metrics.AddRow(self._label("ASE  (Glare Risk)"),        self.ase_val, self.ase_stat)
        metrics.AddRow(self._label("Lux  (Illuminance)"),       self.lux_val, self.lux_stat)
        metrics.AddRow(self._label("Radiation  (kWh/m2)"),      self.rad_val, forms.Label())
        p2.AddRow(metrics)

        p2.AddRow(self._spacer())

        # ── STEP 4: DESIGN FEEDBACK ───────────────────────────────────────────
        p2.AddRow(self._section("4  DESIGN FEEDBACK AND ACTIONS"))

        self.explain_lbl           = forms.Label()
        self.explain_lbl.Text      = "Run analysis to see feedback."
        self.explain_lbl.TextColor = COLOR_GREY
        p2.AddRow(self.explain_lbl)

        p2.AddRow(self._spacer())
        p2.AddRow(self._label("Suggested Actions (click to apply and re-run):"))

        # StackLayout for suggestion buttons — supports live add/remove correctly
        self.suggestion_panel = forms.StackLayout()
        self.suggestion_panel.Spacing = 5
        self.suggestion_panel.HorizontalContentAlignment = forms.HorizontalAlignment.Stretch
        ph_s           = forms.Label()
        ph_s.Text      = "No suggestions yet."
        ph_s.TextColor = COLOR_DIM
        self.suggestion_panel.Items.Add(ph_s)
        p2.AddRow(self.suggestion_panel)

        p2.AddRow(self._spacer())

        # ── STEP 5: ITERATION HISTORY ─────────────────────────────────────────
        p2.AddRow(self._section("5  ITERATION HISTORY"))
        p2.AddRow(self._label("Click a saved iteration to restore its inputs."))

        # StackLayout for history buttons — supports live add/remove correctly
        self.history_panel = forms.StackLayout()
        self.history_panel.Spacing = 4
        self.history_panel.HorizontalContentAlignment = forms.HorizontalAlignment.Stretch
        ph_h           = forms.Label()
        ph_h.Text      = "No iterations saved yet."
        ph_h.TextColor = COLOR_DIM
        self.history_panel.Items.Add(ph_h)
        p2.AddRow(self.history_panel)

        self.save_btn         = forms.Button()
        self.save_btn.Text    = "Save This Iteration"
        self.save_btn.Enabled = False
        self.save_btn.Click  += self._on_save
        p2.AddRow(self.save_btn)

        p2.AddRow(self._spacer())

        # Set layout directly as tab content — no Scrollable inside TabPage
        t2.Content = p2

        # ── TAB CONTROL ───────────────────────────────────────────────────────
        self.tab_control = forms.TabControl()
        self.tab_control.Pages.Add(t1)
        self.tab_control.Pages.Add(t2)

        # Single outer Scrollable wrapping the whole TabControl.
        # This is the only pattern that works correctly on macOS Eto:
        # Scrollable inside TabPage produces a visual gap and broken scroll.
        outer_scroll                     = forms.Scrollable()
        outer_scroll.Content             = self.tab_control
        outer_scroll.ExpandContentWidth  = True
        outer_scroll.ExpandContentHeight = False
        outer_scroll.Border              = forms.BorderType.None
        self.Content = outer_scroll

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _label(self, text):
        l           = forms.Label()
        l.Text      = text
        l.TextColor = COLOR_GREY
        return l

    def _val_label(self, text):
        l       = forms.Label()
        l.Text  = text
        l.Width = 55
        return l

    def _section(self, text):
        l           = forms.Label()
        l.Text      = text
        l.Font      = drawing.Font(drawing.SystemFont.Bold, 9)
        l.TextColor = COLOR_DIM
        return l

    def _spacer(self):
        l      = forms.Label()
        l.Text = " "
        return l

    def _slider(self, mn, mx, val):
        s          = forms.Slider()
        s.MinValue = mn
        s.MaxValue = mx
        s.Value    = val
        return s

    def _slider_row(self, slider, val_lbl):
        row = forms.DynamicLayout()
        row.AddRow(slider, val_lbl)
        return row

    def _dropdown(self, items, default_index):
        dd = forms.DropDown()
        for item in items:
            dd.Items.Add(item)
        dd.SelectedIndex = default_index
        return dd

    # ── Slider handlers ───────────────────────────────────────────────────────
    def _on_wwr_changed(self, sender, e):
        self.wwr_val.Text = "{:.2f}".format(self.wwr_slider.Value / 100.0)

    def _on_porosity_changed(self, sender, e):
        self.porosity_val.Text = "{:.2f}".format(self.porosity_slider.Value / 100.0)

    def _on_rotation_changed(self, sender, e):
        self.rotation_val.Text = "{} deg".format(self.rotation_slider.Value)

    def _on_calculate_wwr(self, sender, e):
        wwr_value = calculate_wwr()
        if wwr_value is None:
            self.status_lbl.Text      = "WWR calculation cancelled or failed."
            self.status_lbl.TextColor = COLOR_WARN
            return
        self.wwr_slider.Value     = int(wwr_value)
        self.wwr_val.Text         = "{:.2f}".format(wwr_value / 100.0)
        self.status_lbl.Text      = "WWR updated from model: {:.2f}%".format(wwr_value)
        self.status_lbl.TextColor = COLOR_PASS

    # ── Read current UI inputs ────────────────────────────────────────────────
    def _get_inputs(self):
        glass_key = list(GLASS_PRESETS.keys())[self.glass_dd.SelectedIndex]
        payload = {
            "WWR":         self.wwr_slider.Value / 100.0,
            "Orientation": ORIENTATION_KEYS[self.orientation_dd.SelectedIndex],
            "Geometry":    GEOMETRY_KEYS[self.geom_dd.SelectedIndex],
            "Panel_Size":  [20, 40, 60][self.size_dd.SelectedIndex],
            "Porosity":    self.porosity_slider.Value / 100.0,
            "Rotation":    self.rotation_slider.Value,
            # store widget state for restore
            "_orientation_idx": self.orientation_dd.SelectedIndex,
            "_glass_idx":       self.glass_dd.SelectedIndex,
            "_geom_idx":        self.geom_dd.SelectedIndex,
            "_size_idx":        self.size_dd.SelectedIndex,
            "_wwr_slider":      self.wwr_slider.Value,
            "_porosity_slider": self.porosity_slider.Value,
            "_rotation_slider": self.rotation_slider.Value,
        }
        payload.update(GLASS_PRESETS[glass_key])
        return payload

    # ── Restore UI from saved inputs dict ─────────────────────────────────────
    def _restore_inputs(self, saved_inputs):
        self.wwr_slider.Value             = saved_inputs["_wwr_slider"]
        self.porosity_slider.Value        = saved_inputs["_porosity_slider"]
        self.rotation_slider.Value        = saved_inputs["_rotation_slider"]
        self.orientation_dd.SelectedIndex = saved_inputs["_orientation_idx"]
        self.glass_dd.SelectedIndex       = saved_inputs["_glass_idx"]
        self.geom_dd.SelectedIndex        = saved_inputs["_geom_idx"]
        self.size_dd.SelectedIndex        = saved_inputs["_size_idx"]
        self.wwr_val.Text      = "{:.2f}".format(saved_inputs["_wwr_slider"] / 100.0)
        self.porosity_val.Text = "{:.2f}".format(saved_inputs["_porosity_slider"] / 100.0)
        self.rotation_val.Text = "{} deg".format(saved_inputs["_rotation_slider"])

    # ── Analyze ───────────────────────────────────────────────────────────────
    def _on_analyze(self, sender, e):
        if self._analyzing:
            return
        self._analyzing          = True
        self.analyze_btn.Enabled = False
        self.status_lbl.Text      = "Running ML prediction..."
        self.status_lbl.TextColor = COLOR_GREY

        try:
            payload = self._get_inputs()
            result  = http_post(API_BASE + "/predict", payload)
            self._last_result = result
            self._last_inputs = payload
            self._display_results(result)
            self._build_interaction_layer(result)
            self.save_btn.Enabled     = True
            self.status_lbl.Text      = "Analysis complete."
            self.status_lbl.TextColor = COLOR_HIGH
            # Auto-switch to Results tab
            self.tab_control.SelectedIndex = 1

        except Exception as ex:
            self.status_lbl.Text      = "Error: {}".format(str(ex))
            self.status_lbl.TextColor = COLOR_FAIL

        finally:
            self._analyzing          = False
            self.analyze_btn.Enabled = True

    # ── Display metrics ───────────────────────────────────────────────────────
    def _display_results(self, result):
        out     = result["outputs"]
        stat    = result["status"]
        overall = stat["overall"]

        if overall == "HIGH PERFORMANCE":
            self.overall_lbl.Text      = "HIGH PERFORMANCE"
            self.overall_lbl.TextColor = COLOR_HIGH
        elif overall == "COMPLIANT":
            self.overall_lbl.Text      = "COMPLIANT"
            self.overall_lbl.TextColor = COLOR_PASS
        else:
            self.overall_lbl.Text      = "NOT COMPLIANT"
            self.overall_lbl.TextColor = COLOR_FAIL

        self.sda_val.Text = "{}%".format(out["sDA"])
        self.ase_val.Text = "{}%".format(out["ASE"])
        self.lux_val.Text = "{} lx".format(int(out["Lux"]))
        self.rad_val.Text = "{} kWh/m2".format(out["Radiation"])

        def set_stat(lbl, s):
            if s in ("high", "pass", "good"):
                lbl.Text      = "PASS"
                lbl.TextColor = COLOR_HIGH
            elif s == "warning":
                lbl.Text      = "WARNING"
                lbl.TextColor = COLOR_WARN
            else:
                lbl.Text      = "FAIL"
                lbl.TextColor = COLOR_FAIL

        set_stat(self.sda_stat, stat["sDA"])
        set_stat(self.ase_stat, stat["ASE"])
        set_stat(self.lux_stat, stat["Lux"])

    # ── Interaction layer ─────────────────────────────────────────────────────
    def _build_interaction_layer(self, result):
        stat        = result["status"]
        out         = result["outputs"]
        suggestions = result.get("suggestions", [])
        overall     = stat["overall"]

        lines = []
        if stat["sDA"] == "fail":
            lines.append("sDA {}% is below the LEED minimum of 55%.".format(out["sDA"]))
        elif stat["sDA"] == "pass":
            lines.append("sDA {}% meets minimum but is below the 75% target.".format(out["sDA"]))
        else:
            lines.append("sDA {}% - excellent daylight autonomy.".format(out["sDA"]))

        if stat["ASE"] == "fail":
            lines.append("ASE {}% exceeds 10% limit - glare risk.".format(out["ASE"]))
        else:
            lines.append("ASE {}% - glare within acceptable range.".format(out["ASE"]))

        if stat["Lux"] == "warning":
            if out["Lux"] < 300:
                lines.append("Illuminance {} lx is below the 300 lx minimum.".format(int(out["Lux"])))
            else:
                lines.append("Illuminance {} lx exceeds 3000 lx - visual discomfort risk.".format(int(out["Lux"])))

        self.explain_lbl.Text      = "\n".join(lines)
        self.explain_lbl.TextColor = COLOR_WARN if overall != "HIGH PERFORMANCE" else COLOR_HIGH

        # Rebuild suggestion buttons using StackLayout.Items (live-safe)
        self.suggestion_panel.Items.Clear()
        self._suggestion_btns = []

        if not suggestions:
            ok           = forms.Label()
            ok.Text      = "No further improvements needed."
            ok.TextColor = COLOR_HIGH
            self.suggestion_panel.Items.Add(ok)
            return

        for suggestion in suggestions:
            btn        = forms.Button()
            btn.Text   = "Apply: " + suggestion
            btn.Tag    = suggestion
            btn.Click += self._on_suggestion_clicked
            self.suggestion_panel.Items.Add(btn)
            self._suggestion_btns.append(btn)

    def _on_suggestion_clicked(self, sender, e):
        suggestion = sender.Tag
        action     = SUGGESTION_ACTIONS.get(suggestion)

        if action:
            param, direction = action

            if param == "WWR":
                step    = 5 if direction == "up" else -5
                new_val = max(10, min(90, self.wwr_slider.Value + step))
                self.wwr_slider.Value = new_val
                self.wwr_val.Text     = "{:.2f}".format(new_val / 100.0)

            elif param == "Porosity":
                step    = 5 if direction == "up" else -5
                new_val = max(0, min(40, self.porosity_slider.Value + step))
                self.porosity_slider.Value = new_val
                self.porosity_val.Text     = "{:.2f}".format(new_val / 100.0)

            elif param == "Rotation":
                step    = 10 if direction == "up" else -10
                new_val = max(0, min(60, self.rotation_slider.Value + step))
                self.rotation_slider.Value = new_val
                self.rotation_val.Text     = "{} deg".format(new_val)

            elif param == "Panel_Size":
                idx = self.size_dd.SelectedIndex
                if direction == "up" and idx < 2:
                    self.size_dd.SelectedIndex = idx + 1
                elif direction == "down" and idx > 0:
                    self.size_dd.SelectedIndex = idx - 1

        # Switch to Parameters tab so user sees the changed inputs, then re-run
        self.tab_control.SelectedIndex = 0
        self._on_analyze(None, None)

    # ── Save iteration ────────────────────────────────────────────────────────
    def _on_save(self, sender, e):
        if not self._last_result or not self._last_inputs:
            return
        default_name = "Iteration {}".format(len(self._history) + 1)
        self._history.append((default_name, self._last_inputs.copy(), self._last_result))
        self._rebuild_history()
        self.status_lbl.Text      = "Saved: {}".format(default_name)
        self.status_lbl.TextColor = COLOR_PASS

    def _rebuild_history(self):
        # Rebuild history buttons using StackLayout.Items (live-safe)
        self.history_panel.Items.Clear()

        if not self._history:
            ph           = forms.Label()
            ph.Text      = "No iterations saved yet."
            ph.TextColor = COLOR_DIM
            self.history_panel.Items.Add(ph)
            return

        for idx, (name, saved_inputs, result) in enumerate(self._history):
            overall = result["status"]["overall"]
            out     = result["outputs"]

            color = COLOR_HIGH if overall == "HIGH PERFORMANCE" else \
                    COLOR_PASS if overall == "COMPLIANT" else COLOR_FAIL
            icon  = "[HP]" if overall == "HIGH PERFORMANCE" else \
                    "[OK]" if overall == "COMPLIANT" else "[--]"

            btn_text = (
                "{} {}. {}\n"
                "   WWR:{:.0f}%  Orient:{}  Panel:{}  Poros:{:.0f}%  Rot:{}deg\n"
                "   sDA:{}%  ASE:{}%  Lux:{} lx  Rad:{} kWh/m2"
            ).format(
                icon, idx + 1, name,
                saved_inputs["WWR"] * 100,
                saved_inputs["Orientation"],
                saved_inputs["Geometry"],
                saved_inputs["Porosity"] * 100,
                saved_inputs["Rotation"],
                out["sDA"], out["ASE"], int(out["Lux"]), out["Radiation"]
            )

            iter_btn           = forms.Button()
            iter_btn.Text      = btn_text
            iter_btn.TextColor = color
            iter_btn.Tag       = idx
            iter_btn.Click    += self._make_restore_handler(idx)
            self.history_panel.Items.Add(iter_btn)

            # Delta row vs previous iteration
            if idx > 0:
                prev_out  = self._history[idx - 1][2]["outputs"]
                sda_delta = round(out["sDA"]      - prev_out["sDA"],       1)
                ase_delta = round(out["ASE"]      - prev_out["ASE"],       1)
                lux_delta = round(out["Lux"]      - prev_out["Lux"],       0)
                rad_delta = round(out["Radiation"] - prev_out["Radiation"], 1)

                def fmt(val):
                    if val == 0: return "+/-0"
                    sign  = "+" if val > 0 else ""
                    arrow = "(+)" if val > 0 else "(-)"
                    return "{}{}{}".format(sign, val, arrow)

                delta_lbl           = forms.Label()
                delta_lbl.Text      = "   Delta vs prev:  sDA {}  |  ASE {}  |  Lux {}  |  Rad {}".format(
                    fmt(sda_delta), fmt(ase_delta), fmt(lux_delta), fmt(rad_delta)
                )
                delta_lbl.TextColor = COLOR_DIM
                self.history_panel.Items.Add(delta_lbl)

    def _make_restore_handler(self, idx):
        """Returns a click handler that restores iteration[idx] inputs."""
        def handler(sender, e):
            name, saved_inputs, result = self._history[idx]
            self._restore_inputs(saved_inputs)
            self._last_result = result
            self._last_inputs = saved_inputs
            self._display_results(result)
            self._build_interaction_layer(result)
            self.save_btn.Enabled     = True
            self.status_lbl.Text      = "Restored: {}".format(name)
            self.status_lbl.TextColor = COLOR_PASS
        return handler


# ── Launch ────────────────────────────────────────────────────────────────────
def show_dialog():
    dlg       = FacadeDialog()
    dlg.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    dlg.Show()

show_dialog()