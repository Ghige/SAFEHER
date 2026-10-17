# AI Retraining Gates

**This repository does not start training.** `retraining_gate.py --approve-train` is ignored.

## Pipeline (future, manual)

1. Candidate data  
2. Human review  
3. Gold dataset  
4. Minimum-count checks (500 DISTRESS, 1000 HARD_NEGATIVE)  
5. Leakage checks (same `event_id` / `source_id` must not appear in train and test)  
6. License checks (`SAFE`, `ATTRIBUTION_REQUIRED`, or `USER_CONSENT_OPT_IN`)  
7. Retraining **approval** (human)  
8. Training (offline job; existing weights untouched until then)  
9. Frozen evaluation  
10. Model comparison vs current production artifacts  
11. Model versioning  
12. Manual approval  
13. Deployment  

Existing model files must remain on disk for **rollback**.

## Gate run (2026-09-16, this tree)

| Field | Value | Status |
|-------|--------|--------|
| automatic_retrain | false | **VERIFIED** |
| training_executed | false | **VERIFIED** |
| approved_to_train | false | **VERIFIED** |
| total_DISTRESS | 0 | below 500 |
| total_HARD_NEGATIVE | 0 | below 1000 |
| ready_to_consider_training | false | **VERIFIED** |
| process exit | 2 TRAINING FORBIDDEN | **VERIFIED** |

## Command

```bat
cd safeher_ai\training
python retraining_gate.py
```

Do not run `train_*.py` until this gate prints `ready_to_consider_training: true` **and** a human signs an offline training ticket.
