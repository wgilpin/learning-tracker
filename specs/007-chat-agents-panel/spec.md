# Feature Specification: Chat Agents Panel

**Feature Branch**: `007-chat-agents-panel`  
**Created**: 2026-04-02  
**Status**: Draft  
**Input**: User description: "The app should have a chat interface in a pane to the right. There will be several agents, allowing questions about the material, setting the user questions to answer with assessment, or expanding content in a given area"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a Question About the Material (Priority: P1)

A learner is reviewing topic content and wants to ask a clarifying question. They open the chat pane and type their question in natural language. The system answers directly, drawing on the topic's syllabus and source material. No agent is explicitly invoked — answering is the default behaviour.

**Why this priority**: This is the core use case — giving learners on-demand access to their material through conversation. It delivers immediate value and establishes the baseline that specialist tools extend.

**Independent Test**: Can be fully tested by opening a topic with existing source material, submitting a question in the chat, and verifying the response references the material accurately.

**Acceptance Scenarios**:

1. **Given** a logged-in user is on a topic detail page, **When** they open the chat pane at the start of a session, **Then** a single chat input is shown alongside two suggested message buttons: "Give me the quiz" and "Set me a question".
2. **Given** the chat pane is at the start of a session, **When** the user clicks a suggested message button, **Then** the corresponding message is submitted as if the user had typed and sent it.
3. **Given** the conversation has messages in it, **When** the user views the pane, **Then** the suggested message buttons are not shown.
4. **Given** a session has been reset (e.g., the user navigated away and returned), **When** the pane is opened again, **Then** the suggested message buttons reappear.
5. **Given** the chat pane is open, **When** the user submits a question about the material, **Then** a response is streamed into the chat referencing the topic's content.
6. **Given** a question is submitted, **When** the system has no relevant content to draw from, **Then** the response informs the user and suggests they add source material to the topic.
7. **Given** a conversation is in progress, **When** the user asks a follow-up question, **Then** the system maintains context from earlier in the same session.

---

### User Story 2 - Chapter Quiz (Priority: P2)

A learner wants to formally test their knowledge of a chapter. They ask to be quizzed (e.g., "set me a quiz on chapter 3"). The system retrieves the stored quiz for that chapter — a fixed set of questions and answers generated once and persisted with the chapter record. The learner works through the questions, and when they achieve a passing score the chapter is marked as passed.

**Why this priority**: A quiz with a pass/fail outcome gives learners a concrete milestone and motivates completion. Recording pass state against the chapter turns it into a trackable progress signal.

**Independent Test**: Can be fully tested by requesting a quiz for a chapter, completing all questions, and verifying that the chapter is marked as passed in the UI when the score meets the threshold.

**Acceptance Scenarios**:

1. **Given** the user requests a quiz for a chapter, **When** the system detects quiz intent and a quiz already exists for that chapter, **Then** the stored questions and answers are retrieved and presented to the user.
2. **Given** the user requests a quiz for a chapter, **When** no quiz has been generated for that chapter yet, **Then** a set of multiple-choice questions (3–4 options each) is generated from the chapter's material, stored against the chapter, and presented.
3. **Given** questions are presented, **When** the user selects an answer for each, **Then** immediate feedback is shown after each answer (correct/incorrect with explanation).
4. **Given** all questions in a quiz are answered, **When** the score meets or exceeds the passing threshold, **Then** the chapter is recorded as passed and the UI reflects this change.
5. **Given** all questions are answered, **When** the score does not meet the passing threshold, **Then** the result is shown with a summary of which areas were weak, and the chapter is not marked as passed.
6. **Given** a chapter is already marked as passed, **When** the user requests the quiz again, **Then** the same stored quiz is presented showing their previous answers, and they can re-answer to update their result.
7. **Given** a user has previously completed a quiz, **When** they return to the quiz, **Then** their most recent answers are shown alongside the questions so they can see what they answered before.

---

### User Story 3 - Socratic Questioning Dialogue (Priority: P3)

