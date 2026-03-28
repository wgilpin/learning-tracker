# Academic Learning Tracker: Concept Summary

* **Objective:** A source-grounded, AI-driven application for mastering complex subjects.
* **Primary Artifact:** A stateful, hierarchical syllabus (interactive to-do list) that maps to a "Virtual Book."

## System Architecture

* **Virtual Book Model:** One master document per broad topic, composed of "Atomic Chapters."
* **Monorepo Structure:** Managed via `uv` workspaces.
* **Shared Engine:** `documentlm-core` package handles RAG, vector storage, database base models, and Google ADK agent orchestration.
* **State Management:** `SyllabusItem` entity tracks progress (`Unresearched`, `In Progress`, `Mastered`) and enforces prerequisites.

## Agent Orchestration

* **Syllabus Architect:** Replaces standard planner. Generates prerequisite-aware dependency graphs and identifies bottleneck concepts.
* **Academic Scout:** Replaces general web search. Curates rigorous sources (ArXiv, educational channels) into a verification queue.
* **Chapter Scribe:** Replaces general drafter. Synthesizes deep-dive explanations for single syllabus nodes using only verified Core Bucket sources.

## User Workflow & UI

* **Initialization:** User defines topic -> Architect builds the syllabus checklist.
* **Targeted Drafting:** User expands a single to-do item. The Scribe drafts only that section.
* **Context Folding:** To maintain logical consistency without breaking context limits, the Scribe receives the master overview and summaries of preceding chapters, rather than full text.
* **Pedagogical Blocking:** The system prevents drafting advanced concepts if prerequisite nodes are incomplete.
* **Active Reading:** User interacts via margin comments to request expanded derivations or simplified analogies.
* **Automated Aggregation:** Local chapter citations compile into a dynamic master bibliography.
