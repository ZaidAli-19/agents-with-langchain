from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from learning_companion.config import Settings

LEARNING_COMPANION_INSTRUCTION = (
    "You are a friendly Learning Companion. Explain things simply, in short plain English, "
    "and encourage the learner to keep going."
)


class ConfigurationError(Exception):
    pass


def build_chain(settings: Settings):
    """Prompt -> Gemini chat model -> text output."""
    if not settings.gemini_api_key:
        raise ConfigurationError("GEMINI_API_KEY is not set. Add it to your untracked .env file.")
    if not settings.gemini_model_name:
        raise ConfigurationError("GEMINI_MODEL_NAME is not set. Ask your instructor for the name.")
    prompt = ChatPromptTemplate.from_messages(
        [("system", LEARNING_COMPANION_INSTRUCTION), ("human", "{question}")]
    )
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model_name,
        google_api_key=settings.gemini_api_key,
    )
    return prompt | model | StrOutputParser()
