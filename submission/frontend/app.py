import os
import time

import httpx
import streamlit as st

from search_agent.citations import citation_page_label

base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
st.title("Internet Search Agent")
if "messages" not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
if question := st.chat_input("Ask about a sustainability report"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        progress = st.status("Submitting research request")
        with httpx.Client(timeout=30) as client:
            request_id = (
                client.post(f"{base}/api/v1/query", json={"question": question}).raise_for_status().json()["request_id"]
            )
            while True:
                state = client.get(f"{base}/api/v1/status/{request_id}").raise_for_status().json()
                progress.update(label=state["stage"])
                if state["stage"] in ("completed", "failed"):
                    break
                time.sleep(0.5)
            result = client.get(f"{base}/api/v1/requests/{request_id}").raise_for_status().json()
        progress.update(label="Completed", state="complete")
        st.markdown(result["answer"])
        with st.expander("Sources"):
            for source in result["sources"]:
                physical_page = source.get("pdf_page")
                printed_page = source.get("printed_page")
                page_label = citation_page_label(printed_page, physical_page)
                st.markdown(
                    f"**[{source['citation_number']}] "
                    f"[{source['title']}]({source['url']})**  \n"
                    f"{source.get('company') or 'Web'} · "
                    f"{source.get('reporting_year') or 'year unknown'} · {page_label}"
                )
                st.caption(source["snippet"])
        if result["warnings"]:
            st.warning("\n\n".join(result["warnings"]))
    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
