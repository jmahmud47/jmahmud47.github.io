---
layout: page
title: Interactive Bug Reporting
description:
img: assets/img/interactive_br.webp
importance: 1
category: work
related_publications: true
---

Many software bugs are reported manually, particularly bugs that manifest themselves visually in the user interface. End-users typically report these bugs via app reviewing websites, issue trackers, or in-app built-in bug reporting tools, if available. While these systems have various features that facilitate bug reporting (e.g., textual templates or forms), they often provide limited guidance, concrete feedback, or quality verification to end-users, who are often inexperienced at reporting bugs and submit low-quality bug reports that lead to excessive developer effort in bug report management tasks. We propose an interactive bug reporting system for end-users (Burt), implemented as a task-oriented chatbot. Unlike existing bug reporting systems, Burt provides guided reporting of essential bug report elements (i.e., the observed behavior, expected behavior, and steps to reproduce the bug), instant quality verification, and graphical suggestions for these elements. We implemented a version of Burt for Android and conducted an empirical evaluation study with end-users, who reported 12 bugs from six Android apps studied in prior work. The reporters found that Burt's guidance and automated suggestions/clarifications are useful and Burt is easy to use. We found that Burt reports contain higher-quality information than reports collected via a template-based bug reporting system. Improvements to Burt, informed by the reporters, include support for various wordings to describe bug report elements and improved quality verification. Our work marks an important paradigm shift from static to interactive bug reporting for end-users.

<h2>References</h2>
<div class="publications">
  {% bibliography --group_by none --query @*[selected=interactive_br]* %}
</div>
