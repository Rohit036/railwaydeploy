import streamlit as st

st.set_page_config(page_title="Sample Streamlit App")
st.title("Sample Streamlit App")
st.write("Hello from Streamlit on Railway!")

value = st.slider("Pick a number", 0, 100, 25)
st.write("You picked:", value)
