import numpy as np

# All data points from INLINE_DATA
data = [
    # Baseline
    (536, 571),  # Exp 1
    (581, 624),  # Exp 2  
    (611, 658),  # Exp 3
    # Exposure
    (751, 802),  # Exp 1
    (1445, 1473), # Exp 2
    (2423, 2487), # Exp 3
    # Post-vent
    (576, 620),  # Exp 1
    (610, 652),  # Exp 2
    (652, 707),  # Exp 3
]

print("All 9 data points (sensor_101, control_99):")
for i, (s, c) in enumerate(data, 1):
    print(f"Point {i}: Sensor={s:4}, Control={c:4}, Diff={c-s:+4}")

diffs = [c - s for s, c in data]
offset = np.mean(diffs)

print(f"\nOverall offset (mean of all 9 points): {offset:.6f} ppm")
print(f"\nBaseline Exp 1 calibration:")
print(f"  Raw: 536 ppm")
print(f"  Calibrated: 536 + {offset:.6f} = {536 + offset:.6f} ppm")
print(f"  Control: 571 ppm")
print(f"  Error: {536 + offset - 571:+.6f} ppm")
