#!/usr/bin/env python3
"""Actual document-only entry point. Verify visible native formulas before building.
Content and layout: build_documents.py. No model or human-visual success claimed.
"""
import copy, json, re, zipfile, hashlib
import fitz
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import build_documents as b

# Equivalent to the user's R formula; named K avoids growing-delimiter import ambiguity.
b.EQUATIONS['R']=r'R_d(t)=\rho(K(t)),\qquad K(t)=\operatorname{diag}(\beta_i(t)(1-x_i(t)))C(t)\Gamma(t)^{-1}'
CACHE={}


def source_math(key):
    if key not in CACHE:
        md=b.TMP/(key+'_native.md');path=b.TMP/(key+'_native.docx')
        md.write_text('$$\n'+b.EQUATIONS[key]+'\n$$\n',encoding='utf-8')
        b.run(['pandoc',str(md),'-o',str(path)])
        source=Document(path)
        matches=[p for p in source.paragraphs if p._p.xpath('.//m:oMath')]
        if not matches:raise RuntimeError('No native equation: '+key)
        CACHE[key]=copy.deepcopy(matches[0]._p)
    return copy.deepcopy(CACHE[key])


def equation(doc,key,number=None):
    p=doc.add_paragraph();p._p.addprevious(source_math(key))
    if number:
        p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(3)
        p.add_run('('+str(number)+')').font.size=Pt(7)
    else:p._p.getparent().remove(p._p)
    return p


def probe():
    doc=b.init_doc('수식 렌더 검사',True)
    equation(doc,'SIS',1);equation(doc,'R',2)
    path=b.TMP/'native_final_probe.docx';doc.save(path)
    pdf=b.convert(path,b.TMP)
    with fitz.open(pdf) as f:
        text='\n'.join(p.get_text() for p in f)
        ok=all(c in text for c in ('β','γ','∑','ρ','Γ'))
        f[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(b.RENDER/'native_final_probe.png')
    (b.ART/'math_render_probe.json').write_text(json.dumps({'method':'Pandoc complete native OMML paragraph, LibreOffice Math installed','text':text,'symbols_present':ok,'human_visual_review':False},ensure_ascii=False,indent=2),encoding='utf-8')
    if not ok:raise RuntimeError('Native math does not render. Check libreoffice-math installation.')


def finalize():
    jpath=b.ART/'document_check.json';checks=json.loads(jpath.read_text())
    rendered=[]
    for stem,expected in [('RDelay_참가신청서_v0.1',3),('RDelay_종합설계서_v0.1',26)]:
        docx=b.OUT/(stem+'.docx');pdf=b.OUT/(stem+'.pdf')
        native=len(Document(docx)._element.xpath('.//m:oMath'))
        with fitz.open(pdf) as f:
            text='\n'.join(p.get_text() for p in f)
            labels=[int(x) for x in re.findall(r'^\s*\((\d+)\)\s*$',text,re.M)]
            fonts=sorted({x[3] for p in f for x in p.get_fonts(full=True)})
        rendered.append({'path':str(pdf.relative_to(b.ROOT)),'native_math_count':native,'expected':expected,'number_labels':labels,'all_numbers_found':set(range(1,expected+1)).issubset(labels),'sis_glyphs_present':all(c in text for c in ('β','γ','∑')),'fonts':fonts})
    checks['rendered_equation_checks']=rendered
    checks['automatic_pass']=checks['automatic_pass'] and all(r['native_math_count']>=r['expected'] and r['all_numbers_found'] and r['sis_glyphs_present'] for r in rendered)
    checks['visual_review']='NOT PERFORMED: all pages rasterized; local runtime and remote image retrieval failed. Automatic checks are not human visual review.'
    checks['files']=[{'path':str(p.relative_to(b.ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.OUT.iterdir()) if p.is_file() and p.suffix!='.zip']
    jpath.write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 문서 검사 — 실제 실행 기록','',f'- 생성 입력 커밋: `{checks["source_commit"]}`',f'- 신청서 PDF: {checks["application"]["pages"]}쪽 (신청1+컨셉4)',f'- 종합설계 PDF: {checks["design"]["pages"]}쪽',f'- 요약 {checks["summary_characters_including_spaces"]}자 / 지원동기 {checks["motivation_characters_including_spaces"]}자 (공백 포함)',f'- 키워드 {checks["keyword_count"]}개 / 신청서 OMML 수식 {checks["native_omml_count"]}개','- 종합설계서 네이티브 수식 26개',f'- 팀정보 공란 오류: {checks["team_blank_errors"]}',f'- 본문 LaTeX 소스 노출: {checks["raw_latex_in_visible_docx_text"]}','- 전체 페이지 PNG 렌더링: 완료',f'- 쪽수·공란·수식 기호/번호·경계 자동 검사: {checks["automatic_pass"]}','- 육안검수: 미실행. 로컬 초기화 및 원격 이미지 조회 실패. 자동 검사와 구분함.','- 수리모델 수치시험·웹/API 실행·배포·현장 성능: 미실행','','## 파일','']
    lines += [f'- `{x["path"]}` — {x["bytes"]:,} bytes' for x in checks['files']]
    lines += ['','## 수식과 재현','- LibreOffice Math를 설치하고 Pandoc 네이티브 OMML 문단을 보존했다. PDF에서 β·γ·합 기호 및 모든 수식 번호를 검사했다.','- R_d=rho(K), K=diag(beta(1-x)) C Gamma^-1로 동등하게 표현하여 괄호 호환성을 높였다.','- 실제 실행 원본: scripts/build_native_documents.py 및 scripts/build_documents.py.','- 실행: python scripts/build_native_documents.py ; python scripts/audit_rendering.py','- 원본 PNG는 artifacts/rendered/. 문서 검사는 모델의 현실 적합성 검증이 아니다.','- Word의 다른 환경 재페이지화, 서명·증빙·자격·최신 공지는 별도 확인. 공식 HWP 픽셀 복제본이 아니다.']
    (b.ART/'document_check.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    package=b.OUT/'RDelay_v0.1_문서및생성원본.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for root in (b.DOCS,b.ROOT/'scripts',b.ROOT/'.github/workflows'):
            for p in root.rglob('*'):
                if p.is_file() and '__pycache__' not in str(p):z.write(p,str(p.relative_to(b.ROOT)))
        for p in [b.ROOT/'AGENTS.md',*b.OUT.glob('*.docx'),*b.OUT.glob('*.pdf'),b.ART/'environment_check.md',b.ART/'environment_check.json',b.ART/'document_check.md',jpath,b.ART/'math_render_probe.json']:
            z.write(p,str(p.relative_to(b.ROOT)))
    (b.ART/'package_manifest.json').write_text(json.dumps({'path':str(package.relative_to(b.ROOT)),'bytes':package.stat().st_size,'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'scope':'v0.1 documents and actual document generation source, not final service code'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    if not checks['automatic_pass']:raise RuntimeError('Document checks failed; inspect artifacts.')


def main():
    probe();b.equation=equation;b.main();finalize()

if __name__=='__main__':main()
