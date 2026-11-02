"""Export separate review DOCX copies; no original documents are edited."""
from pathlib import Path
from datetime import datetime, timezone
import json
from docx import Document
from docx.shared import Inches, Pt
import docx

ROOT=Path(__file__).resolve().parents[1]


def export(source, destination):
    content=(ROOT/source).read_text()
    doc=Document()
    doc.sections[0].top_margin=Inches(.7)
    doc.sections[0].bottom_margin=Inches(.7)
    style=doc.styles['Normal']
    style.font.name='Calibri';style.font.size=Pt(10)
    style.paragraph_format.space_after=Pt(5)
    for line in content.splitlines():
        if line.startswith('# '):doc.add_heading(line[2:],level=0)
        elif line.startswith('## '):doc.add_heading(line[3:],level=1)
        elif line.startswith('### '):doc.add_heading(line[4:],level=2)
        elif line.startswith('- '):doc.add_paragraph(line[2:],style='List Bullet')
        else:doc.add_paragraph(line)
    doc.core_properties.title=content.splitlines()[0].lstrip('# ')
    doc.core_properties.subject='Prepared evidence/proposal; human approvals pending'
    doc.save(ROOT/destination)


def main():
    files=[('protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.md','protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.docx'),
           ('review_sheets/HUMAN_REVIEW_SIGNATURES.md','review_sheets/HUMAN_REVIEW_SIGNATURES.docx')]
    for src,dest in files:export(src,dest)
    (ROOT/'protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.txt').write_text((ROOT/'protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.md').read_text())
    (ROOT/'reports/document_export.json').write_text(json.dumps({'export_utc':datetime.now(timezone.utc).isoformat(),
        'python_docx_version':docx.__version__,'files':[d for _,d in files],
        'rendered_layout_review':False},indent=2)+'\n')
    print('Separate protocol and signature DOCX exports written; originals untouched.')


if __name__=='__main__':main()
