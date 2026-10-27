import os
import time

CHART_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use('Agg')  # Headless mode: avoids GUI thread crashes
    import matplotlib.pyplot as plt
    import numpy as np
    CHART_AVAILABLE = True
except ImportError:
    pass

def make_charts(chart_folder, poll_id, labels, votes):
    """
    Generates Bar and Pie charts for a given poll.
    Returns (bar_chart_rel_path, pie_chart_rel_path, timestamp) or (None, None, None)
    """
    if not CHART_AVAILABLE:
        return None, None, None

    if not votes or sum(votes) == 0 or len(labels) == 0:
        return None, None, None

    os.makedirs(chart_folder, exist_ok=True)
    ts = int(time.time())

    # Try removing old charts for this poll (ignore if file is locked on Windows)
    for f in os.listdir(chart_folder):
        if f.startswith(f"poll_{poll_id}_"):
            try:
                os.remove(os.path.join(chart_folder, f))
            except Exception:
                pass

    n = len(labels)
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, max(n, 1)))

    bar_filename = f"poll_{poll_id}_bar_{ts}.png"
    pie_filename = f"poll_{poll_id}_pie_{ts}.png"

    bar_path = os.path.join(chart_folder, bar_filename)
    pie_path = os.path.join(chart_folder, pie_filename)

    # --- BAR CHART ---
    try:
        fig, ax = plt.subplots(figsize=(10, 5.5))
        bars = ax.bar(labels, votes, color=colors, edgecolor='black', linewidth=1.2, alpha=0.9)
        ax.set_title('Candidate Vote Count', fontsize=16, fontweight='bold', pad=15)
        ax.set_ylabel('Number of Votes', fontsize=12)
        ax.set_xlabel('Candidates', fontsize=12)
        ax.tick_params(axis='x', rotation=30)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        max_v = max(votes) if votes else 1
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + (max_v * 0.02 if max_v > 0 else 0.1),
                f'{int(h)}',
                ha='center',
                va='bottom',
                fontweight='bold',
                fontsize=11
            )

        plt.tight_layout()
        fig.savefig(bar_path, dpi=150, bbox_inches='tight', facecolor='#ffffff')
        plt.close(fig)
    except Exception as e:
        print(f"[Chart Error] Bar chart failed: {e}")
        bar_filename = None

    # --- PIE / DONUT CHART ---
    try:
        fig, ax = plt.subplots(figsize=(8, 8))
        total_votes = sum(votes)
        wedges, texts, autotexts = ax.pie(
            votes,
            labels=labels,
            autopct=lambda pct: f'{pct:.1f}%\n({int(round(pct/100*total_votes))})' if pct > 0 else '',
            startangle=90,
            colors=colors,
            textprops={'fontsize': 10, 'fontweight': 'bold'},
            wedgeprops={'edgecolor': 'white', 'linewidth': 2}
        )
        ax.set_title('Vote Distribution Percentage', fontsize=16, fontweight='bold', pad=15)
        centre_circle = plt.Circle((0, 0), 0.65, fc='white')
        fig.gca().add_artist(centre_circle)
        plt.tight_layout()
        fig.savefig(pie_path, dpi=150, bbox_inches='tight', facecolor='#ffffff')
        plt.close(fig)
    except Exception as e:
        print(f"[Chart Error] Pie chart failed: {e}")
        pie_filename = None

    rel_bar = f"charts/{bar_filename}" if bar_filename else None
    rel_pie = f"charts/{pie_filename}" if pie_filename else None
    return rel_bar, rel_pie, ts

