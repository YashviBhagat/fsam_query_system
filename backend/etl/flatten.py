import re
from backend.etl.loader import load_all_json_files


def extract_numeric_and_unit(value) -> tuple:
    """
    Extracts min, max, and normalized unit from any value string.
    Handles: ranges, ± errors, single values, unit conversions.
    """
    if value is None:
        return None, None, None

    text = str(value).strip()

    # ── Step 1: Normalize all unit variants ─────────────

    # Hardness
    text = re.sub(r'\bHv\b', 'HV', text)
    text = re.sub(r'HV\s*\d+\.?\d*', 'HV', text)   # HV0.2, HV0.5 → HV
    text = re.sub(r'\bVHN\b|\bHVN\b', 'HV', text)

    # Speed
    text = re.sub(r'\br/min\b|\brev/min\b|\bRPM\b', 'rpm', text)

    # Length
    text = re.sub(r'\bμm\b|\bum\b', 'µm', text)

    # Pressure
    text = re.sub(r'\bMPA\b', 'MPa', text)
    text = re.sub(r'\bGPA\b', 'GPa', text)

    # Temperature unicode fix
    text = re.sub(r'℃', '°C', text)

    # ── Step 2: Handle unit CONVERSIONS ─────────────────

    # IPM → mm/min (1 IPM = 25.4 mm/min)
    ipm_match = re.match(r'^([\d\.]+)\s*[–\-—]\s*([\d\.]+)\s*IPM', text)
    if ipm_match:
        return (
            round(float(ipm_match.group(1)) * 25.4, 2),
            round(float(ipm_match.group(2)) * 25.4, 2),
            'mm/min'
        )
    single_ipm = re.match(r'^([\d\.]+)\s*IPM', text)
    if single_ipm:
        val = round(float(single_ipm.group(1)) * 25.4, 2)
        return val, val, 'mm/min'

    # Kelvin → Celsius
    k_match = re.match(r'^([\d\.]+)\s*K\b', text)
    if k_match:
        val = round(float(k_match.group(1)) - 273.15, 2)
        return val, val, '°C'

    # ── Step 3: Handle ± patterns FIRST ─────────────────
    # "86.3 ± 1.7 HV" → (86.3, 86.3, "HV")
    pm = re.match(
        r'^([\d\.]+)\s*(?:±|\+/?-)\s*[\d\.]+\s*(.*)',
        text
    )
    if pm:
        main_val = float(pm.group(1))
        unit     = pm.group(2).strip() or None
        if unit:
            unit = re.sub(r'^[±\+\-\s]+', '', unit).strip()
            unit = unit if unit else None
        return main_val, main_val, unit

    # ── Step 4: Handle ranges ────────────────────────────
    # "71.93–88.53 HV" or "1000-2000 rpm"
    rng = re.match(
        r'^([\d\.]+)\s*[–\-—]\s*([\d\.]+)\s*(.*)',
        text
    )
    if rng:
        min_val = float(rng.group(1))
        max_val = float(rng.group(2))
        unit    = rng.group(3).strip() or None
        return min_val, max_val, unit

    # ── Step 5: Handle single value ─────────────────────
    single = re.match(r'^([\d\.]+)\s*(.*)', text)
    if single:
        val  = float(single.group(1))
        unit = single.group(2).strip() or None
        return val, val, unit

    return None, None, None

