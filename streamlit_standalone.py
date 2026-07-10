"""
streamlit_standalone.py
------------------------
A single-process version of the AI Code Review Assistant for deployment on
Streamlit Community Cloud (or any host without a separate FastAPI server).

It reuses ALL the real logic from your project (agents.py, parser.py,
report.py, chroma_store.py) by importing the already-initialized objects
from main.py — it just skips the HTTP layer (no uvicorn, no requests.post).

Your original app.py + main.py are untouched and still work for local /
two-service deployments.
"""

import streamlit as st
import os

# ------------------------------------------------------------------
# IMPORTANT: GROQ_API_KEY must be injected BEFORE importing `main`,
# because main.py reads os.getenv("GROQ_API_KEY") at import time
# (inside CodeReviewOrchestrator.__init__, triggered by main.py's
# module-level `orchestrator = CodeReviewOrchestrator()` line).
#
# On Streamlit Community Cloud, set this in:
#   App settings -> Secrets  ->  GROQ_API_KEY = "gsk_..."
# Locally, it will fall back to your .env / real environment variable.
# ------------------------------------------------------------------
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    # st.secrets raises if no secrets.toml exists at all (e.g. local run) — ignore.
    pass

import json
import base64
import shutil
from datetime import datetime
import pandas as pd

# Reuse the already-initialized objects and helper functions from main.py.
# Importing main.py does NOT start the uvicorn server (that only happens
# under `if __name__ == "__main__":`), so this is safe.
from main import (
    orchestrator,
    report_gen,
    validate_github_url,
    clone_github_repo,
    get_code_files_from_repo,
)

