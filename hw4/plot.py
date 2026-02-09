import matplotlib.pyplot as plt
import statistics as stats

baseline = [0.85, 0.60, 0.33, 1.42, 0.49]
mapreduce = [2.17, 1.40, 1.08, 1.17, 0.97]

baseline_avg = stats.mean(baseline)
mapreduce_avg = stats.mean(mapreduce)

labels = ["Baseline", "MapReduce"]
values = [baseline_avg, mapreduce_avg]

fig = plt.figure()
ax = fig.add_subplot(111)
ax.bar(labels, values)

ax.set_ylabel("Average latency (seconds)")
ax.set_title("Average end-to-end latency (n=5 each)")

for i, v in enumerate(values):
    ax.text(i, v, f"{v:.2f}s", ha="center", va="bottom")

plt.tight_layout()
plt.savefig("performance_barchart.png", dpi=200)
print("Saved: performance_barchart.png")
