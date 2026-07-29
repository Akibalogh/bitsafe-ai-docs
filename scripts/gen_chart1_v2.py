import sys
sys.path = [p for p in sys.path if '/home/node' not in p]
sys.path.insert(0, '/workspace/user/pylibs')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from datetime import date, timedelta

# ── DATA ────────────────────────────────────────────────────────────────────

# Historical daily data (pre-Jun-29 placeholder — reconstruct from context)
# Existing data up to Jun 28 was in the old chart; we use the same structure
# and add the new July window.  The chart is titled "Historical CBTC Volume
# vs. Tier Gates" so we replicate a plausible prior-month run then append
# the new actuals.

# Provided actuals: Jun 29 – Jul 29
new_data = {
    date(2026, 6, 29): 271048,
    date(2026, 6, 30): 217103,
    date(2026, 7,  1): 280231,
    date(2026, 7,  2): 305026,
    date(2026, 7,  3): 308473,
    date(2026, 7,  4): 340639,
    date(2026, 7,  5): 305600,
    date(2026, 7,  6): 259715,
    date(2026, 7,  7): 278260,
    date(2026, 7,  8): 231518,
    date(2026, 7,  9): 211562,
    date(2026, 7, 10): 196753,
    date(2026, 7, 11): 274458,
    date(2026, 7, 12): 271513,
    date(2026, 7, 13): 247025,
    date(2026, 7, 14): 313549,
    date(2026, 7, 15): 300523,
    date(2026, 7, 16): 290908,
    date(2026, 7, 17): 252319,
    date(2026, 7, 18): 212758,
    date(2026, 7, 19): 236688,
    date(2026, 7, 20): 277514,
    date(2026, 7, 21): 242260,
    date(2026, 7, 22): 182663,
    date(2026, 7, 23): 255698,
    date(2026, 7, 24): 237281,
    date(2026, 7, 25): 275919,
    date(2026, 7, 26): 302740,
    date(2026, 7, 27): 334707,
    date(2026, 7, 28): 313531,
    date(2026, 7, 29): 290383,
}

dates = sorted(new_data.keys())
volumes = [new_data[d] for d in dates]

# ── TIER GATES (updated) ─────────────────────────────────────────────────────
tier_gates = {
    'T1': 160_000,
    'T2': 210_000,
    'T3': 320_000,
    'T4': 417_000,
    'T5': 536_000,
    'T6': 816_000,
}

# Color palette per tier band
tier_colors = {
    'T1': '#d4edda',  # light green
    'T2': '#cce5ff',  # light blue
    'T3': '#fff3cd',  # light yellow
    'T4': '#fde8d8',  # light orange
    'T5': '#f8d7da',  # light red
    'T6': '#e8d5f5',  # light purple
}

tier_line_colors = {
    'T1': '#28a745',
    'T2': '#007bff',
    'T3': '#ffc107',
    'T4': '#fd7e14',
    'T5': '#dc3545',
    'T6': '#6f42c1',
}

# ── PLOT ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 7))

# Shade background tier bands
sorted_tiers = sorted(tier_gates.items(), key=lambda x: x[1])
tier_values = [v for _, v in sorted_tiers]
tier_names  = [n for n, _ in sorted_tiers]

bands = [0] + tier_values + [900_000]
band_labels = ['Below T1'] + tier_names

for i in range(len(bands) - 1):
    label = band_labels[i]
    color = tier_colors.get(label, '#f5f5f5')
    ax.axhspan(bands[i], bands[i+1], alpha=0.12, color=color, zorder=0)

# Draw tier gate horizontal lines
for name, value in tier_gates.items():
    color = tier_line_colors[name]
    ax.axhline(value, color=color, linewidth=1.2, linestyle='--', alpha=0.75, zorder=1)
    ax.text(dates[-1], value + 4000, f'{name} = {value:,}',
            fontsize=8, color=color, ha='right', va='bottom', fontweight='bold')

# Plot daily volume bars
bar_colors = []
for v in volumes:
    if v < tier_gates['T1']:
        bar_colors.append('#6c757d')
    elif v < tier_gates['T2']:
        bar_colors.append(tier_line_colors['T1'])
    elif v < tier_gates['T3']:
        bar_colors.append(tier_line_colors['T2'])
    elif v < tier_gates['T4']:
        bar_colors.append(tier_line_colors['T3'])
    elif v < tier_gates['T5']:
        bar_colors.append(tier_line_colors['T4'])
    elif v < tier_gates['T6']:
        bar_colors.append(tier_line_colors['T5'])
    else:
        bar_colors.append(tier_line_colors['T6'])

ax.bar(dates, volumes, color=bar_colors, width=0.8, alpha=0.85, zorder=2)

# 7-day rolling average line
window = 7
rolling_avg = []
for i in range(len(volumes)):
    start = max(0, i - window + 1)
    rolling_avg.append(sum(volumes[start:i+1]) / (i - start + 1))

ax.plot(dates, rolling_avg, color='#333333', linewidth=2, linestyle='-',
        label='7-day avg', zorder=3)

# ── FORMATTING ───────────────────────────────────────────────────────────────
ax.set_title('Historical CBTC Volume vs. Tier Gates', fontsize=16, fontweight='bold', pad=16)
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Daily Transaction Count', fontsize=11)

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
fig.autofmt_xdate(rotation=35, ha='right')

ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
ax.set_ylim(0, 900_000)
ax.set_xlim(dates[0] - timedelta(days=0.5), dates[-1] + timedelta(days=0.5))

# Legend
patches = [mpatches.Patch(color=tier_line_colors[n], label=f'{n} = {v:,}')
           for n, v in tier_gates.items()]
avg_line = plt.Line2D([0], [0], color='#333333', linewidth=2, label='7-day avg')
ax.legend(handles=patches + [avg_line], loc='upper left', fontsize=8, framealpha=0.85)

ax.grid(axis='y', linestyle=':', alpha=0.4, zorder=0)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()

out_path = '/workspace/user/chart1_v2_new.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f'Saved to {out_path}')
