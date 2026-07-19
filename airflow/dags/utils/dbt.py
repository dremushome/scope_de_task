from airflow.sdk import task

def dbt_task(task_id: str, command: str = "run", select: str | None = None, exclude: str | None = None):
    """
    Helper function using modern TaskFlow @task.bash to execute a dbt command inside the container.
    """
    cmd = f"dbt {command} --profiles-dir /opt/airflow/dwh/dbt --project-dir /opt/airflow/dwh/dbt"
    if select:
        cmd += f" --select '{select}'"
    if exclude:
        cmd += f" --exclude '{exclude}'"
        
    @task.bash(task_id=task_id)
    def run_cmd():
        return cmd
        
    return run_cmd()
