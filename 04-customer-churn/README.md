# Lab 04 — Customer Churn with Kubeflow Pipelines

Inspired by Ivan Mushket's `Building-Machine-Learning-Pipelines-on-AWS` (S04-L07). Implements the **same synthetic AWS telecom churn use case** with Kubernetes-native KFP artifacts, a Decision Tree model, a validation quality gate, and independent holdout evaluation. This is an adaptation, not an unchanged reproduction of the SageMaker notebook.

## 1. Setup and compile

```bash
cd /home/ubuntu/kubeflow-mlops-lab
mkdir -p 04-customer-churn
# Copy 01_customer_churn_pipeline.py into 04-customer-churn/
uv run python 04-customer-churn/01_customer_churn_pipeline.py
ls -lh 04-customer-churn/pipeline.yaml
```

## 2. Submit

In one SSH session:

```bash
kubectl -n kubeflow port-forward svc/ml-pipeline 8888:8888
```

In a second SSH session:

```bash
cd /home/ubuntu/kubeflow-mlops-lab
uv run python - <<'PY'
from kfp import Client
client = Client(host='http://127.0.0.1:8888')
run = client.create_run_from_pipeline_package(
    pipeline_file='04-customer-churn/pipeline.yaml',
    arguments={
        'max_depth': 5,
        'min_samples_split': 2,
        'random_state': 42,
        'min_accuracy': 0.85,
    },
    experiment_name='customer-churn-kfp',
    run_name='churn-decision-tree-depth-5',
)
print('Run ID:', run.run_id)
PY
```

## 3. Observe

```bash
kubectl -n kubeflow get workflows.argoproj.io
kubectl -n kubeflow get pods -w
# Only if problems
kubectl -n kubeflow get events --sort-by=.lastTimestamp | tail -30
```

Open the KFP UI using existing secure port-forward (e.g., EC2 `kubectl -n kubeflow port-forward svc/ml-pipeline-ui 8080:80` and SSH port tunnel). Find the experiment and view `prepare-churn-data`, `train-churn-model`, `evaluate-churn-model` (validation), `validate-model`, and `evaluate-churn-model` (test). Check dataset/model artifacts, confusion-matrix counts and precision/recall/F1 metrics.

## 4. Compare runs

Repeat with `max_depth=9` and a distinct `run_name`; compare validation and holdout metrics. Optionally increase `min_accuracy` to force a deliberate quality-gate rejection.

## 5. Commit

```bash
git add 04-customer-churn/
git commit -m 'feat(kubeflow): train and validate customer churn model with KFP artifacts'
git push origin HEAD
```

## Notes
- Dataset: official AWS synthetic telecom churn sample (`churn.txt`), downloaded by the preparation task over HTTPS.
- Requires outbound HTTPS from the KFP component Pod. If the source gives 403/404, pass a working `data_url` at run submission; the original course used `s3://sagemaker-sample-files/datasets/tabular/synthetic/churn.txt`.
- `pipeline_root` is `minio://mlpipeline/v2/artifacts` to use the current SeaweedFS-backed standalone KFP setup.
- The `0.85` accuracy gate matches the teaching objective, but **accuracy alone is insufficient** for imbalanced churn. Compare `precision`, `recall`, `f1`, and the majority-class baseline in the UI.
- The test split is not consulted until validation approval; this avoids using the holdout to make model-selection decisions.
- No model registration or serving is performed; those belong in later labs.
