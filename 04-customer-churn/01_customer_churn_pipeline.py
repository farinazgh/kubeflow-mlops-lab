"""Synthetic telecom churn -> train/validation/test -> scikit-learn Decision Tree
-> validation metrics -> quality gate -> independent holdout evaluation.
"""

from pathlib import Path

from kfp import compiler, dsl
from kfp.dsl import Dataset, Input, Metrics, Model, Output

# s3://sagemaker-sample-files/datasets/tabular/synthetic/churn.txt
# AWS also publishes the synthetic data in region-specific sample buckets.
DEFAULT_DATA_URL = (
    "https://sagemaker-example-files-prod-eu-west-1.s3.eu-west-1.amazonaws.com/"
    "datasets/tabular/synthetic/churn.txt"
)


# 1 — INGEST AND SPLIT
# Output[Dataset] tells KFP these files are ML dataset artifacts, not scalars.
@dsl.component(
    base_image="python:3.12-slim",
    packages_to_install=["pandas==2.2.3", "scikit-learn==1.6.1"],
)
def prepare_churn_data(
    train_dataset: Output[Dataset],
    validation_dataset: Output[Dataset],
    test_dataset: Output[Dataset],
    data_url: str,
    random_state: int = 42,
):
    from io import BytesIO
    from urllib.request import urlopen

    import pandas as pd
    from sklearn.model_selection import train_test_split

    # The original SageMaker course downloads the same AWS synthetic churn data.
    with urlopen(data_url, timeout=90) as response:
        raw = response.read()
    df = pd.read_csv(BytesIO(raw))

    if "Churn?" not in df.columns:
        raise ValueError(f"Expected 'Churn?' column; got {list(df.columns)}")

    # Avoid memorizing a customer identifier, and normalize target labels.
    df = df.drop(columns=["Phone"], errors="ignore")
    labels = {
        "false.": 0,
        "true.": 1,
        "false": 0,
        "true": 1,
        "0": 0,
        "1": 1,
    }
    df["churn"] = df.pop("Churn?").astype(str).str.strip().str.lower().map(labels)
    if df["churn"].isna().any():
        raise ValueError("Churn target contains unexpected labels")
    df["churn"] = df["churn"].astype(int)

    # Area Code is categorical even though it is numerically encoded.
    if "Area Code" in df:
        df["Area Code"] = df["Area Code"].astype(str)

    # Independent, stratified 60/20/20 splits. Keep test untouched until approval.
    train, remainder = train_test_split(
        df, test_size=0.4, random_state=random_state, stratify=df["churn"]
    )
    validation, test = train_test_split(
        remainder,
        test_size=0.5,
        random_state=random_state,
        stratify=remainder["churn"],
    )

    for frame, artifact, split in [
        (train, train_dataset, "train"),
        (validation, validation_dataset, "validation"),
        (test, test_dataset, "test"),
    ]:
        frame.to_csv(artifact.path, index=False)
        artifact.metadata["split"] = split
        artifact.metadata["rows"] = len(frame)
        artifact.metadata["churn_rate"] = float(frame["churn"].mean())
        artifact.metadata["source"] = data_url
        print(f"{split}: {len(frame)} rows, churn={frame['churn'].mean():.3f}")


# 2 — TRAIN A SINGLE MODEL
# Preprocessing is fitted on training data only, then stored WITH the model.
@dsl.component(
    base_image="python:3.12-slim",
    packages_to_install=["pandas==2.2.3", "scikit-learn==1.6.1", "joblib==1.4.2"],
)
def train_churn_model(
    train_dataset: Input[Dataset],
    trained_model: Output[Model],
    max_depth: int = 5,
    min_samples_split: int = 2,
    random_state: int = 42,
):
    import joblib
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.tree import DecisionTreeClassifier

    frame = pd.read_csv(train_dataset.path)
    X = frame.drop(columns=["churn"])
    y = frame["churn"].astype(int)
    if "Area Code" in X:
        X["Area Code"] = X["Area Code"].astype(str)

    categoricals = X.select_dtypes(include=["object", "string"]).columns.tolist()
    numerics = [column for column in X.columns if column not in categoricals]

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categoricals),
            ("numeric", "passthrough", numerics),
        ]
    )
    model = Pipeline(
        [
            ("preprocessing", preprocessor),
            (
                "classifier",
                DecisionTreeClassifier(
                    max_depth=max_depth,
                    min_samples_split=min_samples_split,
                    random_state=random_state,
                ),
            ),
        ]
    )
    model.fit(X, y)
    joblib.dump(model, trained_model.path)

    trained_model.metadata["framework"] = "scikit-learn"
    trained_model.metadata["algorithm"] = "DecisionTreeClassifier"
    trained_model.metadata["max_depth"] = max_depth
    trained_model.metadata["min_samples_split"] = min_samples_split
    print(f"Saved model from {len(frame)} training samples")


