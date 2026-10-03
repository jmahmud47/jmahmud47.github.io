---
layout: page
title: Automated Program Repair
description: How well do repair tools and LLM agents fix UI-centric Android bugs?
img: assets/img/code-repair.webp
importance: 3
category: work
related_publications: true
---

This project conducts the first comprehensive empirical study of how five recent automated program repair techniques function on UI-centric bugs derived from Android applications. To carry out this study, we created a dataset called DroidFixBench, containing 50 real bugs and 46 synthetic bugs. After performing an open-coding analysis, we identified nine key categories of failures, which can inform future work on UI-centric program repair. Later, we extended our work by applying LLMs (Claude, Codex, Gemini) with agentic AI workflows to evaluate their performance on the same dataset.

<h2>References</h2>
<div class="publications">
  {% bibliography --group_by none --query @*[selected=apr]* %}
</div>
