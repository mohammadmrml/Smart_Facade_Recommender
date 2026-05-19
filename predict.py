"""
predict.py
----------
Pure ML logic extracted from app.py.
No Streamlit, no UI dependencies.
Can be imported by api.py, tests, or any other script.
"""

import pickle
import os

# ── Load model once at import time ──────────────────────────────────────────
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "facade_model.pkl")
_model = pickle.load(open(_MODEL_PATH, "rb"))

# ── Fixed room / glass constants (same as app.py lines 468–475) ─────────────
# These can be overridden per-call if needed in future,
# but are kept as defaults to match the trained model's assumptions.
DEFAULTS = {
    "Glass_VLT":        0.8,
    "Glass_SHGC":       0.71,
    "Glass_U":          1.81,
    "Panel_Reflectance":0.46,
    "Facade_Distance":  0.7,
    "Room_Depth":       8,
    "Room_Width":       6,
    "Room_Height":      4,
}


# ── Core prediction function ─────────────────────────────────────────────────
def predict_facade(
    WWR,
    Orientation,        # "N" | "E" | "S" | "W"
    Geometry,           # "NoPanel" | "C01" | "T01" | "H01"
    Panel_Size,         # 20 | 40 | 60  (cm)
    Porosity,           # 0.0 – 0.4
    Rotation,           # 0 – 60  (degrees)
    Glass_VLT,
    Glass_SHGC,
    Glass_U,
    Panel_Reflectance=None,
    Facade_Distance=None,
    Room_Depth=None,
    Room_Width=None,
    Room_Height=None,
):
    """
    Run the ML model and return a fully structured result dict.

    Required arguments match the six user-facing inputs in app.py.
    Optional arguments override the fixed constants when provided
    (e.g. when glass material is selected by the user in Rhino).

    Returns
    -------
    dict with keys:
        inputs    – echo of what was passed in
        outputs   – sDA, ASE, Lux, Radiation (rounded)
        status    – overall, sDA, ASE, Lux status strings
        suggestions – list of recommendation strings
    """

    # Apply defaults for any unset constants
    vlt   = Glass_VLT         if Glass_VLT         is not None else DEFAULTS["Glass_VLT"]
    shgc  = Glass_SHGC        if Glass_SHGC        is not None else DEFAULTS["Glass_SHGC"]
    u_val = Glass_U           if Glass_U           is not None else DEFAULTS["Glass_U"]
    refl  = Panel_Reflectance if Panel_Reflectance is not None else DEFAULTS["Panel_Reflectance"]
    dist  = Facade_Distance   if Facade_Distance   is not None else DEFAULTS["Facade_Distance"]
    depth = Room_Depth        if Room_Depth        is not None else DEFAULTS["Room_Depth"]
    width = Room_Width        if Room_Width        is not None else DEFAULTS["Room_Width"]
    height= Room_Height       if Room_Height       is not None else DEFAULTS["Room_Height"]

    # One-hot encode orientation
    Orientation_E = 1 if Orientation == "E" else 0
    Orientation_N = 1 if Orientation == "N" else 0
    Orientation_S = 1 if Orientation == "S" else 0
    Orientation_W = 1 if Orientation == "W" else 0

    # One-hot encode geometry
    Geometry_C01 = 1 if Geometry == "C01" else 0
    Geometry_H01 = 1 if Geometry == "H01" else 0
    Geometry_T01 = 1 if Geometry == "T01" else 0
    Geometry_NoPanel = 1 if Geometry == "NoPanel" else 0

    # Build feature vector — same order as app.py line 488–494
    features = [[
        WWR, Panel_Size, Rotation, Porosity,
        vlt, shgc, u_val, refl,
        dist, depth, width, height,
        Orientation_E, Orientation_N, Orientation_S, Orientation_W,
        Geometry_C01, Geometry_H01, Geometry_NoPanel, Geometry_T01
    ]]

    prediction = _model.predict(features)
    sDA       = prediction[0][0]
    ASE       = prediction[0][1]
    Lux       = prediction[0][2]
    Radiation = prediction[0][3]

    final_status, sda_s, ase_s, lux_s = evaluate_status(sDA, ASE, Lux)
    suggestions = facade_recommendation(sDA, ASE, Lux)

    return {
        "inputs": {
            "WWR":        WWR,
            "Orientation":Orientation,
            "Geometry":   Geometry,
            "Panel_Size": Panel_Size,
            "Porosity":   Porosity,
            "Rotation":   Rotation,
        },
        "outputs": {
            "sDA":       round(float(sDA),       1),
            "ASE":       round(float(ASE),       1),
            "Lux":       round(float(Lux),       0),
            "Radiation": round(float(Radiation), 1),
        },
        "status": {
            "overall": final_status,
            "sDA":     sda_s,
            "ASE":     ase_s,
            "Lux":     lux_s,
        },
        "suggestions": suggestions,
    }


