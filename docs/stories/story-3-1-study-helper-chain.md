# Story 3.1 — Study-Helper Chain

## Purpose

Give the Learning Companion Chatbot a second LangChain behaviour: a study-helper chain that explains beginner technical concepts in plain language and ends with one small suggested next learning step. This story only **creates** the capability and a way to try it locally. The Open WebUI endpoint keeps using the existing general-chat chain; Story 3.2 adds the visible `/study` rule that chooses between the two.

Project path: the repository root (there is no `docs/config.yaml`).

## What this story implements in plain English

After this story, the project can do the following. Participants still chat exactly as before in Open WebUI.

- Greetings and ordinary conversation in Open WebUI work exactly as they did after Story 2.2. Nothing about that route changed.
- The implementer can run a local command that sends one question through a new study-helper chain and see its answer in the terminal.
- A study-helper answer gives a short plain-English explanation, a small example where it helps, and exactly one small next step to learn.
- The study-helper chain uses the same configured model, the same conversation-history handling, and the same app as general chat. It is a different set of instructions, not a different application.
- The study helper does not research, browse, or look up course material, and it does not promise to be correct.

This is a chain with its own instructions. It is not an autonomous agent, and nothing chooses it automatically yet.

## Prerequisites

- Story 2.2 is complete: `build_prompt()`, `split_conversation()`, `MAX_HISTORY_MESSAGES`, and `build_chain(settings)` in `src/learning_companion/chain.py` work, and Open WebUI answers follow-up questions.
- The untracked `.env` holds the existing model key and name. The repository's configured provider is Gemini via `langchain-google-genai` (the handout calls it "Grok"; the code and `.env.example` say Gemini). Keep the existing settings unchanged and do not switch providers.
- Open WebUI already points at `http://127.0.0.1:8000/v1`. Do **not** reinstall, reconfigure, modify, or build it.
- Before editing, read `docs/architecture.md`, Stories 1.1, 2.1 and 2.2, `.env.example`, and `src/learning_companion/` (`chain.py`, `main.py`, `config.py`). Preserve routes, settings, request/response behaviour, and `tests/test_health.py`.
- This document only describes the work. Do not install dependencies; everything needed is already installed.

## Work to do

Keep the change small. Add no dependencies, endpoints, settings, providers, UI, or storage.

### 1. `src/learning_companion/chain.py` (add only)

- Leave `LEARNING_COMPANION_INSTRUCTION`, `build_prompt()`, `build_chain(settings)`, `split_conversation()`, `prompt_roles()`, `ConfigurationError`, and `MAX_HISTORY_MESSAGES` exactly as they are. The general-chat chain stays untouched.
- Add `STUDY_HELPER_INSTRUCTION`, a separate application-owned instruction. It should tell the model to:
  - explain the beginner technical concept in short, plain English;
  - include a small example where useful;
  - end with exactly one small suggested next learning step;
  - be concise and encouraging;
  - never claim to research, browse, retrieve course data, or guarantee that the answer is correct.
- Add `build_study_helper_prompt()` returning a `ChatPromptTemplate` in the same shape as `build_prompt()`: fixed `SystemMessage(STUDY_HELPER_INSTRUCTION)`, `MessagesPlaceholder("history")`, then `HumanMessagePromptTemplate.from_template("{question}")`. User text goes only in the human slot; do not join strings into the instruction.
- Add `build_study_helper_chain(settings)` returning `study-helper prompt | the same Gemini chat model | StrOutputParser()`. Apply the same key and model-name checks, raise the same `ConfigurationError` messages, and construct the model from the same two settings. Do not edit `build_chain` to share code; a few repeated lines are acceptable here so the general chain stays untouched.
- Take the same `{"history": ..., "question": ...}` input as the general chain.

### 2. `src/learning_companion/study_dev.py` (new, development only)

A small command-line helper so the implementer can invoke the study-helper chain without touching the endpoint:

- Run as `uv run python -m learning_companion.study_dev "What is an API?"`.
- Read the question from the command-line argument, load settings with `get_settings()`, build the chain with `build_study_helper_chain`, call `invoke({"history": [], "question": question})`, and print the text answer.
- If `ConfigurationError` is raised, print its message and exit non-zero. Print no keys or instruction text.
- It is not imported by `main.py` and adds no route.

### 3. `docs/architecture.md`

- Add a short **Chain behaviours** section listing the two available behaviours and their responsibilities:

  | Behaviour | Where | Responsibility | Used by |
  | --- | --- | --- | --- |
  | General chat | `build_chain` | Friendly Learning Companion for greetings and ordinary conversation | Open WebUI endpoint (unchanged) |
  | Study helper | `build_study_helper_chain` | Plain-language beginner explanation, a small example where useful, one next step | Local dev command only |

- State that both use the same configured model, the same request-provided history shape, the same OpenAI-compatible endpoint, and the same Open WebUI chat.
- State clearly that this story creates the study-helper capability only; selection between the chains is Story 3.2.
- Update the **Planned layout** to include `study_dev.py`.

### Files this story changes

| File | Change |
| --- | --- |
| `src/learning_companion/chain.py` | add study-helper instruction, prompt, and chain builder |
| `src/learning_companion/study_dev.py` | new local development command |
| `docs/architecture.md` | chain behaviours section, layout line |

Do not change `main.py`, `config.py`, `.env.example`, `pyproject.toml`, `uv.lock`, routes, or Open WebUI. If one seems necessary, stop and say why.

### Out of scope

Routing or the `/study` rule, LLM-based classification, more specialists, loops, review steps, tools, retrieval, MCP, LangGraph, agents, a new endpoint, model provider, database, UI, broad tests, or production controls.

## Completion checks

Run only these and report the real results:

```
uv run ruff format .
uv run ruff check .
uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000
```

1. **General chat unchanged.** With the server running and the real key in `.env`, send one ordinary message in the existing Open WebUI, for example "Hi, how are you?". **Expected:** a friendly general reply as before, with no study-helper structure forced on it.
2. **Study-helper invocation.** Stop the server (or use a second terminal) and run:

   ```
   uv run python -m learning_companion.study_dev "What is an API?"
   ```

   **Expected:** the terminal prints a short plain-English explanation, a small example if useful, and exactly one suggested next learning step. It does not claim to have searched, browsed, or looked anything up, and it does not guarantee correctness.

Do not add routing, a test suite, or an evaluation harness.

## Handover

- List exactly which files changed and which commands were actually run, with outcomes.
- State whether the general-chat Open WebUI message behaved as before, and whether the study-helper answer had a plain explanation and one next step. If a check could not be run, say so plainly.
- Confirm `main.py` and the endpoint are unchanged, no key or instruction text was printed, and `.env` stays untracked.
- **Story 3.2 will extend this story** by adding the visible `/study` route rule in the application so Open WebUI messages starting with `/study` use the study-helper chain and everything else keeps using the general-chat chain. It will reuse `build_study_helper_chain` and the same history handling.