A learner wants to be challenged on their understanding through conversation. They ask for a question (e.g., "lead me through a question" or "question my understanding"). The system enters a Socratic dialogue: it asks one open-ended question at a time, rooted in the topic's material, and generates each follow-up question based on what the user just said. It never lectures or corrects directly — if an answer reveals a gap or misconception, the next question is designed to make that contradiction visible. The dialogue ends when the user demonstrates accurate understanding in their own words. Nothing is recorded; the dialogue is generated on demand and exists only within the session.

**Why this priority**: Socratic questioning develops genuine understanding rather than pattern-matching. It forces the learner to construct and defend an explanation, exposing gaps that recognition-based formats miss. It is secondary to the quiz because it produces no persistent outcome.

**Independent Test**: Can be fully tested by requesting questioning on a topic, giving a partially correct answer, and verifying the follow-up question probes the gap rather than providing the correct answer directly.

**Acceptance Scenarios**:

1. **Given** the user requests to be led through a question, **When** the system detects the intent, **Then** it poses exactly one open-ended question grounded in the topic's material — never two at once.
2. **Given** a question has been posed, **When** the user gives a vague or imprecise answer, **Then** the system asks a narrower follow-up question to force specificity rather than accepting the answer or correcting it.
3. **Given** the user's answer contains a misconception, **When** the system responds, **Then** it asks a question that makes the contradiction visible ("You said X — what happens when Y?") rather than stating the user is wrong.
4. **Given** the user gives a correct and precise answer, **When** the system responds, **Then** it advances to a harder or more specific question rather than repeating ground already covered.
5. **Given** the user demonstrates accurate understanding with their own words and a concrete example, **When** the system evaluates the answer, **Then** it acknowledges the understanding and concludes the questioning rather than continuing indefinitely.
6. **Given** a Socratic session is in progress, **When** the user asks a direct question (stepping out of the Socratic mode), **Then** the system answers it and then resumes the dialogue.

---

### User Story 4 - Expand a Content Area (Priority: P4)

A learner wants to explore a concept in more depth. They ask about it in the chat (e.g., "can you tell me more about X" or "expand on chapter 3"). The system detects the expansion intent, routes to the Content Expansion agent, and returns enriched explanations, examples, or related concepts drawn from source material.

**Why this priority**: Expands the value of the material already in the system without requiring the user to leave the app. Dependent on P1 infrastructure being in place.

**Independent Test**: Can be fully tested by sending an expansion-style message about a named chapter or concept and verifying the response adds depth beyond what the syllabus item already shows.

**Acceptance Scenarios**:

1. **Given** the user sends a message requesting more detail on a concept or chapter, **When** the system detects expansion intent, **Then** a richer explanation with examples or elaboration is returned.
2. **Given** the agent returns expanded content, **When** the source material does not cover the requested area, **Then** the response clearly states the limits of available material rather than generating unsupported content.

---

### Edge Cases

