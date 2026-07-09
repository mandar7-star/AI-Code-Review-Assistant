from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional, List, Dict, Any
import uvicorn
import os
from datetime import datetime
import json
from pathlib import Path
import shutil
import base64
import subprocess
import re

print("=" * 50)
print("Starting AI Code Review Assistant Backend...")
print("=" * 50)

try:
    from agents import CodeReviewOrchestrator
    print("✓ agents imported")
except Exception as e:
    print(f"✗ Error importing agents: {e}")
    exit(1)

try:
    from parser import CodeParser
    print("✓ parser imported")
except Exception as e:
    print(f"✗ Error importing parser: {e}")
    exit(1)

try:
    from report import ReportGenerator
    print("✓ report imported")
except Exception as e:
    print(f"✗ Error importing report: {e}")
    exit(1)

print("All imports successful!")

app = FastAPI(title="AI Code Review Assistant", version="1.0.0")

# ============================================================
# CORS Configuration - Updated for Hugging Face Deployment
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Hugging Face
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Initializing components...")
orchestrator = CodeReviewOrchestrator()
print("✓ orchestrator initialized")

parser = CodeParser()
print("✓ parser initialized")

report_gen = ReportGenerator()
print("✓ report generator initialized")

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

GITHUB_DIR = Path("github_repos")
GITHUB_DIR.mkdir(exist_ok=True)

VALID_GITHUB_PATTERN = re.compile(r'^https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/?$')

def validate_github_url(url: str) -> bool:
    return bool(VALID_GITHUB_PATTERN.match(url))

def clone_github_repo(repo_url: str) -> str:
    if not validate_github_url(repo_url):
        raise Exception("Invalid GitHub URL format")
    
    repo_name = repo_url.rstrip('/').split('/')[-1]
    if repo_name.endswith('.git'):  # ✅ FIXED: changed to repo_name
        repo_name = repo_name[:-4]
    
    repo_dir = GITHUB_DIR / f"{repo_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    repo_dir.mkdir(exist_ok=True)
    
    result = subprocess.run(
        ['git', 'clone', '--depth', '1', repo_url, str(repo_dir)],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    if result.returncode != 0:
        raise Exception(f"Git clone failed: {result.stderr}")
    
    return str(repo_dir)

def get_code_files_from_repo(repo_path: str, language: str) -> List[Dict]:
    extensions = {
        'python': ['.py'],
        'java': ['.java'],
        'javascript': ['.js', '.jsx', '.ts', '.tsx'],
        'cpp': ['.cpp', '.c', '.h', '.hpp'],
        'go': ['.go'],
        'rust': ['.rs']
    }
    
    exts = extensions.get(language.lower(), ['.py'])
    code_files = []
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', 'target']]
        
        for file in files:
            if any(file.endswith(ext) for ext in exts):
                file_path = Path(root) / file
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    code_files.append({
                        'filename': str(file_path.relative_to(repo_path)),
                        'content': content,
                        'size': len(content)
                    })
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
    
    return code_files

@app.get("/")
async def root():
    return {"message": "AI Code Review Assistant API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Backend is running"}

@app.post("/review")
async def review_code(
    files: Optional[List[UploadFile]] = File(None),
    code_content: Optional[str] = Form(None),
    language: str = Form("python"),
    review_types: str = Form("{}"),
    github_url: Optional[str] = Form(None)
):
    try:
        print(f"Received request: language={language}, has_files={files is not None}, has_code={code_content is not None}, has_github={github_url is not None}")
        
        review_types_dict = json.loads(review_types) if review_types else {
            "security": True, "performance": True, "bugs": True,
            "style": True, "refactoring": True
        }
        
        code_files = []
        repo_summary = None
        
        if github_url and github_url.strip():
            print(f"Cloning GitHub repo: {github_url}")
            if not validate_github_url(github_url):
                raise HTTPException(status_code=400, detail="Invalid GitHub URL format")
            
            repo_path = clone_github_repo(github_url)
            code_files = get_code_files_from_repo(repo_path, language)
            
            if not code_files:
                if repo_path and os.path.exists(repo_path):
                    shutil.rmtree(repo_path)
                raise HTTPException(status_code=400, detail=f"No {language} files found")
            
            repo_summary = {
                'total_files': len(code_files),
                'total_lines': sum(f['content'].count('\n') + 1 for f in code_files),
                'largest_files': sorted([{'name': f['filename'], 'lines': f['content'].count('\n') + 1} for f in code_files], key=lambda x: x['lines'], reverse=True)[:5]
            }
            
            shutil.rmtree(repo_path)
        
        if files:
            for file in files:
                content = await file.read()
                code_files.append({
                    "filename": file.filename,
                    "content": content.decode('utf-8', errors='ignore'),
                    "size": file.size
                })
        
        if code_content:
            code_files.append({
                "filename": "pasted_code.txt",
                "content": code_content,
                "size": len(code_content)
            })
        
        if not code_files:
            raise HTTPException(status_code=400, detail="No code provided")
        
        all_results = []
        for code_file in code_files:
            print(f"Processing: {code_file['filename']} ({len(code_file['content'])} chars)")
            report = orchestrator.run_review(
                code_file['content'],
                language,
                review_types_dict
            )
            all_results.append({
                "filename": code_file['filename'],
                "review": report
            })
        
        overall_report = orchestrator.generate_report(all_results)
        if repo_summary:
            overall_report['repository_summary'] = repo_summary
        
        report_file = report_gen.generate_pdf(overall_report)
        pdf_data = report_gen.get_pdf_data(report_file)
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8') if pdf_data else ""
        
        return JSONResponse({
            "status": "success",
            "review_id": f"REV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "quality_score": overall_report.get('quality_score', 0),
            "complexity": overall_report.get('complexity', 'N/A'),
            "score_breakdown": overall_report.get('score_breakdown', {}),
            "bugs": overall_report.get('bugs', []),
            "security_issues": overall_report.get('security_issues', []),
            "performance_issues": overall_report.get('performance_issues', []),
            "style_issues": overall_report.get('style_issues', []),
            "refactoring_suggestions": overall_report.get('refactoring_suggestions', []),
            "suggestions": overall_report.get('suggestions', []),
            "suggested_fixes": overall_report.get('suggested_fixes', []),
            "ai_analysis": overall_report.get('ai_analysis', ''),
            "repository_summary": repo_summary,
            "report_filename": report_file,
            "report_base64": pdf_base64
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_report(filename: str):
    file_path = TEMP_DIR / filename
    if file_path.exists():
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/pdf"
        )
    raise HTTPException(status_code=404, detail="Report not found")

if __name__ == "__main__":
    print("=" * 50)
    print("Starting server on http://0.0.0.0:8000")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)