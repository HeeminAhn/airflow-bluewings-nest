from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _print_hello():
    print("Hello from Airflow!")
    return "Hello!"


with DAG(
    dag_id="example_dag",
    default_args=default_args,
    description="A simple example DAG",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["example"],
) as dag:

    start = BashOperator(
        task_id="start",
        bash_command="echo 'Starting pipeline'",
    )

    hello = PythonOperator(
        task_id="hello_task",
        python_callable=_print_hello,
    )

    end = BashOperator(
        task_id="end",
        bash_command="echo 'Pipeline complete'",
    )

    start >> hello >> end