st.set_page_config(page_title="AI Code Review Assistant", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

# Custom CSS - Minified (identical to app.py)
st.markdown("""
<style>
.main-header{font-size:3.2rem;color:#fff;text-align:center;padding:2.5rem 3rem 0.8rem 3rem;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:15px 15px 0 0;box-shadow:0 4px 20px rgba(102,126,234,0.4);width:100%;max-width:100%}
.main-header-subtitle{font-size:1.1rem;color:rgba(255,255,255,0.9);text-align:center;margin-top:.5rem;font-weight:300;letter-spacing:.5px}
.tech-stack-container{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:.8rem 1.5rem 1.2rem 1.5rem;border-radius:0 0 15px 15px;margin-bottom:2rem;box-shadow:0 4px 20px rgba(102,126,234,0.3);display:flex;flex-wrap:wrap;gap:.8rem;justify-content:center;align-items:center}
.tech-card{background:rgba(255,255,255,0.15);backdrop-filter:blur(10px);padding:.5rem 1.2rem;border-radius:20px;color:#fff;font-size:.85rem;font-weight:500;border:1px solid rgba(255,255,255,0.2);transition:all .3s ease;white-space:nowrap;letter-spacing:.3px}
.tech-card:hover{background:rgba(255,255,255,0.25);transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.2)}
.tech-card .icon{margin-right:.4rem}
.sidebar-title{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:.8rem 1rem;border-radius:10px;text-align:center;margin-bottom:1rem;box-shadow:0 2px 10px rgba(102,126,234,0.3);white-space:nowrap}
.sidebar-title h2{color:#fff!important;margin:0;font-size:1.1rem;font-weight:600;display:inline-block}
.source-selector-card{background:#fff;padding:1rem 1.5rem;border-radius:12px;border:2px solid #667eea;box-shadow:0 2px 12px rgba(102,126,234,0.12);margin-bottom:1.5rem}
.source-selector-card .card-title{font-weight:600;font-size:.95rem;color:#2c3e50;margin-bottom:.8rem;display:block;border:none;background:0;padding:0}
.stRadio>div{flex-direction:row!important;gap:.8rem!important;padding:.3rem 0!important}
.stRadio>div>label{flex:1!important;text-align:center!important;padding:.8rem 1rem!important;border:none!important;border-radius:10px!important;background:#e8edf9!important;transition:all .3s ease!important;font-weight:600!important;font-size:1rem!important;min-height:60px!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:.5rem!important;cursor:pointer!important;box-shadow:0 2px 8px rgba(0,0,0,0.05)!important;color:#4a5a8a!important}
.stRadio>div>label:hover{background:#d5def5!important;box-shadow:0 4px 16px rgba(102,126,234,0.2)!important;transform:translateY(-2px)!important}
.stRadio>div>label[data-baseweb="radio"]{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%)!important;color:#fff!important;box-shadow:0 4px 16px rgba(102,126,234,0.35)!important;transform:translateY(-2px)!important}
.input-block{background:#fff;padding:1.5rem;border-radius:12px;border:2px solid #667eea;box-shadow:0 2px 12px rgba(102,126,234,0.15);margin-bottom:1rem}
.input-block-title{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:.5rem 1.2rem;border-radius:8px;color:#fff;font-weight:600;font-size:.95rem;margin-bottom:1rem;display:inline-block}
.score-card{background:#fff;padding:1rem;border-radius:10px;border:1px solid #e0e0e0;text-align:center;box-shadow:0 2px 4px rgba(0,0,0,0.08);height:100%}
.score-value{font-size:2rem;font-weight:700;margin:.3rem 0}
.score-label{font-size:.85rem;color:#666;font-weight:500}
.issue-card,.security-card{background:#fff;padding:1rem;border-radius:8px;border-left:4px solid #ff6b6b;margin:.5rem 0;border:1px solid #e8e8e8}
.fix-card{background:#fff;padding:1rem;border-radius:8px;border-left:4px solid #51cf66;margin:.5rem 0;border:1px solid #e8e8e8}
.refactoring-card{background:#fff;padding:1.2rem;border-radius:8px;border-left:4px solid #764ba2;margin:.5rem 0;border:1px solid #e8e8e8}
.refactoring-card .title{color:#764ba2;font-size:1.05rem;font-weight:600}
.refactoring-card .explanation{margin:.5rem 0;color:#2c3e50}
.refactoring-card .improvement-list{background:#f8f9fa;padding:.8rem 1rem;border-radius:6px;border:1px solid #e8e8e8;margin-top:.5rem}
.refactoring-card .improvement-item{padding:.3rem 0;font-size:.95rem;color:#2c3e50;border-bottom:1px solid #f0f0f0}
.refactoring-card .improvement-item:last-child{border-bottom:none}
.stButton>button{width:100%;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;font-weight:700;padding:.75rem;border:none;border-radius:8px;transition:all .3s ease;font-size:1.1rem;margin-top:.5rem}
.stButton>button:hover{transform:scale(1.02);box-shadow:0 4px 15px rgba(102,126,234,0.4)}
.code-block{background:#f5f5f5;padding:1rem;border-radius:8px;font-family:'Courier New',monospace;font-size:14px;overflow-x:auto;border:1px solid #e8e8e8}
.dataframe{border:2px solid #4a4a4a!important;border-collapse:collapse!important}
.dataframe th{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%)!important;color:#fff!important;padding:12px!important;border:2px solid #4a4a4a!important;text-align:center!important;font-weight:600!important}
.dataframe td{border:2px solid #4a4a4a!important;padding:12px!important;text-align:center!important;background:#fff!important;color:#2c3e50!important;font-weight:500!important}
.dataframe tr:hover td{background:#f8f9fa!important}
.section-header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:.6rem 1.2rem;border-radius:8px;color:#fff;margin:1.5rem 0 .8rem 0;font-weight:600;font-size:1.2rem}
.section-divider{border:none;height:2px;background:linear-gradient(to right,transparent,#667eea,#764ba2,transparent);margin:1.5rem 0}
.score-table-container{background:#fff;padding:.5rem;border-radius:10px;border:1px solid #e0e0e0;box-shadow:0 2px 8px rgba(0,0,0,0.06)}
.source-indicator{background:#e8f5e9;padding:.5rem 1rem;border-radius:8px;border-left:4px solid #4caf50;margin-bottom:1rem}
.stFileUploader>div,.stFileUploader>div>div{display:flex!important;flex-wrap:nowrap!important}
.file-list{display:inline-block;padding:.5rem 1rem;background:#f5f5f5;border-radius:8px;border:1px solid #e0e0e0;font-family:monospace;font-size:.9rem;margin-top:.5rem}
.stFooter,.stDeployButton{display:none!important}
.st-emotion-cache-1y4p8pa{max-width:100%!important;padding-bottom:0!important}
</style>
""", unsafe_allow_html=True)

# Session state
for key in ['review_result', 'active_source', 'selected_source', 'file_uploader_key']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'selected_source' else 'code'
        if key == 'file_uploader_key':
            st.session_state[key] = 0

# Sidebar
with st.sidebar:
    st.markdown('<div class="sidebar-title"><h2>🤖 AI Code Review Assistant</h2></div>', unsafe_allow_html=True)
    language = st.selectbox("Programming Language", ["Python", "Java", "JavaScript", "C++", "Go", "Rust"])
    st.subheader("Review Types")
    review_security = st.checkbox("🔒 Security", value=True)
    review_performance = st.checkbox("⚡ Performance", value=True)
    review_bugs = st.checkbox("🐛 Bugs", value=True)
    review_style = st.checkbox("🎨 Code Style", value=True)
    review_refactoring = st.checkbox("🔄 Refactoring", value=True)
    st.markdown("---")
    st.info("💡 Select review types and language, then provide code")
    if not os.getenv("GROQ_API_KEY"):
        st.warning("⚠️ GROQ_API_KEY not set — AI analysis/refactoring will be limited. Add it in App Settings → Secrets.")

# Main content
st.markdown('<div class="main-header">🔍 AI Code Review Assistant<div class="main-header-subtitle">✨ AI-powered code analysis for bugs, security, performance, and style improvements</div></div>', unsafe_allow_html=True)
st.markdown('<div class="tech-stack-container"><span class="tech-card"><span class="icon">⚡</span>Groq · Llama 3.3 70B</span><span class="tech-card"><span class="icon">🔄</span>LangGraph</span><span class="tech-card"><span class="icon">📚</span>LangChain</span><span class="tech-card"><span class="icon">🔍</span>ChromaDB</span><span class="tech-card"><span class="icon">🚀</span>Streamlit (standalone)</span></div>', unsafe_allow_html=True)

# Source selector
st.markdown('<div class="source-selector-card"><div class="card-title">📌 Select Input Source</div>', unsafe_allow_html=True)
source_options = {"code": "📝 Paste Code", "files": "📁 Upload Files", "github": "🔗 GitHub URL"}
selected_source = st.radio("", options=list(source_options.keys()), format_func=lambda x: source_options[x], horizontal=True, key="source_radio_big", index=0)
if selected_source != st.session_state.selected_source:
    st.session_state.selected_source = selected_source
    st.session_state.review_result = None
    st.session_state.active_source = None
    st.session_state.file_uploader_key += 1
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# Input section
uploaded_files, code_input, github_url = None, "", ""
if st.session_state.selected_source == "code":
    st.markdown('<div class="input-block"><div class="input-block-title">📝 Paste Your Code</div>', unsafe_allow_html=True)
    code_input = st.text_area("Paste your code here", height=400, placeholder="def hello():\n    print('Hello, World!')", key="code_input_main", label_visibility="collapsed")
    if code_input:
        st.info(f"📝 {len(code_input.splitlines())} lines ready for analysis")
    st.markdown('</div>', unsafe_allow_html=True)
elif st.session_state.selected_source == "files":
    st.markdown('<div class="input-block"><div class="input-block-title">📁 Upload Your Files</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Choose code files", type=["py", "java", "js", "cpp", "go", "rs", "txt"], accept_multiple_files=True, key=f"file_uploader_{st.session_state.file_uploader_key}", label_visibility="collapsed")
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
        st.markdown(f'<div class="file-list">📄 {", ".join([f.name for f in uploaded_files])}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
elif st.session_state.selected_source == "github":
    st.markdown('<div class="input-block"><div class="input-block-title">🔗 Enter GitHub Repository URL</div>', unsafe_allow_html=True)
    github_url = st.text_input("Enter GitHub repository URL", placeholder="https://github.com/username/repo", key="github_url_main", label_visibility="collapsed")
    if github_url:
        st.info(f"📂 Will analyze: {github_url.split('/')[-1]}")
    st.markdown('</div>', unsafe_allow_html=True)

# Analyze button
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    analyze_button = st.button("🚀 Analyze Code", use_container_width=True)

# ------------------------------------------------------------------
# Process analysis — this replaces the `requests.post(f"{API_URL}/review", ...)`
# call from app.py with a direct, in-process call into the same logic
# main.py's /review endpoint uses.
# ------------------------------------------------------------------
if analyze_button:
    has_files = uploaded_files and len(uploaded_files) > 0
    has_code = code_input and code_input.strip() != ""
    has_github = github_url and github_url.strip() != ""

    if (st.session_state.selected_source == "code" and not has_code) or (st.session_state.selected_source == "files" and not has_files) or (st.session_state.selected_source == "github" and not has_github):
        st.error(f"❌ Please provide code for {source_options[st.session_state.selected_source]}")
    else:
        st.session_state.review_result = None
        with st.spinner("🤖 AI is analyzing your code..."):
            try:
                review_types_dict = {
                    "security": review_security,
                    "performance": review_performance,
                    "bugs": review_bugs,
                    "style": review_style,
                    "refactoring": review_refactoring,
                }

                code_files = []
                repo_summary = None
                active_source = st.session_state.selected_source

                if active_source == "github":
                    if not validate_github_url(github_url):
                        st.error("❌ Invalid GitHub URL format (expected https://github.com/user/repo)")
                        st.stop()

                    repo_path = clone_github_repo(github_url)
                    try:
                        code_files = get_code_files_from_repo(repo_path, language)
                        if not code_files:
                            st.error(f"❌ No {language} files found in that repository")
                            st.stop()

                        repo_summary = {
                            'total_files': len(code_files),
                            'total_lines': sum(f['content'].count('\n') + 1 for f in code_files),
                            'largest_files': sorted(
                                [{'name': f['filename'], 'lines': f['content'].count('\n') + 1} for f in code_files],
                                key=lambda x: x['lines'], reverse=True
                            )[:5]
                        }
                    finally:
                        shutil.rmtree(repo_path, ignore_errors=True)

                elif active_source == "files":
                    for file in uploaded_files:
                        content = file.read()
                        code_files.append({
                            "filename": file.name,
                            "content": content.decode('utf-8', errors='ignore'),
                            "size": len(content),
                        })

                else:  # pasted code
                    code_files.append({
                        "filename": "pasted_code.txt",
                        "content": code_input,
                        "size": len(code_input),
                    })

                if not code_files:
                    st.error("❌ No code provided")
                    st.stop()

                all_results = []
                for code_file in code_files:
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

                result = {
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
                    "report_base64": pdf_base64,
                }

                st.session_state.review_result = result
                st.session_state.active_source = active_source
                st.success("✅ Review completed successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")

# ------------------------------------------------------------------
# Display results — identical to app.py, unchanged.
# ------------------------------------------------------------------
if st.session_state.review_result:
    result = st.session_state.review_result
    source_names = {'files': '📁 Uploaded Files', 'code': '📝 Pasted Code', 'github': '🔗 GitHub Repository'}
    active = st.session_state.active_source
    if active in source_names:
        st.markdown(f'<div class="source-indicator">✅ Results from: <strong>{source_names[active]}</strong></div>', unsafe_allow_html=True)

    # Quality Score
    st.markdown("---")
    st.markdown('<div class="section-header">📊 Overall Quality Score</div>', unsafe_allow_html=True)
    quality_score = result.get('quality_score', 0)
    color = "red" if quality_score < 50 else "orange" if quality_score < 70 else "green"
    cols = st.columns(4)
    metrics = [("📊 Quality Score", f"{quality_score}/100", color), ("📈 Complexity", result.get('complexity', 'N/A'), "#4a90d9"), ("🐛 Bugs Found", len(result.get('bugs', [])), "#ff6b6b"), ("🔒 Security Issues", len(result.get('security_issues', [])), "#ff6b6b")]
    for idx, (label, value, c) in enumerate(metrics):
        with cols[idx]:
            st.markdown(f'<div class="score-card"><div class="score-label">{label}</div><div class="score-value" style="color:{c};">{value}</div></div>', unsafe_allow_html=True)

    # Repository Summary
    if result.get('repository_summary'):
        st.markdown("---")
        st.markdown('<div class="section-header">📂 Repository Analysis</div>', unsafe_allow_html=True)
        rs = result['repository_summary']
        cols = st.columns(3)
        cols[0].metric("📁 Total Files", rs.get('total_files', 0))
        cols[1].metric("📝 Total Lines", rs.get('total_lines', 0))
        largest = rs.get('largest_files', [{}])[0] if rs.get('largest_files') else {}
        cols[2].metric("📊 Largest File", largest.get('name', 'N/A')[:30] if largest.get('name') else 'N/A')
        if rs.get('largest_files'):
            st.subheader("📄 Largest Files")
            for f in rs['largest_files'][:5]:
                st.write(f"• `{f['name']}` ({f['lines']} lines)")

    # Score Breakdown
    st.markdown("---")
    st.markdown('<div class="section-header">📊 Score Breakdown</div>', unsafe_allow_html=True)
    if 'score_breakdown' in result:
        df = pd.DataFrame({'Metric': ['Readability', 'Security', 'Performance', 'Maintainability', 'Documentation'], 'Score': [f"{result['score_breakdown'].get(m, 0)}/100" for m in ['readability', 'security', 'performance', 'maintainability', 'documentation']]})
        st.markdown('<div class="score-table-container">', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Helper function to display issues
    def display_issues(title, issues, key, color_map):
        st.markdown("---")
        st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
        if issues:
            unique = []
            seen = set()
            for i in issues:
                k = f"{i.get('line', '')}_{i.get('type', '')}"
                if k not in seen:
                    seen.add(k)
                    unique.append(i)
            for i in unique:
                sev = i.get('severity', 'medium').lower()
                c = color_map.get(sev, '#6c757d')
                st.markdown(f'<div class="{key}-card"><strong style="color:{c};font-size:1.05rem;">⚠️ {i.get("type", "Issue")}</strong><br><strong>📍 Line:</strong> {i.get("line", "N/A")}<br><strong>📝 Description:</strong> {i.get("description", "")}<br><strong>⚠️ Severity:</strong> <span style="color:{c};font-weight:700;">{sev.upper()}</span></div>', unsafe_allow_html=True)
        else:
            st.success(f"✅ No {title.lower()} detected!")

    # Display all issue types
    display_issues("🔒 Security Issues", result.get('security_issues', []), "security", {'critical':'#dc3545','high':'#fd7e14','medium':'#ffc107','low':'#28a745','info':'#17a2b8'})
    display_issues("🐛 Bugs Detected", result.get('bugs', []), "issue", {'critical':'#dc3545','high':'#fd7e14','medium':'#ffc107','low':'#28a745'})

    # Performance Issues
    st.markdown("---")
    st.markdown('<div class="section-header">⚡ Performance Issues</div>', unsafe_allow_html=True)
    perf_issues = result.get('performance_issues', [])
    if perf_issues:
        unique = []
        seen = set()
        for i in perf_issues:
            k = f"{i.get('line', '')}_{i.get('type', '')}"
            if k not in seen:
                seen.add(k)
                unique.append(i)
        for i in unique:
            impact = i.get('impact', 'medium').lower()
            c = {'high':'#fd7e14','medium':'#ffc107','low':'#28a745'}.get(impact, '#6c757d')
            st.markdown(f'<div class="issue-card"><strong style="color:#fd7e14;font-size:1.05rem;">⚡ {i.get("type", "Performance Issue")}</strong><br><strong>📍 Line:</strong> {i.get("line", "N/A")}<br><strong>📝 Description:</strong> {i.get("description", "")}<br><strong>📊 Impact:</strong> <span style="color:{c};font-weight:700;">{impact.upper()}</span></div>', unsafe_allow_html=True)
    else:
        st.success("✅ No performance issues detected!")

    # Style Issues (limit to 15)
    st.markdown("---")
    st.markdown('<div class="section-header">🎨 Code Style Issues</div>', unsafe_allow_html=True)
    style_issues = result.get('style_issues', [])
    if style_issues:
        unique = []
        seen = set()
        for i in style_issues:
            k = f"{i.get('line', '')}_{i.get('type', '')}"
            if k not in seen:
                seen.add(k)
                unique.append(i)
        for i in unique[:15]:
            st.markdown(f'<div class="issue-card"><strong style="color:#4a90d9;font-size:1.05rem;">🎨 {i.get("type", "Style Issue")}</strong><br><strong>📍 Line:</strong> {i.get("line", "N/A")}<br><strong>📝 Description:</strong> {i.get("description", "")}<br><strong>💡 Suggestion:</strong> {i.get("suggestion", "")}</div>', unsafe_allow_html=True)
        if len(unique) > 15:
            st.info(f"📌 Showing 15 of {len(unique)} style issues. See full report for all.")
    else:
        st.success("✅ No style issues detected!")

    # Suggested Fixes
    st.markdown("---")
    st.markdown('<div class="section-header">🔧 Suggested Fixes</div>', unsafe_allow_html=True)
    fixes = result.get('suggested_fixes', [])
    if fixes:
        unique = []
        seen = set()
        for f in fixes:
            k = f"{f.get('type', '')}_{f.get('explanation', '')}"
            if k not in seen:
                seen.add(k)
                unique.append(f)
        for f in unique[:5]:
            st.markdown(f'<div class="fix-card"><strong style="color:#28a745;font-size:1.05rem;">✅ {f.get("type", "Fix")}</strong><br><strong>📝 Explanation:</strong> {f.get("explanation", "")}<br><strong>📄 Original:</strong><br><div class="code-block" style="color:#dc3545;">{f.get("original", "")}</div><strong>✅ Fixed:</strong><br><div class="code-block" style="color:#28a745;">{f.get("fixed", "")}</div></div>', unsafe_allow_html=True)
    else:
        st.info("💡 No fixes suggested")

    # Refactoring Suggestions - Consolidated
    st.markdown("---")
    st.markdown('<div class="section-header">🔄 Refactoring Suggestions</div>', unsafe_allow_html=True)
    refactoring = result.get('refactoring_suggestions', [])
    if refactoring and isinstance(refactoring, list) and len(refactoring) > 0:
        all_improvements, all_explanations = [], []
        for ref in refactoring:
            if isinstance(ref, dict):
                exp = ref.get('explanations', '')
                if exp and exp not in all_explanations:
                    all_explanations.append(exp)
                imp = ref.get('improvements', '')
                if imp:
                    for line in imp.split('\n'):
                        if line.strip() and line.strip() not in all_improvements:
                            all_improvements.append(line.strip())
        st.markdown('<div class="refactoring-card"><div class="title">🔄 Code Refactoring Recommendations</div>', unsafe_allow_html=True)
        if all_explanations:
            st.markdown(f'<div class="explanation"><strong>📝 Explanation:</strong> {all_explanations[0]}</div>', unsafe_allow_html=True)
        if all_improvements:
            st.markdown('<div class="improvement-list"><strong>✅ Improvements:</strong>', unsafe_allow_html=True)
            for item in all_improvements:
                st.markdown(f'<div class="improvement-item">• {item}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="improvement-list"><em>No specific improvements suggested.</em></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("💡 No refactoring suggestions")

    # General Suggestions
    st.markdown("---")
    st.markdown('<div class="section-header">💡 General Suggestions</div>', unsafe_allow_html=True)
    suggestions = result.get('suggestions', [])
    if suggestions:
        for s in suggestions:
            st.markdown(f'<div class="fix-card" style="border-left-color:#667eea;"><strong style="color:#667eea;font-size:1.05rem;">💡 {s.get("title", "Suggestion")}</strong><br>{s.get("description", "")}</div>', unsafe_allow_html=True)
    else:
        st.info("💡 No additional suggestions")

    # Download Report
    st.markdown("---")
    st.markdown('<div class="section-header">📄 Download Full Report</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if result.get('report_filename') and result.get('report_base64'):
            st.success(f"📄 Report generated: {result['report_filename']}")
            pdf_bytes = base64.b64decode(result['report_base64'])
            st.download_button("📥 Download PDF Report (Full Details)", data=pdf_bytes, file_name=f"code_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", mime="application/pdf", use_container_width=True)
