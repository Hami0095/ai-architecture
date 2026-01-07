import os
import json
import ollama
from .prompts import AUDITOR_SYSTEM_PROMPT

class ArchitecturalAuditor:
    def __init__(self, model="gemma3:1b"):
        self.model = model

    def scan_directory(self, root_path, max_depth=2) -> str:
        """
        Creates a text representation of the project structure and key file contents.
        Truncates content to fit into context.
        """
        summary = f"Project Root: {root_path}\nStructure:\n"
        
        for root, dirs, files in os.walk(root_path):
            # Simple depth check
            depth = root[len(root_path):].count(os.sep)
            if depth > max_depth:
                del dirs[:] 
                continue
                
            level = root.replace(root_path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            summary += f"{indent}{os.path.basename(root)}/\n"
            subindent = ' ' * 4 * (level + 1)
            
            for f in files:
                if f.endswith('.py') or f.endswith('.md') or f.endswith('.txt'):
                    summary += f"{subindent}{f}\n"

        # Now add some content sample (naive approach for now)
        summary += "\n\nKey File Contents (Truncated):\n"
        for root, dirs, files in os.walk(root_path):
            for f in files:
                if f.endswith('.py'):
                     path = os.path.join(root, f)
                     try:
                         with open(path, 'r', encoding='utf-8') as file_obj:
                             content = file_obj.read()
                             if len(content) > 1000:
                                 content = content[:1000] + "...[TRUNCATED]"
                             summary += f"--- FILE: {f} ---\n{content}\n\n"
                     except:
                         pass
        return summary

    def audit_project(self, root_path: str, user_context: str = "", project_status: str = "", expected_output: str = "") -> dict:
        """
        Scans the project and returns a list of architectural tickets.
        """
        code_structure = self.scan_directory(root_path)
        
        prompt = f"""
        Analyze the following project.
        
        USER CONTEXT:
        {user_context if user_context else "None provided."}

        PROJECT STATUS:
        {project_status if project_status else "None provided."}

        EXPECTED OUTPUT/PLAN:
        {expected_output if expected_output else "Standard architectural audit."}

        CODE STRUCTURE & CONTENT:
        {code_structure}
        
        Based on the code structure AND the user's context/expectations, identify flaws and generate JSON tickets.
        """
        
        print("\nAuditor: Analyzing project structure... (This may take a moment)")
        
        try:
            response = ollama.chat(model=self.model, format='json', messages=[
                {'role': 'system', 'content': AUDITOR_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ])
            
            content = response['message']['content']
            # Basic cleanup for JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            return json.loads(content)
            
        except Exception as e:
            print(f"Auditor Error: {e}")
            return {"tickets": []}
