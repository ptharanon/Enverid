import sys
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

INLINE_DATA = [
    {"experiment": 1, "sensor_id": 101,  "baseline": 536, "exposure": 751, "post_vent": 576, "injection_time": 2},
    {"experiment": 1, "sensor_id": 99, "baseline": 571, "exposure": 802, "post_vent": 620, "injection_time": 2},

    {"experiment": 2, "sensor_id": 101,  "baseline": 581, "exposure": 1445, "post_vent": 610, "injection_time": 4},
    {"experiment": 2, "sensor_id": 99, "baseline": 624, "exposure": 1473, "post_vent": 652, "injection_time": 4},

    {"experiment": 3, "sensor_id": 101,  "baseline": 611, "exposure": 2423, "post_vent": 652, "injection_time": 8},
    {"experiment": 3, "sensor_id": 99, "baseline": 658, "exposure": 2487, "post_vent": 707, "injection_time": 8},
]
# =========================

PHASES = ["baseline", "exposure", "post_vent"]
CONTROL_DEFAULT = 99

def linreg(x, y, force_slope_one=False):
    if force_slope_one:
        # Offset-only calibration: y = x + offset
        # Find offset that minimizes error: offset = mean(y - x)
        offset = float((y - x).mean())
        a = offset  # intercept
        b = 1.0     # slope fixed at 1.0
        yhat = a + b * x
    else:
        # Standard OLS with both slope and intercept
        b, a = np.polyfit(x, y, 1)
        yhat = a + b * x
    
    resid = y - yhat
    ss_res = float((resid**2).sum())
    ss_tot = float(((y - y.mean())**2).sum())
    r2 = 1.0 - (ss_res / ss_tot if ss_tot > 0 else float("nan"))
    rmse = math.sqrt(float((resid**2).mean()))
    mae = float(np.abs(resid).mean())
    max_abs = float(np.abs(resid).max())
    return dict(intercept=a, slope=b, r2=r2, rmse=rmse, mae=mae, max_abs=max_abs, yhat=yhat, resid=resid)

def to_long(df):
    recs = []
    for _, r in df.iterrows():
        for p in PHASES:
            recs.append({
                "experiment": r["experiment"],
                "sensor_id": r["sensor_id"],
                "phase": p.upper(),
                "reading": r[p]
            })
    return pd.DataFrame(recs)

def pair_with_control(long_df, control_id):
    s = long_df[long_df["sensor_id"] != control_id].copy()
    c = long_df[long_df["sensor_id"] == control_id].copy()
    merged = pd.merge(
        s, c,
        on=["experiment", "phase"],
        suffixes=("_sensor", "_control"),
        validate="many_to_one"
    )
    return merged

def plot_vs_control(y_true, y_pred, title, outpath):
    xy_min = float(min(y_true.min(), y_pred.min()))
    xy_max = float(max(y_true.max(), y_pred.max()))
    pad = (xy_max - xy_min) * 0.05 if xy_max > xy_min else 1.0
    lo, hi = xy_min - pad, xy_max + pad

    plt.figure(figsize=(7,6))
    plt.scatter(y_true, y_pred)
    plt.plot([lo, hi], [lo, hi])
    plt.xlabel("Control (ppm)")
    plt.ylabel("Sensor (ppm)")
    plt.title(title)
    plt.xlim(lo, hi)
    plt.ylim(lo, hi)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

def plot_all_sensors_vs_control(merged, sensor_fits, title, outpath, apply_calibration=False):
    xy_min = float(merged["reading_control"].min())
    xy_max = float(merged["reading_control"].max())
    pad = (xy_max - xy_min) * 0.05 if xy_max > xy_min else 1.0
    lo, hi = xy_min - pad, xy_max + pad

    plt.figure(figsize=(8,7))
    
    sensors = sorted(merged["sensor_id_sensor"].unique())

    colors = ['#E63946', '#2A9D8F', '#F4A261', '#8338EC', '#3A86FF', '#FB5607']
    
    for sid, color in zip(sensors, colors):
        sub = merged[merged["sensor_id_sensor"] == sid].copy()
        x_control = sub["reading_control"].to_numpy(dtype=float)
        y_sensor = sub["reading_sensor"].to_numpy(dtype=float)
        
        if apply_calibration and sid in sensor_fits:
            fit = sensor_fits[sid]
            y_sensor = fit['intercept'] + fit['slope'] * y_sensor
        
        plt.scatter(x_control, y_sensor, label=f"Sensor {int(sid)}", alpha=0.7, color=color, s=50)
    
    plt.plot([lo, hi], [lo, hi], 'k--', label='Perfect correlation', linewidth=1.5)
    
    plt.xlabel("Control (ppm)", fontsize=11)
    plt.ylabel("Sensor (ppm)", fontsize=11)
    plt.title(title, fontsize=12)
    plt.xlim(lo, hi)
    plt.ylim(lo, hi)
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