def flatten_paper(paper: dict) -> dict:
    """
    Takes one nested JSON and returns one completely flat dict.
    Every field is captured. Numeric fields have _min, _max, _unit columns.
    """
    d   = paper["data"]
    pid = paper["paper_id"]

    meta    = d.get("metadata", {})                or {}
    mat     = d.get("material_input", {})           or {}
    proc    = d.get("process_parameters", {})       or {}
    tool    = d.get("tool_geometry_parameters", {}) or {}
    physics = d.get("physics_and_environment", {})  or {}
    micro   = d.get("microstructure_outputs", {})   or {}
    mech    = d.get("mechanical_outputs", {})       or {}

    # ── Extract numeric + units ──────────────────────────
    hard_min,    hard_max,    hard_unit    = extract_numeric_and_unit(mech.get("measured_hardness"))
    ys_min,      ys_max,      ys_unit      = extract_numeric_and_unit(mech.get("yield_strength"))
    uts_min,     uts_max,     uts_unit     = extract_numeric_and_unit(mech.get("ultimate_tensile_strength"))
    elong_min,   elong_max,   elong_unit   = extract_numeric_and_unit(mech.get("Elongation_percentage"))
    ductility,   _,           duct_unit    = extract_numeric_and_unit(mech.get("ductility_percentage"))

    grain_min,   grain_max,   grain_unit   = extract_numeric_and_unit(micro.get("final_grain_size"))
    grain_ref,   _,           gref_unit    = extract_numeric_and_unit(micro.get("grain_refinement_factor"))

    init_grain,  _,           igrain_unit  = extract_numeric_and_unit(mat.get("initial_grain_size"))
    density,     _,           dens_unit    = extract_numeric_and_unit(mat.get("density"))
    melting_pt,  _,           melt_unit    = extract_numeric_and_unit(mat.get("melting_point"))
    thermal_c,   _,           therm_unit   = extract_numeric_and_unit(mat.get("thermal_conductivity"))

    rpm_min,     rpm_max,     rpm_unit     = extract_numeric_and_unit(proc.get("rotation_speed"))
    vel_min,     vel_max,     vel_unit     = extract_numeric_and_unit(proc.get("traverse_velocity"))
    feed_min,    feed_max,    feed_unit    = extract_numeric_and_unit(proc.get("feed_rate_or_pitch"))
    layer_thick, _,           layer_unit   = extract_numeric_and_unit(proc.get("layer_thickness"))
    tilt_angle,  _,           tilt_unit    = extract_numeric_and_unit(proc.get("tool_tilt_angle"))
    dwell_time,  _,           dwell_unit   = extract_numeric_and_unit(proc.get("interlayer_dwell_time"))

    shoulder,    _,           shldr_unit   = extract_numeric_and_unit(tool.get("shoulder_diameter"))
    pin_root,    _,           proot_unit   = extract_numeric_and_unit(tool.get("pin_diameter_root"))
    pin_tip,     _,           ptip_unit    = extract_numeric_and_unit(tool.get("pin_diameter_tip"))
    pin_len,     _,           plen_unit    = extract_numeric_and_unit(tool.get("pin_length"))

    temp_min,    temp_max,    temp_unit    = extract_numeric_and_unit(physics.get("peak_temperature_recorded"))
    axial_force, _,           force_unit   = extract_numeric_and_unit(physics.get("axial_force"))
    torque,      _,           torq_unit    = extract_numeric_and_unit(physics.get("torque"))
    ambient_t,   _,           amb_unit     = extract_numeric_and_unit(physics.get("ambient_temperature"))

    row = {
        # ── METADATA ──────────────────────────────────────
        "paper_id":                     pid,
        "paper_name":                   meta.get("paper_name"),
        "sample_id":                    meta.get("sample_id"),

        # ── MATERIAL INPUT ────────────────────────────────
        "base_alloy":                   mat.get("base_alloy"),
        "starting_temper":              mat.get("starting_temper"),
        "temper_condition":             mat.get("temper_condition"),
        "starting_material_form":       mat.get("starting_material_form"),
        "reinforcement_material":       mat.get("reinforcement_material"),
        "reinforcement_vol_pct":        mat.get("reinforcement_vol_pct"),
        "elemental_composition":        str(mat.get("elemental_composition_wt_pct")),
        "melting_point":                melting_pt,
        "melting_point_unit":           melt_unit,
        "thermal_conductivity":         thermal_c,
        "thermal_conductivity_unit":    therm_unit,
        "density":                      density,
        "density_unit":                 dens_unit,
        "initial_grain_size":           init_grain,
        "initial_grain_size_unit":      igrain_unit,

        # ── PROCESS PARAMETERS ────────────────────────────
        "process_category":             proc.get("process_category"),
        "process_description":          proc.get("process_description"),
        "rotation_speed_min":           rpm_min,
        "rotation_speed_max":           rpm_max,
        "rotation_speed_unit":          rpm_unit,
        "traverse_velocity_min":        vel_min,
        "traverse_velocity_max":        vel_max,
        "traverse_velocity_unit":       vel_unit,
        "feed_rate_min":                feed_min,
        "feed_rate_max":                feed_max,
        "feed_rate_unit":               feed_unit,
        "layer_thickness":              layer_thick,
        "layer_thickness_unit":         layer_unit,
        "build_direction":              proc.get("build_direction"),
        "interlayer_dwell_time":        dwell_time,
        "interlayer_dwell_time_unit":   dwell_unit,
        "tool_tilt_angle":              tilt_angle,
        "tool_tilt_angle_unit":         tilt_unit,

        # ── TOOL GEOMETRY ─────────────────────────────────
        "tool_material":                tool.get("tool_material"),
        "shoulder_diameter":            shoulder,
        "shoulder_diameter_unit":       shldr_unit,
        "shoulder_feature":             tool.get("shoulder_feature"),
        "pin_diameter_root":            pin_root,
        "pin_diameter_root_unit":       proot_unit,
        "pin_diameter_tip":             pin_tip,
        "pin_diameter_tip_unit":        ptip_unit,
        "pin_length":                   pin_len,
        "pin_length_unit":              plen_unit,
        "pin_geometry":                 tool.get("pin_geometry"),
        "pin_features":                 tool.get("pin_features"),

        # ── PHYSICS & ENVIRONMENT ─────────────────────────
        "peak_temperature":             temp_min,
        "peak_temperature_max":         temp_max,
        "peak_temperature_unit":        temp_unit,
        "axial_force":                  axial_force,
        "axial_force_unit":             force_unit,
        "torque":                       torque,
        "torque_unit":                  torq_unit,
        "ambient_temperature":          ambient_t,
        "ambient_temperature_unit":     amb_unit,
        "cooling_method":               physics.get("cooling_method"),
        "cooling_medium":               physics.get("cooling_medium"),
        "inert_gas_used":               physics.get("inert_gas_used"),

        # ── MICROSTRUCTURE OUTPUTS ────────────────────────
        "final_grain_size_min":         grain_min,
        "final_grain_size_max":         grain_max,
        "final_grain_size_unit":        grain_unit,
        "grain_morphology":             micro.get("grain_morphology"),
        "recrystallization_type":       micro.get("recrystallization_type"),
        "precipitate_condition":        micro.get("precipitate_condition"),
        "second_phase_particles":       micro.get("second_phase_particles"),
        "phase_transformation_details": micro.get("phase_transformation_details"),
        "defect_type":                  micro.get("defect_type"),
        "grain_refinement_factor":      grain_ref,
        "grain_refinement_factor_unit": gref_unit,

        # ── MECHANICAL OUTPUTS ────────────────────────────
        "hardness_min":                 hard_min,
        "hardness_max":                 hard_max,
        "hardness_unit":                hard_unit,
        "yield_strength_min":           ys_min,
        "yield_strength_max":           ys_max,
        "yield_strength_unit":          ys_unit,
        "uts_min":                      uts_min,
        "uts_max":                      uts_max,
        "uts_unit":                     uts_unit,
        "elongation_min":               elong_min,
        "elongation_max":               elong_max,
        "elongation_unit":              elong_unit,
        "ductility":                    ductility,
        "ductility_unit":               duct_unit,
    }

    return row


