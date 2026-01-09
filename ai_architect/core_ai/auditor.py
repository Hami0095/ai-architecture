import os
import json
import ollama
from .prompts import DISCOVERY_SYSTEM_PROMPT, GAP_ANALYSIS_SYSTEM_PROMPT, TICKET_GENERATION_SYSTEM_PROMPT

class ArchitecturalAuditor:
    def __init__(self, model="qwen3-coder:480b-cloud"):
        self.model = model

    def scan_directory(self, root_path, max_depth=4) -> str:
        """
        Creates a text representation of the project structure and key file contents.
        """
        summary = f"Project Root: {root_path}\nStructure:\n"
        ignore_dirs = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build', '.idea', '.vscode'}
        relevant_extensions = {'.py', '.md', '.sql', '.yaml', '.yml', '.json', '.toml', '.env', 'Dockerfile', '.js', '.ts'}
        
        file_contents = ""
        
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            depth = root[len(root_path):].count(os.sep)
            if depth > max_depth:
                del dirs[:]
                continue
                
            level = root.replace(root_path, '').count(os.sep)
            indent = ' ' * 4 * level
            summary += f"{indent}{os.path.basename(root)}/\n"
            subindent = ' ' * 4 * (level + 1)
            
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in relevant_extensions or f in relevant_extensions:
                    summary += f"{subindent}{f}\n"
                    path = os.path.join(root, f)
                    try:
                        if ext in {'.py', '.sql', '.yaml', '.yml', '.toml', '.env', '.js', '.ts'} or f == 'Dockerfile':
                            with open(path, 'r', encoding='utf-8', errors='ignore') as file_obj:
                                content = file_obj.read()
                                if len(content) > 1500:
                                    content = content[:1000] + "\n...[TRUNCATED]...\n" + content[-500:]
                                file_contents += f"--- FILE: {os.path.relpath(path, root_path)} ---\n{content}\n\n"
                    except:
                        pass

        return summary + "\n\nKey File Contents:\n" + file_contents

    def _call_llm_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            response = ollama.chat(model=self.model, format='json', messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ])
            content = response['message']['content']
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            print(f"LLM JSON Error: {e}")
            return {}

    def _call_llm_text(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ])
            return response['message']['content']
        except Exception as e:
            print(f"LLM Text Error: {e}")
            return "Analysis failed."

    def audit_project(self, root_path: str, user_context: str = "", project_status: str = "", expected_output: str = "") -> dict:
        """
        Refactored multi-stage pipeline for ArchAI.
        """
        from ..data.models import AuditReport, AuditTicket
        from ..improvement_engine.planner import SprintPlanner
        
        print("\n[Stage 1/4] Discovery: Mapping codebase structure...")
        code_structure = self.scan_directory(root_path)
        discovery = self._call_llm_json(DISCOVERY_SYSTEM_PROMPT, f"Project Path: {root_path}\n\nCode Structure:\n{code_structure}")
        
        # Ensure discovery has required keys
        discovery.setdefault("languages", [])
        discovery.setdefault("frameworks", [])
        discovery.setdefault("architecture_type", "Unknown")

        if not discovery["languages"]:
            # Fallback heuristic if LLM misses it
            if ".py" in code_structure: discovery["languages"].append("python")
            if ".js" in code_structure: discovery["languages"].append("javascript")

        print(f"Found languages: {', '.join(discovery['languages'])}")

        print("\n[Stage 2/4] Gap Analysis: Comparing vs target goal...")
        gap_prompt = GAP_ANALYSIS_SYSTEM_PROMPT.format(
            discovery_data=json.dumps(discovery),
            user_context=user_context,
            project_status=project_status,
            expected_output=expected_output
        )
        gap_analysis = self._call_llm_text("You are an ArchAI Gap Analyzer.", gap_prompt)

        print("\n[Stage 3/4] Ticket Generation: Synthesizing roadmap items...")
        ticket_user_prompt = f"Discovery: {json.dumps(discovery)}\nGap Analysis: {gap_analysis}\nGenerate detailed tickets."
        tickets_data = self._call_llm_json(TICKET_GENERATION_SYSTEM_PROMPT, ticket_user_prompt)
        
        tickets = tickets_data.get("tickets", [])
        if not tickets:
             print("No tickets generated by LLM.")

        # Clean and validate tickets
        valid_tickets = []
        for t in tickets:
            if isinstance(t, dict):
                # Ensure defaults before Pydantic validation
                t.setdefault("title", "Proposed Improvement")
                t.setdefault("type", "Logic")
                t.setdefault("severity", "Medium")
                t.setdefault("priority", "Medium")
                t.setdefault("description", "No description provided.")
                t.setdefault("suggested_fix", "Consult the description for instructions.")
                t.setdefault("effort_hours", 2)
                t.setdefault("labels", [])
                
                try:
                    # Convert to Pydantic model for consistency and validation
                    ticket_obj = AuditTicket(**t)
                    valid_tickets.append(ticket_obj)
                except Exception as e:
                    print(f"Skipping invalid ticket: {e}")

        print(f"\n[Stage 4/4] Sprint Planning: Scheduling {len(valid_tickets)} tickets...")
        planner = SprintPlanner(hours_per_day=5.0, total_days=5)
        sprint_days = planner.plan_sprint(valid_tickets)

        # Build Final Report
        report_data = {
            "discovery": discovery,
            "gap_analysis": gap_analysis,
            "tickets": [t.model_dump(mode='json') for t in valid_tickets],
            "sprint_plan": [day.model_dump(mode='json') for day in sprint_days],
            "summary": f"ArchAI analyzed {len(discovery['languages'])} language(s). Found {len(valid_tickets)} actionable item(s)."
        }

        try:
            report = AuditReport(**report_data)
            return report.model_dump(mode='json')
        except Exception as e:
            print(f"Final Report Error: {e}")
            return report_data
