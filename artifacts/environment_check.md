# 실행환경 확인

- timestamp_utc: 2026-10-20T17:05:23.498795+00:00
- branch: codex/rdelay-bootstrap
- source_commit: 89186cb8e0e0d2a003b1992f2f28d32185129153
- git_status_before: ## codex/rdelay-bootstrap...origin/codex/rdelay-bootstrap
?? artifacts/build_tmp/lo-profile-probe_display_math/
?? artifacts/build_tmp/lo-profile-probe_inline_math/
?? artifacts/build_tmp/lo-profile-probe_original/
?? artifacts/build_tmp/lo-profile-probe_whole_paragraph/
?? artifacts/build_tmp/native_probe.docx
?? artifacts/build_tmp/native_probe.md
?? artifacts/build_tmp/probe_display_math.docx
?? artifacts/build_tmp/probe_display_math.pdf
?? artifacts/build_tmp/probe_inline_math.docx
?? artifacts/build_tmp/probe_inline_math.pdf
?? artifacts/build_tmp/probe_original.docx
?? artifacts/build_tmp/probe_original.pdf
?? artifacts/build_tmp/probe_whole_paragraph.docx
?? artifacts/build_tmp/probe_whole_paragraph.pdf
?? artifacts/math_render_probe.json
?? artifacts/rendered/probe_display_math.png
?? artifacts/rendered/probe_inline_math.png
?? artifacts/rendered/probe_original.png
?? artifacts/rendered/probe_whole_paragraph.png
?? scripts/__pycache__/
- python: 3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]
- platform: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39
- git: git version 2.55.0
- pandoc: pandoc 3.1.3
- libreoffice: LibreOffice 24.2.7.2 420(Build:2)
- render_engine: PyMuPDF 1.26.5
- font: NanumGothic.ttf: "NanumGothic" "Regular"
- skills: {'docx': {'present': False}, 'pdfs': {'present': False}}
- local_chat_runtime: container/Python initialization failed before commands; remote workflow used
- service_tests: not run
- file_write_read_delete_probe: pass

저장소에는 공고·양식 PDF가 없었으며 대화 첨부자료를 사용했다. 로컬 skill 경로는 접근 시도했으나 런타임 초기화 오류로 읽지 못했다. 원격 경로도 위 present/read 기록 외 읽었다고 주장하지 않는다.
