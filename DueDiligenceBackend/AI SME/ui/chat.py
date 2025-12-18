import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="Local RAG Bot", layout="centered")
st.title("📚 Local RAG Bot (AWS-ready)")

with st.sidebar:
    st.header("Upload")
    f = st.file_uploader("Add a document", type=["pdf","txt","md","docx","csv"])
    title = st.text_input("Optional title")
    if f and st.button("Upload"):
        files = {"file": (f.name, f.getvalue())}
        data = {"title": title}
        r = requests.post(f"{API}/upload", files=files, data=data)
        st.success(r.json())

if "history" not in st.session_state:
    st.session_state["history"] = []

q = st.text_input("Ask a question about your documents")
if st.button("Ask") and q.strip():
    r = requests.post(f"{API}/query", data={"q": q})
    payload = r.json()
    st.session_state["history"].append(("user", q))
    st.session_state["history"].append(("assistant", payload.get("answer","")))
    st.caption(f"Retrieved {payload.get('hits',0)} chunks")

for role, msg in st.session_state["history"]:
    if role == "user":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")
