---
layout: page
title: Assessing Bug Report Quality
description:
img: assets/img/bug-report-quality.webp
importance: 1
category: work
related_publications: true
---

Bug reports are essential for developers to confirm software problems, investigate their causes, and validate fixes. Unfortunately, reports often miss important information or are written unclearly, which can cause delays, extra issue resolution efforts, or even the inability to solve the issues. One of the often problematic components of reports is the steps to reproduce the bugs (S2Rs), which are essential to replicate the described bug(s) and reason about fixes. Given the proclivity for deficiencies in reported S2Rs, prior work has proposed techniques that assist reporters in writing S2Rs or assessing the quality of reported S2Rs. However, automated understanding of S2Rs is a challenging problem that requires linking nuanced natural language phrases with specific program information -- which prior techniques struggle with due to issues related to language variability and limitations of information gleaned from program analysis. Such challenges make it difficult to infer the language to program connections needed for S2R understanding.  

To more effectively tackle the problem of S2R quality annotation, we propose a new technique called AstroBR, which leverages the language understanding capabilities of LLMs to identify and extract, the S2Rs from bug reports and match them to GUI interactions in a program state model gleaned from dynamic analysis. We compared AstroBR to a related state-of-the-art approach and we found that AstroBR annotates S2Rs 25.2% better (in terms of F1 score) than the baseline. 
Additionally, AstroBR suggests more accurate missing S2Rs than the baseline (by 71.4% in terms of F1 score.).

<h2>References</h2>
<div class="publications">
  {% bibliography --group_by none --query @*[selected=astrobr]* %}
</div>

