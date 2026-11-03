"""Streamlit UI: streamlit run app.py"""
import streamlit as st

from rag.retriever import index_exists

st.set_page_config(page_title="CS5342 Tutor", page_icon="🔐")
st.title("CS5342 Network Security Tutor")

if not index_exists():
    st.error("No knowledge base yet. Put the course files in data/raw and run `python ingest.py`.")
    st.stop()

from agents import qa_agent  # noqa: E402  (loads the embedding model; only once the index exists)

qa_tab, quiz_tab = st.tabs(["Q&A Tutor", "Quiz"])


def show(msg):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("Sources" + (" (includes web)" if msg.get("used_web") else "")):
                for n, label, url in msg["citations"]:
                    st.markdown(f"**[{n}]** " + (f"[{label}]({url})" if url else label))


with qa_tab:
    st.session_state.setdefault("qa", [])
    chat_box = st.container()
    with chat_box:
        for msg in st.session_state.qa:
            show(msg)
    if question := st.chat_input("Ask about the course, e.g. How does HMAC work?"):
        user_msg = {"role": "user", "content": question}
        st.session_state.qa.append(user_msg)
        with chat_box:
            show(user_msg)
            with st.spinner("Searching course materials..."):
                try:
                    result = qa_agent.answer(question)
                    bot_msg = {"role": "assistant", "content": result["answer"],
                               "citations": result["citations"], "used_web": result["used_web"]}
                except ConnectionError:
                    bot_msg = {"role": "assistant",
                               "content": "The local LLM isn't running. Start Ollama, then ask again."}
            st.session_state.qa.append(bot_msg)
            show(bot_msg)

with quiz_tab:
    st.info("Quiz Agent coming soon. It reuses `rag.retriever.retrieve` and `rag.llm.chat`.")
