"""
promote.py — Promote best autoresearch model to production.

Reads: autoresearch/experiments/summary.jsonl for best AUROC
Writes: src/prediction/ module with inference wrapper

Not yet implemented — run experiments first, then build this.

The promotion workflow will:
1. Load the best experiment from experiments/summary.jsonl
2. Retrain on train+val combined (now that we've selected the approach)
3. Save the model artifact to src/prediction/
4. Generate a prediction function that the API can import
5. Optionally run against the held-out 2024 test set for final validation
"""
# TODO: Implement after model quality threshold is determined from experimentation
