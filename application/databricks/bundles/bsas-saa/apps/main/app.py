"""Application shell with optional settings and no backend startup calls."""

import streamlit as st
from libs.app.context import RequestContext
from libs.app.environment import ENV

st.set_page_config(page_title="DataForge", layout="wide")

navigation = st.navigation([st.Page("pages/home.py", title="Home", default=True)])
with st.sidebar:
    st.text("DataForge")
    context = RequestContext.current()
    if user_name := context.user_name or context.user_email:
        st.text(user_name)
    if ENV.ENV_NAME:
        st.text(f"Environment: {ENV.ENV_NAME}")

navigation.run()
