from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os
from pathlib import Path
import json
from typing import Dict, List, Any, Optional

class ReportGenerator:
    def __init__(self, output_dir: str = "temp"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._customize_styles()
    
    def _customize_styles(self):
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3498db'),
            spaceBefore=20,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='SubSectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=12,
            spaceAfter=6
        ))
        
        self.styles.add(ParagraphStyle(
            name='IssueStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=5,
            spaceAfter=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='CodeStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Courier',
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=5,
            spaceAfter=5,
            leftIndent=20
        ))
        
        self.styles.add(ParagraphStyle(
            name='AIInsight',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#764ba2'),
            spaceBefore=5,
            spaceAfter=5,
            backColor=colors.HexColor('#f3e8ff'),
            borderPadding=5,
            borderRadius=5
        ))
    
    def generate_pdf(self, report_data: Dict) -> str:
        filename = f"code_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = self.output_dir / filename
        
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        story = []
        
        # Title
        story.append(Paragraph("AI Code Review Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", self.styles['Normal']))
        story.append(Spacer(1, 12))
        
        # AI Analysis (NEW)
        if report_data.get('ai_analysis'):
            story.append(Paragraph("AI Code Understanding", self.styles['SectionHeader']))
            story.append(Paragraph(report_data['ai_analysis'], self.styles['AIInsight']))
            story.append(Spacer(1, 12))
        
        # Quality Score
        story.append(Paragraph("Overall Quality Score", self.styles['SectionHeader']))
        quality_score = report_data.get('quality_score', 0)
        story.append(Paragraph(f"<b>{quality_score}/100</b>", self.styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Score Breakdown
        story.append(Paragraph("Score Breakdown", self.styles['SectionHeader']))
        breakdown = report_data.get('score_breakdown', {})
        
        score_data = [
            ['Metric', 'Score'],
            ['Readability', f"{breakdown.get('readability', 0)}/100"],
            ['Security', f"{breakdown.get('security', 0)}/100"],
            ['Performance', f"{breakdown.get('performance', 0)}/100"],
            ['Maintainability', f"{breakdown.get('maintainability', 0)}/100"],
            ['Documentation', f"{breakdown.get('documentation', 0)}/100"]
        ]
        
        score_table = Table(score_data, colWidths=[2*inch, 2*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(score_table)
        story.append(Spacer(1, 20))
        
        # Complexity
        story.append(Paragraph(f"Complexity: {report_data.get('complexity', 'N/A')}", self.styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Issues Section
        story.append(PageBreak())
        story.append(Paragraph("Issues Found", self.styles['SectionHeader']))
        
        # Similar Patterns (NEW - from ChromaDB)
        if report_data.get('similar_patterns'):
            story.append(Paragraph("Similar Code Patterns Found", self.styles['SubSectionHeader']))
            for pattern in report_data['similar_patterns']:
                story.append(Paragraph(f"<b>Issue:</b> {pattern.get('issue', 'Unknown')}", self.styles['IssueStyle']))
                story.append(Paragraph(f"<b>Fix:</b> {pattern.get('fix', 'No fix suggested')}", self.styles['IssueStyle']))
                story.append(Paragraph(f"<b>Pattern:</b> {pattern.get('code', '')[:100]}...", self.styles['CodeStyle']))
                story.append(Spacer(1, 5))
        
        # Bugs
        bugs = report_data.get('bugs', [])
        if bugs:
            story.append(Paragraph("<b>Bugs</b>", self.styles['SubSectionHeader']))
            for bug in bugs:
                story.append(Paragraph(
                    f"• Line {bug.get('line', 'N/A')}: {bug.get('description', '')} "
                    f"<i>({bug.get('severity', 'medium')})</i>",
                    self.styles['IssueStyle']
                ))
                if bug.get('suggested_fix'):
                    story.append(Paragraph(
                        f"  <b>Fix:</b> {bug.get('suggested_fix', '')}",
                        self.styles['IssueStyle']
                    ))
            story.append(Spacer(1, 10))
        
        # Security Issues
        security_issues = report_data.get('security_issues', [])
        if security_issues:
            story.append(Paragraph("<b>Security Issues</b>", self.styles['SubSectionHeader']))
            for issue in security_issues:
                story.append(Paragraph(
                    f"• Line {issue.get('line', 'N/A')}: {issue.get('description', '')} "
                    f"<i>({issue.get('severity', 'medium')})</i>",
                    self.styles['IssueStyle']
                ))
                if issue.get('remediation'):
                    story.append(Paragraph(
                        f"  <b>Remediation:</b> {issue.get('remediation', '')}",
                        self.styles['IssueStyle']
                    ))
            story.append(Spacer(1, 10))
        
        # Performance Issues
        performance_issues = report_data.get('performance_issues', [])
        if performance_issues:
            story.append(Paragraph("<b>Performance Issues</b>", self.styles['SubSectionHeader']))
            for issue in performance_issues:
                story.append(Paragraph(
                    f"• Line {issue.get('line', 'N/A')}: {issue.get('description', '')} "
                    f"<i>({issue.get('severity', 'medium')})</i>",
                    self.styles['IssueStyle']
                ))
            story.append(Spacer(1, 10))
        
        # Style Issues
        style_issues = report_data.get('style_issues', [])
        if style_issues:
            story.append(Paragraph("<b>Style Issues</b>", self.styles['SubSectionHeader']))
            for issue in style_issues[:20]:  # Limit to 20
                story.append(Paragraph(
                    f"• Line {issue.get('line', 'N/A')}: {issue.get('description', '')}",
                    self.styles['IssueStyle']
                ))
            if len(style_issues) > 20:
                story.append(Paragraph(
                    f"  <i>... and {len(style_issues) - 20} more style issues</i>",
                    self.styles['IssueStyle']
                ))
            story.append(Spacer(1, 10))
        
        # Suggestions and Fixes
        story.append(PageBreak())
        story.append(Paragraph("Suggestions & Fixes", self.styles['SectionHeader']))
        
        # Refactoring Suggestions
        refactoring = report_data.get('refactoring_suggestions', [])
        if refactoring:
            for refactor in refactoring:
                story.append(Paragraph(f"<b>{refactor.get('title', 'Refactoring')}</b>", self.styles['SubSectionHeader']))
                story.append(Paragraph(refactor.get('explanations', ''), self.styles['Normal']))
                improvements = refactor.get('improvements', '')
                if improvements:
                    for line in improvements.split('\n'):
                        if line.strip():
                            story.append(Paragraph(f"• {line.strip()}", self.styles['IssueStyle']))
                story.append(Spacer(1, 5))
        
        # General Suggestions
        suggestions = report_data.get('suggestions', [])
        if suggestions:
            story.append(Paragraph("<b>General Suggestions</b>", self.styles['SubSectionHeader']))
            for suggestion in suggestions:
                story.append(Paragraph(
                    f"• {suggestion.get('title', '')}: {suggestion.get('description', '')}",
                    self.styles['IssueStyle']
                ))
            story.append(Spacer(1, 10))
        
        # Suggested Fixes
        suggested_fixes = report_data.get('suggested_fixes', [])
        if suggested_fixes:
            story.append(Paragraph("<b>Specific Fixes</b>", self.styles['SubSectionHeader']))
            for fix in suggested_fixes:
                story.append(Paragraph(f"<b>{fix.get('type', 'Fix')}</b>", self.styles['Heading4']))
                story.append(Paragraph(f"Original: {fix.get('original', '')}", self.styles['CodeStyle']))
                story.append(Paragraph(f"Fixed: {fix.get('fixed', '')}", self.styles['CodeStyle']))
                story.append(Paragraph(f"Explanation: {fix.get('explanation', '')}", self.styles['Normal']))
                story.append(Spacer(1, 5))
        
        doc.build(story)
        return filename
    
    def get_pdf_data(self, filename: str) -> bytes:
        filepath = self.output_dir / filename
        if filepath.exists():
            with open(filepath, 'rb') as f:
                return f.read()
        return b''