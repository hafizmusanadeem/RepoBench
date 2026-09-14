from pathlib import Path
import subprocess


class CodingAgent:

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def run_command(
        self,
        command: list[str],
    ) -> str:

        result = subprocess.run(
            command,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        return (
            result.stdout
            + "\n"
            + result.stderr
        )

    def inspect_repo(self):

        output = self.run_command(
            ["git", "status"]
        )

        print(output)

    def run_tests(self):

        output = self.run_command(
            ["pytest", "-q"]
        )

        print(output)

    def modify_repository(self):

        # Your LLM agent will eventually
        # decide which files to modify.
        pass

    def run(self, task: str):

        print("TASK:")
        print(task)

        print("\nRepository:")
        print(self.repo_path)

        self.inspect_repo()
        self.run_tests()