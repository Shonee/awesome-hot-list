# Design QA

## Comparison Target

- Source visual truth: `reference-bilibili-multi-ranking.png`, `reference-rank-trajectory-table.png`, `reference-channel-card-height-gap.png`
- Rendered implementation: `prototype-bilibili-focus.png`, `prototype-today-rank-curves-desktop.png`, `prototype-latest-desktop.png`
- Responsive evidence: `prototype-today-rank-curves-mobile.png`, `prototype-latest-mobile.png`
- New source pixels: 1762 x 918 and 2934 x 1334
- Desktop implementation pixels: 1425 x 990
- Mobile implementation pixels: 375 x 812
- Requested CSS viewports: 1440 x 1000 and 390 x 844
- Device scale factor: 1; screenshots reflect the in-app browser content viewport after scrollbar and browser surface deductions.
- States: 今日报告排名轨迹、历史报告排名轨迹、最新热榜卡片网格、哔哩哔哩多榜单、移动端堆叠曲线。

The source images identify component problems and target behaviors rather than prescribing a full-page visual clone. The implementation keeps the established editorial design language.

## Full-View Comparison Evidence

- Numeric rank cells were replaced by one small smooth line chart per topic. Rank 1 maps to the top of the plot, so upward visual movement consistently means rising heat.
- Missing snapshots create a real break in the line; existing snapshots remain connected. This distinguishes “not on list” from a ranking change.
- Every available point is a 12-14 px interactive target. Hover or keyboard focus displays time and exact rank, for example `13:00 · 热榜排名 #1`.
- Today and history reports use the same chart component and differ only in their time labels and data.
- The first desktop card row measured `[552, 552, 552, 552]` px with matching bottom coordinates. Bilibili keeps its three ranking tabs without increasing the row height.
- Single-ranking cards let the scroll body expand into the space not used by tabs, avoiding a blank strip while preserving equal outer height.
- At the mobile viewport, both page overflow and chart-panel overflow measured `0`; each topic stacks its full-width curve below the topic and trend label.

## Focused Region Comparison Evidence

- Rank trajectory: the former five-number scan is now a continuous shape with subdued time/grid guides and semantic red, blue and teal paths. The exact number remains available on demand rather than competing with the shape.
- Card row: the former gap below shorter cards is removed. All cards share one grid-row height while retaining independent internal scrolling and multi-ranking tabs.
- Bilibili multi-ranking behavior from the earlier reference remains intact.

## Findings

- No actionable P0/P1/P2 mismatch remains for the two requested optimizations.
- Fonts and typography: topic names, tenure and trend labels retain the existing hierarchy. Tooltip text remains compact and does not cover adjacent labels.
- Spacing and layout rhythm: desktop charts preserve aligned time columns; mobile charts stack without horizontal scrolling. Card borders and bottoms align across each grid row.
- Colors and visual tokens: trend curves reuse existing hot, blue and teal semantic tokens and adapt to the night theme.
- Image quality and asset fidelity: the requested elements are data visualizations and layout components; no raster content asset is required.
- Copy and content: report labels, topic names, time points and trend states are unchanged. Exact rank values moved into contextual tooltips.
- Accessibility and state: each plot has a descriptive `role="img"` label, every point is a keyboard-focusable button with an exact rank label, and reduced-motion preferences disable the fade animation.

## Interaction Verification

- Hovered the first topic's final point and confirmed tooltip opacity `1` with text `13:00 · 热榜排名 #1`.
- Today chart: 5 rows, 5 curves, 23 available points.
- History chart: 5 rows, 5 curves, 23 available points.
- Card grid: first-row heights and bottoms are identical; document horizontal overflow is `0`.
- Compact list and channel Tabs layouts still render without horizontal overflow; card layout was restored afterward.
- Mobile card width is 343 px at the requested 390 px viewport.
- Mobile curve plot width is 305 px with no page or panel overflow.
- Existing local channel order, count and visibility preferences were preserved.

## Comparison History

- Earlier iteration: multi-ranking, theme and layout behavior passed.
- Current pass 1 found a P2 issue: SVG stroke-dash animation introduced false visual gaps between valid data points. The stroke animation and normalized dash were removed; post-fix paths are continuous and computed `stroke-dasharray` is `none`.
- Current pass 1 also found a P2 mobile issue: the new chart required internal horizontal scrolling. The mobile structure was changed to a two-row layout with a full-width plot; post-fix panel overflow is `0`.
- Current pass 2 found no remaining P0/P1/P2 issue in the desktop, history, card-grid or mobile evidence.

## Follow-up Polish

- P3: real data with many more time slices may benefit from selective point density or a focused detail view; the current five-point prototype does not require it.

final result: passed