def plot_injected_co2_vs_time(df, sensor_fits, title, outpath, apply_calibration=False, control_id=99):
    plt.figure(figsize=(8,7))
    
    colors = ['#E63946', '#2A9D8F', '#F4A261', '#8338EC', '#3A86FF', '#FB5607']
    
    sensors = sorted([s for s in df['sensor_id'].unique() if s != control_id])
    
    for sid, color in zip(sensors, colors):
        sensor_data = df[df['sensor_id'] == sid].copy()
        
        baseline = sensor_data['baseline'].to_numpy(dtype=float)
        exposure = sensor_data['exposure'].to_numpy(dtype=float)
        injection_time = sensor_data['injection_time'].to_numpy(dtype=float)
        
        if apply_calibration and sid in sensor_fits:
            fit = sensor_fits[sid]
            baseline_cal = fit['intercept'] + fit['slope'] * baseline
            exposure_cal = fit['intercept'] + fit['slope'] * exposure
            injected_co2 = exposure_cal - baseline_cal
        else:
            injected_co2 = exposure - baseline
        
        plt.plot(injection_time, injected_co2, 'o:', label=f"Sensor {int(sid)}", 
                color=color, linewidth=2, markersize=8, alpha=0.8)
    
    control_data = df[df['sensor_id'] == control_id].copy()
    baseline_control = control_data['baseline'].to_numpy(dtype=float)
    exposure_control = control_data['exposure'].to_numpy(dtype=float)
    injection_time_control = control_data['injection_time'].to_numpy(dtype=float)
    injected_co2_control = exposure_control - baseline_control
    
    plt.plot(injection_time_control, injected_co2_control, 's:', label=f"Control (Sensor {int(control_id)})", 
            color='black', linewidth=2.5, markersize=10, alpha=0.9)
    
    plt.xlabel("Injection Time (seconds)", fontsize=11)
    plt.ylabel("Injected CO₂ (ppm)", fontsize=11)
    plt.title(title, fontsize=12)
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()


