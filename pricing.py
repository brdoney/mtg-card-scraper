import json
import os
from collections import defaultdict

input_dir = "out"

# Map "name + attributes" to all entries
items = defaultdict(list)

# Read JSON files
for filename in os.listdir(input_dir):
    if filename.endswith(".json"):
        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                for entry in data:
                    key = f"{entry['name']}|{entry['attributes']}"
                    items[key].append(entry)
            except json.JSONDecodeError as e:
                print(f"Error reading {filename}: {e}")

# Initialize store stats for three categories
categories = ["all", "cheap", "expensive"]
store_stats = {cat: defaultdict(lambda: {"count": 0, "total_savings": 0.0}) for cat in categories}

results = []

for key, entries in items.items():
    if len(entries) < 2:
        continue
    # Sort by price ascending
    sorted_entries = sorted(entries, key=lambda x: x["price"])
    cheapest = sorted_entries[0]
    for other in sorted_entries[1:]:
        high_price = max(cheapest["price"], other["price"])
        low_price = min(cheapest["price"], other["price"])
        savings_pct = ((high_price - low_price) / high_price) * 100 if high_price != 0 else 0
        results.append({
            "name": cheapest["name"],
            "attributes": cheapest["attributes"],
            "cheaper_store": cheapest["store"],
            "cheaper_price": cheapest["price"],
            "other_store": other["store"],
            "other_price": other["price"],
            "savings_pct": savings_pct
        })

        # Determine category
        if cheapest["price"] > 1:
            cat_list = ["all", "expensive"]
        else:
            cat_list = ["all", "cheap"]
        for cat in cat_list:
            store_stats[cat][cheapest["store"]]["count"] += 1
            store_stats[cat][cheapest["store"]]["total_savings"] += savings_pct

# Print detailed results
for r in results:
    print(f"{r['name']} [{r['attributes']}] - cheaper in {r['cheaper_store']} at ${r['cheaper_price']:.2f} "
          f"vs {r['other_store']} at ${r['other_price']:.2f} ({r['savings_pct']:.2f}% savings)")

# Print overall averages per category
print("\nOverall average savings per store:")
for cat in categories:
    print(f"\nCategory: {cat.capitalize()}")
    for store, stats in store_stats[cat].items():
        if stats["count"] > 0:
            avg_savings = stats["total_savings"] / stats["count"]
            print(f"{store}: {avg_savings:.2f}% savings over {stats['count']} comparisons")
        else:
            print(f"{store}: No comparisons")
