from kfp import compiler, dsl, local
from pathlib import Path

# COMPONENT DEFINITIONS
# Lightweight Python components: KFP packages each function for containerized
# execution without requiring us to build a custom Docker image.


@dsl.component(base_image="python:3.12-slim")
def generate_number(seed: int) -> int:
    return seed * 2


@dsl.component(base_image="python:3.12-slim")
def square_number(value: int) -> int:
    return value**2


# PIPELINE ORCHESTRATION
# Define the DAG: component calls create tasks, and their output references
# establish data dependencies and execution order.


@dsl.pipeline(name="first-kubeflow-pipeline")
def first_pipeline(seed: int = 3) -> int:
    generated = generate_number(seed=seed)
    squared = square_number(value=generated.output)

    return squared.output


if __name__ == "__main__":
    # COMPILATION
    # Resolve the output relative to this script, independently of the working directory.
    pipeline_path = Path(__file__).resolve().parent / "pipeline.yaml"

    compiler.Compiler().compile(
        first_pipeline,
        package_path=str(pipeline_path),
    )

    print(f"Pipeline compiled successfully: {pipeline_path}")

    # LOCAL EXECUTION
    # Execute components as local Python subprocesses for rapid validation.
    # No Kubernetes cluster or container runtime is involved in this mode.
    local.init(runner=local.SubprocessRunner(use_venv=False))

    result = first_pipeline(seed=3)

    # VALIDATION
    # Verify component dataflow: 3 -> 6 -> 36.
    assert result.output == 36
    print(f"Local pipeline result: {result.output}")
