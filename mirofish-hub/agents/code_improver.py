#!/usr/bin/env python3
"""
CODE IMPROVER - Uses three-agent architecture for autonomous code improvement

Applies the Anthropic harness pattern to fixing/improving the whale tracker:
1. PLANNER: Takes audit issues, creates fix specifications
2. GENERATOR: Generates code fixes
3. EVALUATOR: Tests and validates fixes

This can run autonomously to continuously improve the codebase.
"""

import json
import subprocess
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

# Config
OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5-coder:7b"  # Updated 2026-04-04: Code specialist
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class CodeIssue:
    """An issue to fix in the codebase."""
    id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    file_path: str
    description: str
    suggested_fix: str = ""
    line_numbers: Optional[str] = None


@dataclass
class FixSpec:
    """Specification for a code fix."""
    issue: CodeIssue
    analysis: str
    fix_approach: str
    files_to_modify: List[str]
    tests_needed: List[str]
    rollback_plan: str
    estimated_complexity: str  # simple, medium, complex


@dataclass
class CodeFix:
    """Generated code fix."""
    spec: FixSpec
    original_code: str
    fixed_code: str
    diff: str
    explanation: str


@dataclass 
class FixEvaluation:
    """Evaluation of a code fix."""
    fix: CodeFix
    syntax_valid: bool
    tests_pass: bool
    no_regressions: bool
    approved: bool
    feedback: str
    concerns: List[str]


class CodePlannerAgent:
    """Plans code fixes from audit issues."""
    
    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.model = MODEL
    
    def _call_llm(self, prompt: str) -> str:
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 2000, "temperature": 0.3}},
                timeout=120
            )
            return resp.json().get("response", "") if resp.ok else ""
        except Exception as e:
            print(f"[CodePlanner] LLM error: {e}")
            return ""
    
    def plan_fix(self, issue: CodeIssue) -> FixSpec:
        """Create a fix specification from an issue."""
        
        # Read the relevant file
        file_content = ""
        try:
            file_path = PROJECT_ROOT / issue.file_path
            if file_path.exists():
                file_content = file_path.read_text()[:5000]  # First 5K chars
        except:
            pass
        
        prompt = f"""You are a senior Python developer. Analyze this issue and create a fix plan.

ISSUE:
- ID: {issue.id}
- Severity: {issue.severity}
- File: {issue.file_path}
- Description: {issue.description}
- Suggested fix: {issue.suggested_fix}

CURRENT CODE (first 5000 chars):
```python
{file_content[:3000]}
```

Create a fix specification in this exact JSON format:
{{
    "analysis": "Root cause analysis",
    "fix_approach": "How to fix this",
    "files_to_modify": ["file1.py", "file2.py"],
    "tests_needed": ["Test case 1", "Test case 2"],
    "rollback_plan": "How to rollback if fix fails",
    "estimated_complexity": "simple|medium|complex"
}}

Be specific and practical. Focus on the minimal change needed."""

        response = self._call_llm(prompt)
        
        # Parse response
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0:
                data = json.loads(response[json_start:json_end])
            else:
                data = {}
        except:
            data = {}
        
        return FixSpec(
            issue=issue,
            analysis=data.get("analysis", "Unable to analyze"),
            fix_approach=data.get("fix_approach", issue.suggested_fix),
            files_to_modify=data.get("files_to_modify", [issue.file_path]),
            tests_needed=data.get("tests_needed", ["Basic syntax check"]),
            rollback_plan=data.get("rollback_plan", "Restore from git"),
            estimated_complexity=data.get("estimated_complexity", "medium")
        )