- What happens if the system cannot confidently determine intent from a user message? The system defaults to Q&A behaviour and responds as best it can, rather than asking the user to rephrase.
- What happens if the chat pane is opened on a topic with no source material or syllabus items? The system responds to the first message by informing the user what material is needed before it can assist.
- What happens if the response takes too long? The user sees a loading indicator; if no response arrives within a reasonable window, a timeout message with a retry option is shown.
- What happens if the user navigates away from the topic while a response is streaming? The client-side chat state is discarded; returning to the topic starts a fresh session.
- What happens if the user requests a quiz but does not specify a chapter? The system asks which chapter to quiz on, or quizzes across all chapters if the topic has few enough to make that tractable.
- What happens if a chapter has insufficient material to generate a quiz? The system informs the user and does not attempt to generate questions.
- What happens if the user gives a confidently wrong answer in the Socratic dialogue? The system does not correct directly — it poses a question designed to make the error visible through reasoning.
- What happens if the user asks to stop being questioned mid-dialogue? The system exits the Socratic mode and returns to normal Q&A behaviour.
- What happens if the topic material is too thin to sustain a multi-turn Socratic dialogue? The system asks what questions it can from available material and notifies the user when it is exhausted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST display a chat pane to the right of the main topic content area, togglable without navigating away from the topic.
- **FR-002**: The chat pane MUST present a single, unified chat input — no agent selection UI is exposed to the user.
- **FR-002a**: When the chat session is empty, the pane MUST display two suggested message buttons — "Give me the quiz" and "Set me a question" — styled as muted/secondary actions. Clicking either submits that text as the user's first message. The buttons MUST disappear once the conversation begins.
- **FR-003**: The system MUST answer user messages directly by default, drawing on the topic's syllabus and source material.
- **FR-004**: The system MUST invoke the Quiz tool when the user's message indicates an intent to be formally quizzed on a chapter; the tool retrieves the stored quiz for that chapter if one exists, or generates and persists a new one if not. It presents the questions to the user, evaluates each selected answer with immediate feedback, and records the quiz outcome against the chapter when complete.
- **FR-005**: A chapter's quiz questions and answers MUST be generated once and stored against the chapter record; subsequent quiz attempts for the same chapter MUST use the same stored questions, not regenerate them.
- **FR-006**: The user's answers from the most recent quiz attempt MUST be persisted against the chapter record alongside the questions, so that returning to the quiz shows the learner's prior responses.
- **FR-007**: A chapter MUST be recorded as passed when the user completes its quiz and achieves a score meeting or exceeding the passing threshold; this pass state MUST persist across sessions.
- **FR-008**: The system MUST invoke the Socratic Questioning tool when the user's message indicates an intent to be led through questioning; the tool poses one open-ended question at a time derived from the topic's material, generates each follow-up question based on the user's prior answer, never corrects the user directly, and concludes when the user demonstrates accurate understanding. No outcome is recorded.
- **FR-009**: The system MUST invoke the Content Expansion tool when the user's message indicates an intent to explore a concept or chapter in greater depth; the tool returns enriched explanations or examples drawn from available source material.
- **FR-010**: Specialist tools (Quiz, Socratic Questioning, Content Expansion) MUST only be invoked when the intent clearly warrants it; all other messages are answered directly.
- **FR-011**: The chat pane MUST support multi-turn conversations, maintaining message history within a single client-side session.
- **FR-012**: All agents MUST gracefully communicate the limits of available material rather than fabricating unsupported answers.
- **FR-013**: The chat session MUST be scoped to the current topic — navigating to a different topic resets the session.
- **FR-014**: Agent responses MUST be streamed progressively to the user rather than shown only after full completion.

### Key Entities

- **Chat Session**: A transient, client-side conversation state scoped to the current topic page visit. Contains an ordered list of messages. Not persisted to the server; lost on page navigation or refresh.
- **Chat Message**: A single turn in a session — either a user input or a system response, with a role and content. Exists only in browser memory.
- **Tool (Agent)**: A specialist capability (Quiz, Socratic Questioning, Content Expansion) invoked internally by the system when user intent warrants it. Invisible to the user. The default behaviour — answering directly — requires no tool invocation.
- **Chapter Quiz**: A persistent record stored against the chapter — contains the generated questions, correct answers, the learner's most recent responses, the outcome (pass/fail), and the chapter's pass state. Generated once; reused on every subsequent attempt. Survives page navigation and session boundaries.
- **Chapter Pass State**: A flag on a chapter record indicating the learner has passed at least one quiz for that chapter. Displayed in the UI to signal progress.
- **Socratic Dialogue State**: The in-session record of the questioning thread — questions asked, answers given, and the agent's running assessment of where the user's understanding stands. Used to generate context-appropriate follow-up questions. Exists only within the current session; never persisted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive a first response within 10 seconds of submitting their first message.
- **SC-002**: The system invokes specialist tools (Quiz, Socratic Questioning, Content Expansion) for at least 90% of messages where the intent clearly warrants them, and avoids invoking them when the intent does not — validated by spot-check testing across representative message types.
- **SC-003**: Direct answers and Content Expansion responses accurately reference content present in the topic's source material in at least 90% of sessions (measured by spot-check review).
- **SC-004**: When a user completes a passing quiz, the chapter's pass state is updated and visible in the UI within the same page session — no refresh required.
- **SC-005**: In a Socratic dialogue, follow-up questions demonstrably respond to the content of the user's prior answer — not a pre-scripted sequence — verified by spot-check review of transcripts.
- **SC-006**: The Socratic agent never directly states that a user's answer is wrong; it always responds to incorrect answers with a question. Validated by reviewing session transcripts for direct corrections.
- **SC-007**: Users can complete a full quiz round-trip (receive questions → answer all → receive outcome → chapter marked passed) without leaving the topic page.
- **SC-008**: The chat pane does not obscure the primary content area — both panes are usable simultaneously on a standard desktop viewport.

