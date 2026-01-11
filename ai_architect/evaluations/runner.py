import subprocess
import os
import json
from pathlib import Path
from ..data.models import EvaluationMetric

class EvaluationRunner:
    def __init__(self):
        self.temp_dir = Path("temp_tests")
        self.temp_dir.mkdir(exist_ok=True)
        self.temp_test_file = self.temp_dir / "test_generated.py"

    def evaluate(self, target_code: str, test_code: str) -> EvaluationMetric:
        target_file_path = Path("temp_target.py")
        target_file_path.write_text(target_code)
        return self.run_evaluation("manual_run", test_code, str(target_file_path))

    def run_evaluation(self, run_id: str, test_code: str, target_file_path: str) -> EvaluationMetric:
        """
        Runs the generated tests and calculates metrics.
        """
        # 1. Write tests to file
        with open(self.temp_test_file, "w") as f:
            f.write(test_code)

        # 2. Check syntax
        valid_syntax = self._check_syntax(self.temp_test_file)
        if not valid_syntax:
            return EvaluationMetric(
                run_id=run_id,
                valid_syntax=False,
                tests_passed=False,
                coverage_percent=0.0,
                total_score=0.2, # Minimum score for trying
                details={"error": "Syntax Error in generated tests"}
            )

        # 3. Run pytest with coverage
        try:
            cmd = [
                "pytest", 
                "--cov=" + target_file_path, 
                "--cov-report=json",
                str(self.temp_test_file)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 4. Parse Coverage
            coverage = 0.0
            if os.path.exists(".coverage"):
                subprocess.run(["coverage", "json"], capture_output=True)
                if os.path.exists("coverage.json"):
                    with open("coverage.json", "r") as f:
                        cov_data = json.load(f)
                        # Normalize path for comparison
                        target_name = os.path.basename(target_file_path)
                        for path, data in cov_data['files'].items():
                            if Path(path).name == target_name:
                                coverage = data['summary']['percent_covered'] / 100.0
                                break
            
            tests_passed = result.returncode == 0
            total_score = (0.4 if tests_passed else 0.0) + (0.6 * coverage)
            
            return EvaluationMetric(
                run_id=run_id,
                valid_syntax=True,
                tests_passed=tests_passed,
                coverage_percent=coverage,
                total_score=total_score,
                details={
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            )
            
        except Exception as e:
            return EvaluationMetric(
                run_id=run_id,
                valid_syntax=True,
                tests_passed=False,
                coverage_percent=0.0,
                total_score=0.0,
                details={"error": str(e)}
            )

    def _check_syntax(self, file_path):
        try:
            with open(file_path, 'r') as f:
                compile(f.read(), file_path, 'exec')
            return True
        except:
            return False
