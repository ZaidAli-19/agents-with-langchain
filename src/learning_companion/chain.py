from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_google_genai import ChatGoogleGenerativeAI

from learning_companion.config import Settings

LEARNING_COMPANION_INSTRUCTION = (
    "You are a friendly Learning Companion. Explain things simply, in short plain English, "
    "and encourage the learner to keep going."
)

# Most recent earlier messages (user + assistant) taken from the current request. Nothing is stored.
MAX_HISTORY_MESSAGES = 10


class ConfigurationError(Exception):
    pass


def build_prompt() -> ChatPromptTemplate:
    """App-owned system instruction, request-provided history, then the current user message."""
    return ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=LEARNING_COMPANION_INSTRUCTION),
            MessagesPlaceholder("history"),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )


def split_conversation(messages) -> tuple[list[BaseMessage], str]:
    """Return (history, question) from request messages.

    The question is the latest user message with plain text. History is the supported user and
    assistant messages before it, in order, limited to MAX_HISTORY_MESSAGES. `system` messages and
    unsupported or empty content are ignored.
    """
    supported = [
        (m.role, m.content)
        for m in messages
        if m.role in ("user", "assistant") and isinstance(m.content, str) and m.content.strip()
    ]
    last_user = max((i for i, (role, _) in enumerate(supported) if role == "user"), default=None)
    if last_user is None:
        return [], ""
    earlier = supported[:last_user][-MAX_HISTORY_MESSAGES:]
    history = [
        HumanMessage(content=text) if role == "user" else AIMessage(content=text)
        for role, text in earlier
    ]
    return history, supported[last_user][1]


def prompt_roles(history: list[BaseMessage], question: str) -> list[str]:
    """Ordered message roles the prompt produces (no message text), for dev logging."""
    messages = build_prompt().format_messages(history=history, question=question)
    return [message.type for message in messages]


def build_chain(settings: Settings):
    """Prompt -> Gemini chat model -> text output."""
    if not settings.gemini_api_key:
        raise ConfigurationError("GEMINI_API_KEY is not set. Add it to your untracked .env file.")
    if not settings.gemini_model_name:
        raise ConfigurationError("GEMINI_MODEL_NAME is not set. Ask your instructor for the name.")
    prompt = build_prompt()
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model_name,
        google_api_key=settings.gemini_api_key,
    )
    return prompt | model | StrOutputParser()


STUDY_HELPER_INSTRUCTION = (
    "You are a friendly study helper for beginners. Explain the technical concept the learner "
    "asks about in short, plain English. Include a small example where it helps. End with exactly "
    "one small suggested next learning step. Be concise and encouraging. Never claim to research, "
    "browse, look up course material, or retrieve data, and never guarantee that your answer is "
    "correct."
)


def build_study_helper_prompt() -> ChatPromptTemplate:
    """Study-helper system instruction, request-provided history, then the current question."""
    return ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=STUDY_HELPER_INSTRUCTION),
            MessagesPlaceholder("history"),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )


def build_study_helper_chain(settings: Settings):
    """Study-helper prompt -> Gemini chat model -> text output."""
    if not settings.gemini_api_key:
        raise ConfigurationError("GEMINI_API_KEY is not set. Add it to your untracked .env file.")
    if not settings.gemini_model_name:
        raise ConfigurationError("GEMINI_MODEL_NAME is not set. Ask your instructor for the name.")
    prompt = build_study_helper_prompt()
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model_name,
        google_api_key=settings.gemini_api_key,
    )
    return prompt | model | StrOutputParser()