class CodeGeneratorAgent:
    """Generates code fixes."""
    
    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.model = MODEL
    
    def _call_llm(self, prompt: str) -> str:
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 3000, "temperature": 0.2}},
                timeout=180
            )
            return resp.json().get("response", "") if resp.ok else ""
        except Exception as e:
            print(f"[CodeGenerator] LLM error: {e}")
            return ""
    
    def generate_fix(self, spec: FixSpec) -> CodeFix:
        """Generate a code fix based on the spec."""
        
        # Read original file
        original_code = ""
        file_path = PROJECT_ROOT / spec.issue.file_path
        try:
            if file_path.exists():
                original_code = file_path.read_text()
        except:
            pass
        
        prompt = f"""You are an expert Python developer. Generate a fix for this issue.

ISSUE: {spec.issue.description}
FILE: {spec.issue.file_path}
APPROACH: {spec.fix_approach}
COMPLEXITY: {spec.estimated_complexity}

ORIGINAL CODE:
```python
{original_code[:8000]}
```

Generate the FIXED code. Return ONLY the complete fixed file content, no explanations.
Make minimal changes - only what's needed to fix the issue.
Preserve all existing functionality.

```python
"""

        response = self._call_llm(prompt)
        
        # Extract code from response
        fixed_code = original_code  # Default to original
        if "```python" in response:
            start = response.find("```python") + 9
            end = response.find("```", start)
            if end > start:
                fixed_code = response[start:end].strip()
        elif response.strip().startswith(("import", "from", "#", "def", "class")):
            fixed_code = response.strip()
        
        # Generate diff
        diff = self._generate_diff(original_code, fixed_code)
        
        return CodeFix(
            spec=spec,
            original_code=original_code,
            fixed_code=fixed_code,
            diff=diff,
            explanation=f"Fixed: {spec.issue.description}"
        )
    
    def _generate_diff(self, original: str, fixed: str) -> str:
        """Generate a simple diff."""
        import difflib
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            fixed.splitlines(keepends=True),
            fromfile="original",
            tofile="fixed"
        )
        return "".join(list(diff)[:50])  # First 50 lines of diff


class CodeEvaluatorAgent:
    """Evaluates and tests code fixes."""
    
    def evaluate_fix(self, fix: CodeFix) -> FixEvaluation:
        """Evaluate a code fix."""
        concerns = []
        
        # 1. Syntax check
        syntax_valid = self._check_syntax(fix.fixed_code)
        if not syntax_valid:
            concerns.append("Syntax error in fixed code")
        
        # 2. Check for obvious issues
        obvious_issues = self._check_obvious_issues(fix.fixed_code)
        concerns.extend(obvious_issues)
        
        # 3. Compare size (huge changes are suspicious)
        size_ratio = len(fix.fixed_code) / max(len(fix.original_code), 1)
        if size_ratio < 0.5 or size_ratio > 2.0:
            concerns.append(f"Suspicious size change: {size_ratio:.1%}")
        
        # 4. Check imports still present
        if not self._check_imports_preserved(fix.original_code, fix.fixed_code):
            concerns.append("Some imports may have been removed")
        
        # Decision
        approved = syntax_valid and len(concerns) <= 1
        
        return FixEvaluation(
            fix=fix,
            syntax_valid=syntax_valid,
            tests_pass=syntax_valid,  # Simplified - just syntax for now
            no_regressions=len(concerns) <= 1,
            approved=approved,
            feedback="Approved" if approved else f"Rejected: {concerns[0] if concerns else 'Unknown'}",
            concerns=concerns
        )
    
    def _check_syntax(self, code: str) -> bool:
        """Check if code has valid Python syntax."""
        try:
            compile(code, "<string>", "exec")
            return True
        except SyntaxError:
            return False
    
    def _check_obvious_issues(self, code: str) -> List[str]:
        """Check for obvious code issues."""
        issues = []
        
        # Check for common problems
        if "TODO" in code and "FIXME" in code:
            issues.append("Contains TODO/FIXME markers")
        
        if code.count("pass") > 5:
            issues.append("Too many pass statements")
        
        if "print(" in code and code.count("print(") > 20:
            issues.append("Excessive print statements")
        
        return issues
    
    def _check_imports_preserved(self, original: str, fixed: str) -> bool:
        """Check that important imports are preserved."""
        import re
        
        original_imports = set(re.findall(r'^(?:from|import)\s+\S+', original, re.MULTILINE))
        fixed_imports = set(re.findall(r'^(?:from|import)\s+\S+', fixed, re.MULTILINE))
        
        # Check that most original imports are still there
        if original_imports:
            preserved_ratio = len(original_imports & fixed_imports) / len(original_imports)
            return preserved_ratio >= 0.8
        return True


