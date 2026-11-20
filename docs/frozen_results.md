# Frozen Research Results

Evaluation period: November 2026

## Dataset summary

| Dataset | ANSWER | ESCALATE | Total |
|---|---:|---:|---:|
| Real development | 55 | 662 | 717 |
| Synthetic development | 200 | 100 | 300 |
| Total development | 255 | 762 | 1017 |
| Protected real test | 25 | 175 | 200 |

## Selected model

- Algorithm: XGBoost
- Feature configuration: D
- Training strategy: Real-only
- Class weighting: Unweighted
- Random seed: 42
- Decision threshold: 0.7423206567764282
- Knowledge base: 20261116T084302Z

## Classifier performance

| Metric | Development OOF | Protected test |
|---|---:|---:|
| Accuracy | 94.56% | 89.00% |
| ANSWER precision | 90.00% | 80.00% |
| ANSWER recall | 32.73% | 16.00% |
| ESCALATE recall | 99.70% | 99.43% |
| Macro F1 | 0.7257 | 0.6036 |
| ROC AUC | 0.9520 | 0.9687 |
| Average precision | 0.6429 | 0.7353 |
| Answer coverage | 2.79% | 2.50% |

## Confusion matrices

ANSWER is the positive class.

| Dataset | TP | FP | TN | FN |
|---|---:|---:|---:|---:|
| Development OOF | 18 | 2 | 660 | 37 |
| Protected test | 4 | 1 | 174 | 21 |

## Protected test acceptance criteria

| Criterion | Target | Observed | Outcome |
|---|---:|---:|---|
| ANSWER precision | >=90% | 80.00% | Not met |
| ESCALATE recall | >=95% | 99.43% | Met |
| Minimum predicted answers | 10 | 5 | Not met |

The always-escalate baseline achieved 87.5% accuracy
on the protected test.

## Integrated functional evaluation

| Metric | Result |
|---|---:|
| Functional challenge cases | 30 |
| Privacy-blocked cases | 2 |
| Authorized cases | 28 |
| Cases completing classification | 23 |
| Handled extraction rate-limit failures | 5 |
| Final true positives | 1 |
| Final false positives | 0 |
| Final true negatives, authorized | 13 |
| Final false negatives | 14 |
| Authorized accuracy | 50.00% |
| Authorized ANSWER recall | 6.67% |
| Authorized answer coverage | 3.57% |

Technical failures are included in observed final decisions
but must not be interpreted as successful intelligent
classification.

## Interpretation

The framework demonstrates strong classifier ranking
performance and high escalation recall.

However, low automated answer coverage, unmet protected
precision criteria and external API failures limit its
readiness for autonomous deployment.

The absence of unsupported final answers in the small
functional challenge set does not establish complete safety.

## Software validation

- 36 root-level Python scripts passed syntax validation.
- Core application imports passed.
- 16 existing unit tests passed.
- Local API integration checks passed.
- Docker deployment and smoke checks passed.
- Three intermediate datasets were reproduced with
  identical data content.
- Knowledge base relocation testing passed.

## Research notebook preservation

Original executed notebooks are retained locally in a
restricted archive.

Repository versions exclude saved cell outputs to reduce
the risk of disclosure of customer-level information.

The original experimental results and serialized model
have been preserved without retraining.