## Clarifications

### Session 2026-04-02

- Q: What format do assessment questions take? → A: Two distinct tools. Quiz tool: multiple-choice, recorded, chapter pass state persisted. Socratic Questioning tool: open-ended, one at a time, no recording.
- Q: Where is chat session state stored? → A: Client-side only — session lives in the browser for the page visit; nothing written to the server.
- Q: How does the user select which agent to use? → A: Agents are invisible to the user — there is one chat box and the system automatically routes each message to the appropriate agent based on intent.
- Q: What is the default behaviour when no specialist agent is needed? → A: Agents are tools — the system attempts to answer directly by default and only invokes a specialist agent (Socratic Questioning, Content Expansion) when the intent clearly warrants it.

### Session 2026-04-03

- Q: What is the questioning approach? → A: Socratic method — one question at a time, generated from the user's prior answer rather than a fixed script. The agent never corrects directly; it poses questions that expose contradictions. The dialogue ends when the user demonstrates understanding, not after a fixed number of questions.

### Session 2026-04-04

- Q: Is the quiz a separate tool from Socratic questioning? → A: Yes. "Set me a quiz" invokes the Quiz tool — multiple choice, records pass state against the chapter, persists across sessions. "Lead me through a question" invokes the Socratic Questioning tool — open-ended dialogue, no recording, generated on demand.
- Q: Are quiz questions regenerated each time? → A: No. Questions and answers are generated once and stored against the chapter record. The learner's most recent responses are also persisted, so returning to a quiz shows what they answered previously.
- Q: How should references be formatted when author information is missing? → A: If a source has no known authors, the authors field is omitted entirely from the reference string — do not substitute a placeholder like "Unknown".

## Assumptions

- The feature is scoped to the topic detail page; chat is not available as a global floating panel in this iteration.
- Users are authenticated — the chat panel is only accessible to logged-in users.
- Each topic's syllabus and source material is already available in the system and forms the knowledge boundary for all agents; no external knowledge base is introduced.
- Chat session state is held entirely in the browser (client-side) for the duration of the page visit; no session data is written to the server. Persistence across sessions is out of scope.
- Mobile layout is out of scope — the dual-pane design targets desktop/tablet viewports only.
- The Quiz tool generates questions per chapter and records pass state against the chapter record; quiz results persist across sessions.
- The Socratic Questioning tool generates questions on demand from the session's conversational history; nothing from a Socratic dialogue is persisted to the server.
- Specialist tools (Quiz, Socratic Questioning, Content Expansion) are invoked automatically based on detected intent; users are never prompted to choose a tool explicitly.
- The Socratic agent uses the full conversational history of the current session to inform each follow-up question — it needs the prior exchange to know what the user said, not just what the material contains.
- The agent determines when to conclude a Socratic dialogue based on answer quality; there is no fixed question count or timer.
- The passing threshold for a quiz is not specified in this iteration and should be defined during planning.
- The default behaviour for any message is a direct answer grounded in the topic's material; tools are only invoked when the intent clearly warrants it.
