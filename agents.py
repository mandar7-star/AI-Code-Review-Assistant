from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, List, Any, TypedDict, Optional
import json
import os
import re

from reviewers import CodeReviewer

try:
    from chroma_store import CodePatternStore
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False
    print("⚠️ chroma_store not available. Running without ChromaDB.")

class ReviewState(TypedDict):
    code: str
    language: str
    review_types: Dict[str, bool]
    file_path: str
    bugs: List[Dict]
    security_issues: List[Dict]
    performance_issues: List[Dict]
    style_issues: List[Dict]
    ai_analysis: str
    similar_patterns: List[Dict]
    refactoring_suggestions: List[Dict]
    final_report: Dict[str, Any]

class CodeReviewOrchestrator:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        self.llm = None
        if api_key:
            try:
                self.llm = ChatGroq(
                    api_key=api_key,
                    model="mixtral-8x7b-32768",
                    temperature=0.1
                )
                print("✓ LLM initialized")
            except Exception as e:
                print(f"✗ LLM error: {e}")
        else:
            print("⚠️ GROQ_API_KEY not set")
        
        self.reviewer = CodeReviewer()
        self.chroma_store = CodePatternStore() if HAS_CHROMA else None
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
        print("✓ LangGraph workflow compiled")
    
    def _build_workflow(self):
        workflow = StateGraph(ReviewState)
        
        workflow.add_node("code_understanding", self.code_understanding_agent)
        workflow.add_node("bug_detection", self.bug_detection_agent)
        workflow.add_node("security_analysis", self.security_agent)
        workflow.add_node("performance_analysis", self.performance_agent)
        workflow.add_node("style_analysis", self.style_agent)
        workflow.add_node("similar_patterns", self.similar_patterns_agent)
        workflow.add_node("refactoring", self.refactoring_agent)
        workflow.add_node("report_generation", self.report_agent)
        
        workflow.set_entry_point("code_understanding")
        
        # Sequential execution to avoid concurrent writes
        workflow.add_edge("code_understanding", "bug_detection")
        workflow.add_edge("bug_detection", "security_analysis")
        workflow.add_edge("security_analysis", "performance_analysis")
        workflow.add_edge("performance_analysis", "style_analysis")
        workflow.add_edge("style_analysis", "similar_patterns")
        workflow.add_edge("similar_patterns", "refactoring")
        workflow.add_edge("refactoring", "report_generation")
        workflow.add_edge("report_generation", END)
        
        return workflow
    
    def code_understanding_agent(self, state: ReviewState) -> ReviewState:
        state["ai_analysis"] = ""
        
        if self.llm and len(state["code"]) < 3000:
            try:
                prompt = ChatPromptTemplate.from_template("""
                Analyze this {language} code and provide:
                1. What the code does (1-2 sentences)
                2. Its overall complexity (Low/Medium/High)
                3. The main purpose of the code
                
                Code:
                {code}
                """)
                response = self.llm.invoke(prompt.format(
                    language=state["language"],
                    code=state["code"][:2000]
                ))
                state["ai_analysis"] = response.content
            except Exception as e:
                print(f"LLM error: {e}")
        
        return state
    
    def bug_detection_agent(self, state: ReviewState) -> ReviewState:
        if not state["review_types"].get("bugs", True):
            return state
        
        bugs = self.reviewer.find_bugs(state["code"], state["language"])
        state["bugs"] = bugs
        return state
    
    def security_agent(self, state: ReviewState) -> ReviewState:
        if not state["review_types"].get("security", True):
            return state
        
        issues = self.reviewer.find_security_issues(state["code"], state["language"])
        state["security_issues"] = issues
        return state
    
    def performance_agent(self, state: ReviewState) -> ReviewState:
        if not state["review_types"].get("performance", True):
            return state
        
        issues = self.reviewer.find_performance_issues(state["code"], state["language"])
        state["performance_issues"] = issues
        return state
    
    def style_agent(self, state: ReviewState) -> ReviewState:
        if not state["review_types"].get("style", True):
            return state
        
        issues = self.reviewer.find_style_issues(state["code"], state["language"])
        state["style_issues"] = issues
        return state
    
    def similar_patterns_agent(self, state: ReviewState) -> ReviewState:
        try:
            if self.chroma_store:
                similar = self.chroma_store.search_similar(state["code"], state["language"])
                state["similar_patterns"] = similar
            else:
                state["similar_patterns"] = []
        except Exception as e:
            print(f"ChromaDB error: {e}")
            state["similar_patterns"] = []
        return state
    
    def refactoring_agent(self, state: ReviewState) -> ReviewState:
        if not state["review_types"].get("refactoring", True):
            state["refactoring_suggestions"] = []
            return state
        
        all_issues = []
        all_issues.extend(state.get("bugs", []))
        all_issues.extend(state.get("security_issues", []))
        all_issues.extend(state.get("performance_issues", []))
        all_issues.extend(state.get("style_issues", []))
        
        suggestions = []
        
        if self.llm and all_issues and len(state["code"]) < 2000:
            try:
                prompt = ChatPromptTemplate.from_template("""
                Refactor this {language} code to fix these issues:
                
                Issues: {issues}
                Code: {code}
                
                Provide JSON with: refactored_code, explanations, improvements
                """)
                response = self.llm.invoke(prompt.format(
                    language=state["language"],
                    issues=json.dumps(all_issues[:10]),
                    code=state["code"][:1500]
                ))
                try:
                    suggestions = [json.loads(response.content)]
                except:
                    suggestions = [{
                        "title": "Refactoring Suggestions",
                        "explanations": "AI analysis completed",
                        "improvements": response.content[:500]
                    }]
            except Exception as e:
                print(f"LLM refactoring error: {e}")
                suggestions = self._fallback_refactoring(all_issues)
        else:
            suggestions = self._fallback_refactoring(all_issues)
        
        state["refactoring_suggestions"] = suggestions
        return state
    
    def _fallback_refactoring(self, all_issues):
        parts = []
        bugs = [i for i in all_issues if i.get('severity') == 'critical' or 'Zero' in i.get('type', '')]
        security = [i for i in all_issues if 'security' in str(i.get('type', '')).lower() or 'SQL' in i.get('type', '')]
        performance = [i for i in all_issues if 'performance' in str(i.get('type', '')).lower() or 'loop' in str(i.get('type', '')).lower()]
        style = [i for i in all_issues if i.get('severity') == 'low' or 'style' in str(i.get('type', '')).lower() or 'Line' in i.get('type', '')]
        
        if bugs:
            parts.append(f"• 🔴 Fix {len(bugs)} bugs")
        if security:
            parts.append(f"• 🔒 Address {len(security)} security vulnerabilities")
        if performance:
            parts.append(f"• ⚡ Optimize {len(performance)} performance issues")
        if style:
            parts.append(f"• 🎨 Improve {len(style)} style issues")
        
        return [{
            "title": "Code Refactoring Recommendations",
            "explanations": "Based on the analysis",
            "improvements": "\n".join(parts) if parts else "Code is clean. Continue best practices."
        }]
    
    def report_agent(self, state: ReviewState) -> ReviewState:
        quality_score = self._calculate_quality_score(state)
        readability_score = max(30, 100 - min(len(state.get("style_issues", [])) * 3, 60))
        security_score = max(20, 100 - (len(state.get("security_issues", [])) * 10))
        performance_score = max(30, 100 - (len(state.get("performance_issues", [])) * 8))
        maintainability_score = max(30, 100 - min(len(state.get("style_issues", [])) * 2, 50))
        
        code = state["code"]
        docstring_lines = sum(1 for line in code.split('\n') if '"""' in line or "'''" in line)
        doc_score = max(30, min(100, int((docstring_lines / max(len(code.split('\n')), 1)) * 400)))
        
        state["final_report"] = {
            "quality_score": quality_score,
            "complexity": self._calculate_complexity(state),
            "score_breakdown": {
                "readability": readability_score,
                "security": security_score,
                "performance": performance_score,
                "maintainability": maintainability_score,
                "documentation": doc_score
            },
            "bugs": state.get("bugs", []),
            "security_issues": state.get("security_issues", []),
            "performance_issues": state.get("performance_issues", []),
            "style_issues": state.get("style_issues", []),
            "refactoring_suggestions": state.get("refactoring_suggestions", []),
            "ai_analysis": state.get("ai_analysis", ""),
            "similar_patterns": state.get("similar_patterns", []),
            "suggestions": self._generate_suggestions(state),
            "suggested_fixes": self._generate_fixes(state)
        }
        
        return state
    
    def run_review(self, code: str, language: str, review_types: Dict[str, bool]) -> Dict:
        state = {
            "code": code,
            "language": language,
            "review_types": review_types,
            "file_path": "",
            "bugs": [],
            "security_issues": [],
            "performance_issues": [],
            "style_issues": [],
            "ai_analysis": "",
            "similar_patterns": [],
            "refactoring_suggestions": [],
            "final_report": {}
        }
        
        result = self.app.invoke(state)
        return result["final_report"]
    
    def generate_report(self, results: List[Dict]) -> Dict:
        all_bugs, all_security, all_performance, all_style = [], [], [], []
        all_refactoring, all_suggestions, all_fixes = [], [], []
        
        seen_bugs, seen_security, seen_performance, seen_style = set(), set(), set(), set()
        
        for result in results:
            review = result.get("review", {})
            
            for bug in review.get("bugs", []):
                key = f"{bug.get('type', '')}_{bug.get('line', '')}"
                if key not in seen_bugs:
                    seen_bugs.add(key)
                    all_bugs.append(bug)
            
            for issue in review.get("security_issues", []):
                key = issue.get('type', '')
                if key not in seen_security:
                    seen_security.add(key)
                    all_security.append(issue)
            
            for issue in review.get("performance_issues", []):
                key = issue.get('type', '')
                if key not in seen_performance:
                    seen_performance.add(key)
                    all_performance.append(issue)
            
            for issue in review.get("style_issues", []):
                key = f"{issue.get('type', '')}_{issue.get('line', '')}"
                if key not in seen_style:
                    seen_style.add(key)
                    all_style.append(issue)
            
            all_refactoring.extend([r for r in review.get("refactoring_suggestions", []) if r not in all_refactoring])
            all_suggestions.extend([s for s in review.get("suggestions", []) if s not in all_suggestions])
            all_fixes.extend([f for f in review.get("suggested_fixes", []) if f not in all_fixes])
        
        style_cnt, security_cnt, perf_cnt = len(all_style), len(all_security), len(all_performance)
        read = max(30, 100 - min(style_cnt * 3, 60))
        sec = max(20, 100 - (security_cnt * 10))
        perf = max(30, 100 - (perf_cnt * 8))
        maint = max(30, 100 - min(style_cnt * 2, 50))
        
        doc = 50
        if results:
            code = results[0].get("review", {}).get("code", "")
            if code:
                doc_lines = sum(1 for line in code.split('\n') if '"""' in line or "'''" in line)
                doc = max(30, min(100, int((doc_lines / max(len(code.split('\n')), 1)) * 400)))
        
        quality = int((read + sec + perf + maint + doc) / 5)
        
        if not all_refactoring:
            parts = []
            if all_bugs:
                parts.append(f"• 🔴 Fix {len(all_bugs)} bugs")
            if all_security:
                parts.append(f"• 🔒 Address {len(all_security)} security vulnerabilities")
            if all_performance:
                parts.append(f"• ⚡ Optimize {len(all_performance)} performance issues")
            if all_style:
                parts.append(f"• 🎨 Improve {len(all_style)} style issues")
            all_refactoring = [{
                "title": "Code Refactoring Recommendations" if parts else "Code Quality",
                "explanations": "Based on the analysis" if parts else "No major issues found",
                "improvements": "\n".join(parts) if parts else "Code structure is acceptable."
            }]
        
        if not all_suggestions:
            if all_bugs: all_suggestions.append({"title": "Fix Bugs", "description": f"{len(all_bugs)} bugs detected"})
            if all_security: all_suggestions.append({"title": "Security Audit", "description": f"{len(all_security)} security issues"})
            if all_performance: all_suggestions.append({"title": "Performance Optimization", "description": f"{len(all_performance)} performance issues"})
            if all_style: all_suggestions.append({"title": "Code Style", "description": f"{len(all_style)} style issues to fix"})
        
        if not all_fixes:
            for bug in all_bugs[:3]:
                all_fixes.append({
                    "type": "Bug Fix",
                    "original": f"Line {bug.get('line', 'N/A')}: {bug.get('description', '')}",
                    "fixed": bug.get("suggested_fix", "Fix the logic error"),
                    "explanation": bug.get("description", "")
                })
        
        return {
            "quality_score": quality,
            "complexity": "Medium",
            "score_breakdown": {"readability": read, "security": sec, "performance": perf, "maintainability": maint, "documentation": doc},
            "bugs": all_bugs,
            "security_issues": all_security,
            "performance_issues": all_performance,
            "style_issues": all_style,
            "refactoring_suggestions": all_refactoring,
            "suggestions": all_suggestions,
            "suggested_fixes": all_fixes,
            "ai_analysis": results[0].get("review", {}).get("ai_analysis", "") if results else ""
        }
    
    def _calculate_quality_score(self, state: ReviewState) -> int:
        total = len(state.get("bugs", [])) * 8 + len(state.get("security_issues", [])) * 10 + len(state.get("performance_issues", [])) * 6 + len(state.get("style_issues", [])) * 2
        return max(30, min(100, 100 - total))
    
    def _calculate_complexity(self, state: ReviewState) -> str:
        lines = len(state["code"].split('\n'))
        return "Low" if lines < 50 else "Medium" if lines < 200 else "High"
    
    def _generate_suggestions(self, state: ReviewState) -> List[Dict]:
        suggestions = []
        if state.get("bugs"):
            suggestions.append({"title": "Fix Critical Bugs", "description": f"Found {len(state['bugs'])} bugs"})
        if state.get("security_issues"):
            suggestions.append({"title": "Security Vulnerabilities", "description": f"Found {len(state['security_issues'])} security issues"})
        if state.get("performance_issues"):
            suggestions.append({"title": "Performance Optimizations", "description": f"Found {len(state['performance_issues'])} performance issues"})
        if state.get("style_issues"):
            suggestions.append({"title": "Code Style Improvements", "description": f"Found {len(state['style_issues'])} style issues"})
        return suggestions
    
    def _generate_fixes(self, state: ReviewState) -> List[Dict]:
        fixes = []
        for bug in state.get("bugs", [])[:3]:
            fixes.append({
                "type": "Bug Fix",
                "original": f"Line {bug.get('line', 'N/A')}",
                "fixed": bug.get("suggested_fix", "Fix the logic error"),
                "explanation": bug.get("description", "")
            })
        for issue in state.get("security_issues", [])[:2]:
            fixes.append({
                "type": "Security Fix",
                "original": f"Line {issue.get('line', 'N/A')}",
                "fixed": issue.get("remediation", "Fix the security vulnerability"),
                "explanation": issue.get("description", "")
            })
        return fixes[:5]