# 3 and 5 — EVALUATION
# This component is reused for validation and the independent holdout test.
# Metrics are first-class KFP artifacts; accuracy is also a scalar for the gate.
@dsl.component(
    base_image="python:3.12-slim",
    packages_to_install=["pandas==2.2.3", "scikit-learn==1.6.1", "joblib==1.4.2"],
)
def evaluate_churn_model(
    dataset: Input[Dataset],
    trained_model: Input[Model],
    metrics: Output[Metrics],
    split_name: str,
) -> float:
    import joblib
    import pandas as pd
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )

    frame = pd.read_csv(dataset.path)
    X = frame.drop(columns=["churn"])
    y = frame["churn"].astype(int)
    if "Area Code" in X:
        X["Area Code"] = X["Area Code"].astype(str)

    model = joblib.load(trained_model.path)  # Only load trusted model artifacts.
    predictions = model.predict(X)

    scores = {
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "majority_baseline_accuracy": float(max(y.mean(), 1 - y.mean())),
    }
    tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    scores.update({"tn": float(tn), "fp": float(fp), "fn": float(fn), "tp": float(tp)})
    for name, value in scores.items():
        metrics.log_metric(name, value)
    metrics.metadata["split"] = split_name
    print(f"{split_name} evaluation: {scores}")
    return scores["accuracy"]


# 4 — VALIDATION QUALITY GATE
# The held-out test task runs only after this succeeds.
@dsl.component(base_image="python:3.12-slim")
def validate_model(accuracy: float, min_accuracy: float = 0.85) -> str:
    if accuracy < min_accuracy:
        raise ValueError(
            f"REJECTED: validation accuracy {accuracy:.3f} < {min_accuracy:.3f}"
        )
    decision = f"APPROVED: validation accuracy {accuracy:.3f} >= {min_accuracy:.3f}"
    print(decision)
    return decision


# PIPELINE DEFINITION — task references create a dependency DAG.
@dsl.pipeline(
    name="customer-churn-decision-tree",
    description="Synthetic customer churn: preparation, training, validation, gate, holdout",
    pipeline_root="minio://mlpipeline/v2/artifacts",
)
def churn_pipeline(
    data_url: str = DEFAULT_DATA_URL,
    random_state: int = 42,
    max_depth: int = 5,
    min_samples_split: int = 2,
    min_accuracy: float = 0.85,
) -> float:
    prepared = prepare_churn_data(data_url=data_url, random_state=random_state)

    trained = train_churn_model(
        train_dataset=prepared.outputs["train_dataset"],
        max_depth=max_depth,
        min_samples_split=min_samples_split,
        random_state=random_state,
    )

    validated = evaluate_churn_model(
        dataset=prepared.outputs["validation_dataset"],
        trained_model=trained.outputs["trained_model"],
        split_name="validation",
    )

    approved = validate_model(
        accuracy=validated.outputs["Output"],
        min_accuracy=min_accuracy,
    )

    holdout = evaluate_churn_model(
        dataset=prepared.outputs["test_dataset"],
        trained_model=trained.outputs["trained_model"],
        split_name="test",
    )
    holdout.after(approved)

    # Force new Pods instead of cached task outputs for the learning exercise.
    for task in (prepared, trained, validated, approved, holdout):
        task.set_caching_options(False)

    return holdout.outputs["Output"]


if __name__ == "__main__":
    output_path = Path(__file__).resolve().parent / "pipeline.yaml"
    compiler.Compiler().compile(churn_pipeline, package_path=str(output_path))
    print(f"Compiled KFP pipeline: {output_path}")
