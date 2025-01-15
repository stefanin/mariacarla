%pip install -qU langchain-ollama
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="aristide",
    temperature=0,
    # other params...
)

from langchain_core.messages import AIMessage

messages = [
    (
        "system",
        "Ti chiami Aristide e parli italiano.",
    ),
    ("human", "Ti piace programmare"),
]
ai_msg = llm.invoke(messages)
print(ai_msg.content)
ai_msg = llm.invoke("che ore sono")
print(ai_msg.content)
ai_msg = llm.invoke("sincronizzati con un NTP e dimmi che ore sono")
print(ai_msg.content)