def plot_absolute_co2_vs_time(df, sensor_fits, title, outpath, apply_calibration=False, control_id=99):
    fig, axes = plt.subplots(2, 1, figsize=(10, 10))
    
    colors = ['#E63946', '#2A9D8F', '#F4A261', '#8338EC', '#3A86FF', '#FB5607']
    phases = ['baseline', 'exposure']
    phase_labels = ['Baseline CO₂ Levels', 'Exposure CO₂ Levels']
    
    sensors = sorted([s for s in df['sensor_id'].unique() if s != control_id])
    
    for idx, (phase, phase_label) in enumerate(zip(phases, phase_labels)):
        ax = axes[idx]
        
        # Plot test sensors
        for sid, color in zip(sensors, colors):
            sensor_data = df[df['sensor_id'] == sid].copy()
            injection_times = sensor_data['injection_time'].to_numpy(dtype=float)
            phase_values = sensor_data[phase].to_numpy(dtype=float)
            
            if apply_calibration and sid in sensor_fits:
                fit = sensor_fits[sid]
                phase_values = fit['intercept'] + fit['slope'] * phase_values
            
            ax.plot(injection_times, phase_values, 'o-',
                   label=f"Sensor {int(sid)}", 
                   color=color, linewidth=2.5, markersize=9, alpha=0.8)
        
        # Plot control sensor
        control_data = df[df['sensor_id'] == control_id].copy()
        injection_times_control = control_data['injection_time'].to_numpy(dtype=float)
        phase_values_control = control_data[phase].to_numpy(dtype=float)
        
        ax.plot(injection_times_control, phase_values_control, 's-',
               label=f"Control (Sensor {int(control_id)})", 
               color='black', linewidth=3, markersize=10, alpha=0.9)
        
        ax.set_xlabel("Injection Time (seconds)", fontsize=11)
        ax.set_ylabel("CO₂ (ppm)", fontsize=11)
        ax.set_title(phase_label, fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        
        if phase == 'baseline':
            ax.yaxis.set_major_locator(plt.MultipleLocator(10))
            ax.yaxis.set_minor_locator(plt.MultipleLocator(2))
            ax.grid(True, which='major', alpha=0.5)
            ax.grid(True, which='minor', alpha=0.2)
        else:
            ax.grid(True, alpha=0.3)
    
    fig.suptitle(title, fontsize=13, fontweight='bold', y=0.995)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

def run(outdir: Path, control_id, offset_only=True):
    df = pd.DataFrame(INLINE_DATA)
    for col in ["experiment", "sensor_id"] + PHASES:
        if col not in df.columns:
            raise SystemExit(f"INLINE_DATA missing column '{col}'")
    long_df = to_long(df)
    merged = pair_with_control(long_df, control_id)

    sensors = sorted(merged["sensor_id_sensor"].unique())
    rows = []
    for sid in sensors:
        sub = merged[merged["sensor_id_sensor"] == sid].copy()
        x = sub["reading_sensor"].to_numpy(dtype=float)
        y = sub["reading_control"].to_numpy(dtype=float)
        fit = linreg(x, y, force_slope_one=offset_only)

        raw_plot = outdir / f"sensor_{sid}_raw_vs_control.png"
        cal_plot = outdir / f"sensor_{sid}_calibrated_vs_control.png"
        plot_vs_control(y_true=y, y_pred=x, title=f"Sensor {sid}: Raw vs Control", outpath=raw_plot)
        plot_vs_control(y_true=y, y_pred=(fit['intercept'] + fit['slope']*x),
                        title=f"Sensor {sid}: Calibrated vs Control (y = {fit['intercept']:.3f} + {fit['slope']:.6f}·x, R²={fit['r2']:.5f})",
                        outpath=cal_plot)

        rows.append({
            "sensor_id": sid,
            "intercept": fit["intercept"],
            "slope": fit["slope"],
            "R2": fit["r2"],
            "RMSE_ppm": fit["rmse"],
            "MAE_ppm": fit["mae"],
            "MaxAbs_ppm": fit["max_abs"],
            "n_points": len(x),
            "raw_plot": str(raw_plot),
            "cal_plot": str(cal_plot),
        })

    summary = pd.DataFrame(rows)
    summary_path = outdir / "calibration_summary.csv"
    summary.to_csv(summary_path, index=False)

    sensor_fits = {row['sensor_id']: {'intercept': row['intercept'], 'slope': row['slope']} 
                   for _, row in summary.iterrows()}

    all_raw_plot = outdir / "all_sensors_raw_vs_control.png"
    all_cal_plot = outdir / "all_sensors_calibrated_vs_control.png"
    
    plot_all_sensors_vs_control(
        merged, sensor_fits, 
        title="All Sensors: Raw vs Control",
        outpath=all_raw_plot,
        apply_calibration=False
    )
    
    plot_all_sensors_vs_control(
        merged, sensor_fits,
        title="All Sensors: Calibrated vs Control",
        outpath=all_cal_plot,
        apply_calibration=True
    )

    injected_raw_plot = outdir / "injected_co2_raw_vs_time.png"
    injected_cal_plot = outdir / "injected_co2_calibrated_vs_time.png"
    
    plot_injected_co2_vs_time(
        df, sensor_fits,
        title="Injected CO₂ vs Injection Time (Raw Sensors)",
        outpath=injected_raw_plot,
        apply_calibration=False,
        control_id=control_id
    )
    
    plot_injected_co2_vs_time(
        df, sensor_fits,
        title="Injected CO₂ vs Injection Time (Calibrated Sensors)",
        outpath=injected_cal_plot,
        apply_calibration=True,
        control_id=control_id
    )

    absolute_raw_plot = outdir / "absolute_co2_raw_vs_time.png"
    absolute_cal_plot = outdir / "absolute_co2_calibrated_vs_time.png"

    plot_absolute_co2_vs_time(
        df, sensor_fits,
        title="Absolute CO₂ Levels vs Injection Time (Raw Sensors)",
        outpath=absolute_raw_plot,
        apply_calibration=False,
        control_id=control_id
    )

    plot_absolute_co2_vs_time(
        df, sensor_fits,
        title="Absolute CO₂ Levels vs Injection Time (Calibrated Sensors)",
        outpath=absolute_cal_plot,
        apply_calibration=True,
        control_id=control_id
    )

    residual_rows = []
    for sid in sensors:
        sub = merged[merged["sensor_id_sensor"] == sid].copy()
        x = sub["reading_sensor"].to_numpy(dtype=float)
        y = sub["reading_control"].to_numpy(dtype=float)
        m, a = np.polyfit(x, y, 1)
        yhat = a + m * x
        for (_, r), xi, yi, yhi in zip(sub.iterrows(), x, y, yhat):
            residual_rows.append({
                "sensor_id": sid,
                "experiment": r["experiment"],
                "phase": r["phase"],
                "sensor_raw": xi,
                "control": yi,
                "sensor_calibrated": yhi,
                "error_before": xi - yi,
                "error_after": yhi - yi,
            })

    residuals = pd.DataFrame(residual_rows)
    residuals_path = outdir / "calibration_point_residuals.csv"
    residuals.to_csv(residuals_path, index=False)

    cal_method = "Offset-Only" if offset_only else "Full OLS"
    print(f"=== {cal_method} Calibration Equations ===")
    for _, row in summary.iterrows():
        print(f"Sensor {row['sensor_id']}: y = {row['intercept']:.6f} + {row['slope']:.9f} * x   (R^2={row['R2']:.5f}, RMSE={row['RMSE_ppm']:.2f} ppm, n={int(row['n_points'])})")
    print(f"\nWrote summary: {summary_path}")
    print(f"Wrote residuals: {residuals_path}")
    print(f"Individual sensor plots: {outdir}/sensor_*.png")
    print(f"Combined raw plot: {all_raw_plot}")
    print(f"Combined calibrated plot: {all_cal_plot}")
    print(f"Injected CO2 raw plot: {injected_raw_plot}")
    print(f"Injected CO2 calibrated plot: {injected_cal_plot}")
    print(f"Absolute CO2 raw plot: {absolute_raw_plot}")
    print(f"Absolute CO2 calibrated plot: {absolute_cal_plot}")


def run_with_csv(csv_path: Path, outdir: Path, control_id, offset_only=True):
    df = pd.read_csv(csv_path)

    def resolve(df, candidates):
        cols = {c.lower(): c for c in df.columns}
        for cand in candidates:
            if cand in df.columns:
                return cand
            if cand.lower() in cols:
                return cols[cand.lower()]
        return None

    idx_col = resolve(df, ["experiment", "no", "No", "NO"])
    sid_col = resolve(df, ["sensor_id", "SENSOR ID", "sensor id", "sensor"])
    base_col = resolve(df, ["baseline"])
    expo_col = resolve(df, ["exposure"])
    post_col = resolve(df, ["post_vent", "post-flush", "post_flush", "post"])

    required = {"experiment/index": idx_col, "sensor_id": sid_col, "baseline": base_col, "exposure": expo_col, "post_vent": post_col}
    missing = [k for k,v in required.items() if v is None]
    if missing:
        raise SystemExit(f"Missing required columns: {missing}. Provided columns: {list(df.columns)}")

    df = df.rename(columns={idx_col:"experiment", sid_col:"sensor_id", base_col:"baseline", expo_col:"exposure", post_col:"post_vent"})
    long_df = to_long(df)
    merged = pair_with_control(long_df, control_id)

    sensors = sorted(merged["sensor_id_sensor"].unique())
    rows = []
    for sid in sensors:
        sub = merged[merged["sensor_id_sensor"] == sid].copy()
        x = sub["reading_sensor"].to_numpy(dtype=float)
        y = sub["reading_control"].to_numpy(dtype=float)
        fit = linreg(x, y, force_slope_one=offset_only)

        raw_plot = outdir / f"sensor_{sid}_raw_vs_control.png"
        cal_plot = outdir / f"sensor_{sid}_calibrated_vs_control.png"
        plot_vs_control(y_true=y, y_pred=x, title=f"Sensor {sid}: Raw vs Control", outpath=raw_plot)
        plot_vs_control(y_true=y, y_pred=(fit['intercept'] + fit['slope']*x),
                        title=f"Sensor {sid}: Calibrated vs Control (y = {fit['intercept']:.3f} + {fit['slope']:.6f}·x, R²={fit['r2']:.5f})",
                        outpath=cal_plot)

        rows.append({
            "sensor_id": sid,
            "intercept": fit["intercept"],
            "slope": fit["slope"],
            "R2": fit["r2"],
            "RMSE_ppm": fit["rmse"],
            "MAE_ppm": fit["mae"],
            "MaxAbs_ppm": fit["max_abs"],
            "n_points": len(x),
            "raw_plot": str(raw_plot),
            "cal_plot": str(cal_plot),
        })

    summary = pd.DataFrame(rows)
    summary_path = outdir / "calibration_summary.csv"
    summary.to_csv(summary_path, index=False)

    sensor_fits = {row['sensor_id']: {'intercept': row['intercept'], 'slope': row['slope']} 
                   for _, row in summary.iterrows()}

    # Generate combined plots for all sensors
    all_raw_plot = outdir / "all_sensors_raw_vs_control.png"
    all_cal_plot = outdir / "all_sensors_calibrated_vs_control.png"
    
    plot_all_sensors_vs_control(
        merged, sensor_fits, 
        title="All Sensors: Raw vs Control",
        outpath=all_raw_plot,
        apply_calibration=False
    )
    
    plot_all_sensors_vs_control(
        merged, sensor_fits,
        title="All Sensors: Calibrated vs Control",
        outpath=all_cal_plot,
        apply_calibration=True
    )

    injected_raw_plot = outdir / "injected_co2_raw_vs_time.png"
    injected_cal_plot = outdir / "injected_co2_calibrated_vs_time.png"
    
    plot_injected_co2_vs_time(
        df, sensor_fits,
        title="Injected CO₂ vs Injection Time (Raw Sensors)",
        outpath=injected_raw_plot,
        apply_calibration=False,
        control_id=control_id
    )
    
    plot_injected_co2_vs_time(
        df, sensor_fits,
        title="Injected CO₂ vs Injection Time (Calibrated Sensors)",
        outpath=injected_cal_plot,
        apply_calibration=True,
        control_id=control_id
    )

    absolute_raw_plot = outdir / "absolute_co2_raw_vs_time.png"
    absolute_cal_plot = outdir / "absolute_co2_calibrated_vs_time.png"

    plot_absolute_co2_vs_time(
        df, sensor_fits,
        title="Absolute CO₂ Levels vs Injection Time (Raw Sensors)",
        outpath=absolute_raw_plot,
        apply_calibration=False,
        control_id=control_id
    )

    plot_absolute_co2_vs_time(
        df, sensor_fits,
        title="Absolute CO₂ Levels vs Injection Time (Calibrated Sensors)",
        outpath=absolute_cal_plot,
        apply_calibration=True,
        control_id=control_id
    )

    residual_rows = []
    for sid in sensors:
        sub = merged[merged["sensor_id_sensor"] == sid].copy()
        x = sub["reading_sensor"].to_numpy(dtype=float)
        y = sub["reading_control"].to_numpy(dtype=float)
        m, a = np.polyfit(x, y, 1)
        yhat = a + m * x
        for (_, r), xi, yi, yhi in zip(sub.iterrows(), x, y, yhat):
            residual_rows.append({
                "sensor_id": sid,
                "experiment": r["experiment"],
                "phase": r["phase"],
                "sensor_raw": xi,
                "control": yi,
                "sensor_calibrated": yhi,
                "error_before": xi - yi,
                "error_after": yhi - yi,
            })

    residuals = pd.DataFrame(residual_rows)
    residuals_path = outdir / "calibration_point_residuals.csv"
    residuals.to_csv(residuals_path, index=False)

    cal_method = "Offset-Only" if offset_only else "Full OLS"
    print(f"=== {cal_method} Calibration Equations (CSV DATA) ===")
    for _, row in summary.iterrows():
        print(f"Sensor {row['sensor_id']}: y = {row['intercept']:.6f} + {row['slope']:.9f} * x   (R^2={row['R2']:.5f}, RMSE={row['RMSE_ppm']:.2f} ppm, n={int(row['n_points'])})")
    print(f"\nSummary: {summary_path}")
    print(f"Residuals: {residuals_path}")
    print(f"Individual sensor plots: {outdir}/sensor_*.png")
    print(f"Combined raw plot: {all_raw_plot}")
    print(f"Combined calibrated plot: {all_cal_plot}")
    print(f"Injected CO2 raw plot: {injected_raw_plot}")
    print(f"Injected CO2 calibrated plot: {injected_cal_plot}")
    print(f"Absolute CO2 raw plot: {absolute_raw_plot}")
    print(f"Absolute CO2 calibrated plot: {absolute_cal_plot}")


def main():
    outdir: Path = Path("calibration_output")
    outdir.mkdir(parents=True, exist_ok=True)

    run(outdir, CONTROL_DEFAULT)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)