import subprocess
import os
import re
from ..data.models import EvaluationMetric

class TestRunner:
    def __init__(self, temp_dir="temp_tests"):
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    def run_evaluation(self, run_id: str, test_code: str, target_file_path: str) -> EvaluationMetric:
        """
        Saves the test code, runs pytest, and extracts metrics.
        """
        test_file = os.path.join(self.temp_dir, f"test_{run_id}.py")
        
        # Write test code to file
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        valid_syntax = True
        try:
            compile(test_code, test_file, 'exec')
        except SyntaxError:
            valid_syntax = False

        tests_passed = False
        coverage_percent = 0.0
        details = {"output": "", "error": ""}

        if valid_syntax:
            # Run pytest with coverage
            # Assumes target file is importable or in path. 
            # We might need to adjust PYTHONPATH.
            target_dir = os.path.dirname(target_file_path)
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{target_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"

            cmd = [
                "pytest",
                test_file,
                f"--cov={target_file_path}",
                "--cov-report=term-missing" # Parse output for percentage
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                details["output"] = result.stdout
                details["error"] = result.stderr
                
                if result.returncode == 0:
                    tests_passed = True
                
                # Parse coverage from stdout
                # Pattern: "TOTAL ... 85%"
                cov_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", result.stdout)
                if cov_match:
                    coverage_percent = float(cov_match.group(1)) / 100.0
                
            except subprocess.TimeoutExpired:
                details["error"] = "Test execution timed out."
            except Exception as e:
                details["error"] = str(e)
        
        # cleanup if needed, or keep for debugging
        # os.remove(test_file)

        # Calculate Score: (Valid * 0.2) + (Pass * 0.3) + (Cov * 0.5)
        # If not valid, score is 0.
        score = 0.0
        if valid_syntax:
            score = 0.2 + (0.3 if tests_passed else 0.0) + (0.5 * coverage_percent)

        return EvaluationMetric(
            run_id=run_id,
            valid_syntax=valid_syntax,
            tests_passed=tests_passed,
            coverage_percent=coverage_percent,
            total_score=score,
            details=details
        )
