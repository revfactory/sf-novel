# Harness architecture infographic

Generation mode: built-in `image_gen`.

## Prompt

Use case: infographic-diagram
Asset type: a finished high-resolution landscape infographic for the README of the open-source Korean SF writing project "sf-novel".
Primary request: Explain the project's REAL harness architecture as an elegant isometric infographic. This is an architecture illustration, not a screenshot and not a novel book cover.
Canvas: wide landscape, approximately 16:10, at least 2400px wide if supported. Warm near-white opaque background, spacious editorial margins. Refined isometric 3D miniature modules with consistent 30-degree axes, soft ambient shadows, clear edges and restrained translucent elements. Rich but disciplined visual craft. Muted teal, violet and amber accent families distinguish stages, dark ink typography. No busy background, logos, watermarks, robots, people or invented statistics.

Layout and architecture:
Top: large title "SF NOVEL" with subtitle "하네스 아키텍처". A compact elevated central orchestration console is the highest-level node, labeled exactly "ORCHESTRATOR", with a clear Korean sublabel "계획 · 배정 · 정본 통합". Fine dotted control lines connect this main-session hub to the five specialist modules below. The hub is not a sixth peer worker.
Middle: three clearly separated stage platforms arranged left-to-right:
1. A design platform, labeled "설계", containing two distinct matching isometric specialist modules: "WORLDBUILDER" / "세계관 · 기술 규칙" with a small globe and scientific blueprint; "PLOTTER" / "인물 · 인과 플롯" with branching scene cards. Caption "공통 전제 · 설계 동기화". These two work from shared premises, not isolated incompatible worlds.
2. A writing platform, labeled "집필", with a single clear module "WRITER" / "장면 · 원고 · 퇴고", illustrated with layered pages and a pen. Caption "연속 장면은 순차 집필".
3. A review platform, labeled "검토", containing two equal specialist modules: "EDITOR" / "서사 · 문장" with a magnifying glass and text page; "CONTINUITY" / "시간선 · 설정" with a clock and connected timeline. Caption "동일 원고 병렬 검토". Both review the same fixed manuscript version. They return findings rather than rewriting shared canon.
Thin, legible solid arrows show the large-scale flow from design to writing, then split from writer to BOTH reviewer modules; a single clearly indicated return arrow from the review platform to WRITER is labeled "수정 · 재검토". Do not draw a forward arrow from EDITOR to CONTINUITY: they are parallel reviewers, not sequential.

Bottom: three tidy horizontal support tiles on a common low isometric foundation, each with one icon and readable label:
"CANON" / "정본은 메인만 갱신" / "novel/canon/"
"MANUSCRIPT" / "원고 버전 보존" / "novel/manuscript/"
"RUN LOG" / "기록 · 변경분 재실행" / ".harness/runs/"
These tiles represent shared artifacts and local execution infrastructure, not three additional agents. Connect CANON to the orchestration hub with a subtle line; do not show peer workers directly writing CANON.
A small quiet footer can state exactly "구상 → 설계 → 집필 → 검토 → 수정·통합".

Text requirements: Render all quoted labels verbatim, with accurate Korean Hangul. Clean contemporary sans-serif, upright flat labels facing the viewer, not heavily perspective-warped. Strong hierarchy, large enough to read in a GitHub README at about 1000px display width. Limit text to the supplied labels. Avoid tiny paragraphs. Preserve the distinction of one main orchestrator plus exactly FIVE specialist workers.
Quality priorities: first topology and all five correct role labels; second readable Korean and clean arrow routing; third polished tactile isometric illustration. Plenty of whitespace; no decorative spaghetti connections.
