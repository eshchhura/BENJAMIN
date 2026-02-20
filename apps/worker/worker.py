from core.orchestration.executor import Executor


class Worker:
    def __init__(self) -> None:
        self.executor = Executor()

    def run_once(self, task: str) -> str:
        return self.executor.execute(task)