# ── Batch prediction (one call per floor/orientation from GH) ────────────────
def predict_batch(floor_list):
    """
    Run predictions for multiple floor/orientation entries at once.

    Parameters
    ----------
    floor_list : list of dicts, each with keys:
        floor        – int, floor number
        orientation  – "N"|"E"|"S"|"W"
        WWR          – float
        Geometry     – str
        Panel_Size   – int
        Porosity     – float
        Rotation     – int
        (all glass/room constants are optional, fall back to DEFAULTS)

    Returns
    -------
    list of dicts — each is the full result from predict_facade(),
    with "floor" key added for identification.
    """
    results = []
    for entry in floor_list:
        result = predict_facade(
            WWR         = entry["WWR"],
            Orientation = entry["orientation"],
            Geometry    = entry.get("Geometry",    "None"),
            Panel_Size  = entry.get("Panel_Size",  40),
            Porosity    = entry.get("Porosity",    0.1),
            Rotation    = entry.get("Rotation",    0),
            Glass_VLT   = entry.get("Glass_VLT"),
            Glass_SHGC  = entry.get("Glass_SHGC"),
            Glass_U     = entry.get("Glass_U"),
        )
        result["floor"] = entry["floor"]
        results.append(result)
    return results


# ── Status evaluation (identical to app.py) ──────────────────────────────────
def evaluate_status(sDA, ASE, Lux):
    if sDA >= 75:
        sda_status = "high"
    elif sDA >= 55:
        sda_status = "pass"
    else:
        sda_status = "fail"

    if ASE <= 10:
        ase_status = "pass"
    else:
        ase_status = "fail"

    if 300 <= Lux <= 3000:
        lux_status = "good"
    else:
        lux_status = "warning"

    if sda_status == "fail" or ase_status == "fail":
        final_status = "NOT COMPLIANT"
    elif sda_status == "high" and ase_status == "pass" and lux_status == "good":
        final_status = "HIGH PERFORMANCE"
    else:
        final_status = "COMPLIANT"

    return final_status, sda_status, ase_status, lux_status


# ── Recommendations (identical to app.py) ────────────────────────────────────
def facade_recommendation(sDA, ASE, Lux):
    suggestions = []

    if sDA < 55:
        suggestions += [
            "Increase WWR to improve daylight access",
            "Increase facade porosity (larger gaps between panels)",
            "Reduce shading density (smaller panels or less overlap)"
        ]
    elif 55 <= sDA < 75:
        suggestions.append("Optimize WWR or porosity to reach higher daylight performance (target sDA >= 75%)")

    if ASE > 10:
        suggestions += [
            "Reduce WWR to limit direct solar exposure",
            "Increase shading using larger panels or reduced porosity",
            "Increase panel rotation to block direct sunlight"
        ]

    if Lux < 300:
        suggestions.append("Increase daylight by adjusting WWR or porosity")
    elif Lux > 3000:
        suggestions.append("Reduce daylight using shading strategies (rotation, panel density, or lower WWR)")

    return list(set(suggestions))


# ── Quick test when run directly ─────────────────────────────────────────────
if __name__ == "__main__":
    test = predict_facade(
        WWR=0.4, Orientation="S", Geometry="C01",
        Panel_Size=40, Porosity=0.1, Rotation=15
    )
    import json
    print(json.dumps(test, indent=2))