def flatten_all_papers() -> list[dict]:
    """Loads all JSONs and flattens every one into a list of rows."""
    papers = load_all_json_files()
    rows = []

    for paper in papers:
        try:
            row = flatten_paper(paper)
            rows.append(row)
        except Exception as e:
            print(f"❌ Error flattening {paper['paper_id']}: {e}")

    print(f"\n✅ Flattened {len(rows)} papers into table format")
    return rows


if __name__ == "__main__":
    import pandas as pd
    import os

    rows = flatten_all_papers()
    #DataFrame is used for TWO purposes only
    #Purpose 1: Visual inspection: Without DataFrame you'd be staring at raw Python dicts — very hard to read.
    #Purpose 2: Easy CSV export
    df = pd.DataFrame(rows)

    print(f"\n--- Table Shape ---")
    print(f"Rows: {len(df)} | Columns: {len(df.columns)}")

    print(f"\n--- Sample: Hardness with units ---")
    sample = df[["paper_id", "base_alloy",
                 "hardness_min", "hardness_max", "hardness_unit",
                 "rotation_speed_min", "rotation_speed_unit"]].head(5)
    print(sample.to_string())

    os.makedirs("data/exports", exist_ok=True)
    df.to_csv("data/exports/fsam_flat.csv", index=False,encoding='utf-8-sig')
    print(f"\n💾 Saved to data/exports/fsam_flat.csv")