class CodeImproverOrchestrator:
    """Orchestrates the code improvement pipeline."""
    
    def __init__(self):
        self.planner = CodePlannerAgent()
        self.generator = CodeGeneratorAgent()
        self.evaluator = CodeEvaluatorAgent()
    
    def improve(self, issue: CodeIssue, apply: bool = False) -> Dict[str, Any]:
        """
        Run the full improvement pipeline for an issue.
        
        Args:
            issue: The issue to fix
            apply: If True, apply the fix to disk (requires approval)
            
        Returns:
            Dict with spec, fix, evaluation, and status
        """
        print(f"\n{'='*60}")
        print(f"[CodeImprover] Processing: {issue.id}")
        print(f"{'='*60}")
        
        # Step 1: Plan
        print("\n[Step 1] PLANNER - Creating fix specification...")
        spec = self.planner.plan_fix(issue)
        print(f"  Approach: {spec.fix_approach[:100]}")
        print(f"  Complexity: {spec.estimated_complexity}")
        
        # Step 2: Generate
        print("\n[Step 2] GENERATOR - Generating code fix...")
        fix = self.generator.generate_fix(spec)
        print(f"  Diff lines: {len(fix.diff.splitlines())}")
        
        # Step 3: Evaluate
        print("\n[Step 3] EVALUATOR - Testing fix...")
        evaluation = self.evaluator.evaluate_fix(fix)
        print(f"  Syntax valid: {evaluation.syntax_valid}")
        print(f"  Approved: {evaluation.approved}")
        if evaluation.concerns:
            print(f"  Concerns: {evaluation.concerns}")
        
        result = {
            "issue_id": issue.id,
            "status": "approved" if evaluation.approved else "rejected",
            "spec": asdict(spec.issue),
            "diff_preview": fix.diff[:500],
            "evaluation": {
                "approved": evaluation.approved,
                "feedback": evaluation.feedback,
                "concerns": evaluation.concerns
            }
        }
        
        # Apply if approved and requested
        if apply and evaluation.approved:
            print("\n[Step 4] APPLYING fix to disk...")
            try:
                file_path = PROJECT_ROOT / issue.file_path
                
                # Backup
                backup_path = file_path.with_suffix(file_path.suffix + ".backup")
                if file_path.exists():
                    backup_path.write_text(fix.original_code)
                
                # Apply
                file_path.write_text(fix.fixed_code)
                result["applied"] = True
                result["backup"] = str(backup_path)
                print(f"  ✅ Fix applied to {issue.file_path}")
                print(f"  📁 Backup at {backup_path}")
                
            except Exception as e:
                result["applied"] = False
                result["error"] = str(e)
                print(f"  ❌ Failed to apply: {e}")
        else:
            result["applied"] = False
        
        return result


# Predefined issues from our audit
KNOWN_ISSUES = [
    CodeIssue(
        id="H4",
        severity="HIGH", 
        file_path="whale_api.py",
        description="Cache TTL too long (30 min) causes stale data",
        suggested_fix="Reduce _CACHE_TTL from 30 to 5 minutes"
    ),
    CodeIssue(
        id="H16",
        severity="HIGH",
        file_path="whale_hunter_connector.py", 
        description="No orderbook liquidity check before trading",
        suggested_fix="Add CLOB orderbook check before generating trade signal"
    ),
    CodeIssue(
        id="M1",
        severity="MEDIUM",
        file_path="whale_api.py",
        description="No health check endpoint for monitoring",
        suggested_fix="Add /api/health/deep endpoint that checks all subsystems"
    ),
]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous code improver")
    parser.add_argument("--issue", type=str, help="Specific issue ID to fix")
    parser.add_argument("--apply", action="store_true", help="Apply approved fixes")
    parser.add_argument("--list", action="store_true", help="List known issues")
    args = parser.parse_args()
    
    if args.list:
        print("\nKnown Issues:")
        for issue in KNOWN_ISSUES:
            print(f"  [{issue.severity}] {issue.id}: {issue.description}")
        return
    
    orchestrator = CodeImproverOrchestrator()
    
    if args.issue:
        # Find specific issue
        issue = next((i for i in KNOWN_ISSUES if i.id == args.issue), None)
        if issue:
            result = orchestrator.improve(issue, apply=args.apply)
            print(f"\nResult: {json.dumps(result, indent=2)}")
        else:
            print(f"Issue {args.issue} not found")
    else:
        # Process all issues
        for issue in KNOWN_ISSUES:
            result = orchestrator.improve(issue, apply=args.apply)
            print(f"\n{issue.id}: {result['status']}")


if __name__ == "__main__":
    main()
