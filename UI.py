import streamlit as st
import time
import altair as alt
import pandas as pd
from text2sql import get_question_response
from streamlit_extras.app_logo import add_logo
import base64

COLOR_BLUE = "#1C83E1"
COLOR_CYAN = "#00C0F2"

logo = "D:/LMU/Text2SQL/openai_test/itanta_newlogo.jpg"

st.set_page_config(page_title="I can Retrieve Any SQL query")

def get_base64_of_bin_file(png_file):
    with open(png_file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

add_logo("https://imgur.com/a/S4M8qL7")

st.sidebar.button("Button")
st.sidebar.button("Button 2")

a, b = st.columns([1, 10])

st.title("Type your question and see the magic!")

question=st.text_input("Input: ",key="input")

submit=st.button("Ask the question")

if submit:

    with st.spinner("Fetching data......"):
        db = "loss-data.db"

        row_dict = get_question_response(db, question)

        print(row_dict)

        df = pd.DataFrame(row_dict)
        
    if "Duration" in df.columns or "Total_Duration" in df.columns:
        st.altair_chart(
        alt.Chart(df)
        .mark_bar(tooltip=True)
        .encode(
            x="Total_Duration:Q",
            y=alt.Y("Error_Code:N", sort="-x"),
            color=alt.Color(value=COLOR_BLUE),
        ),
        use_container_width=True,
    )
        
    elif "Station Number" in df.columns and "Frequency" in df.columns and "Line" in df.columns:
        error_codes = df["Error_Code"].to_list()

        colors = ["#aa423a","#f6b404", "#327a88","#303e55","#c7ab84","#b1dbaa",
    "#feeea5","#3e9a14","#6e4e92","#c98149", "#d1b844","#8db6d8"]
        
        error_code_select = alt.selection_point(fields=["Error_Code"])

        error_code_pie = (alt.Chart(df).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(
                "Frequency",
                type="quantitative",
                aggregate="sum",
                title="Frequency",
            ),
            color=alt.Color(
                field="Error_Code",
                type="nominal",
                scale=alt.Scale(domain=error_codes, range=colors),
                title="Error Codes",
            ),
            opacity=alt.condition(error_code_select, alt.value(1), alt.value(0.25)),
        ).add_params(error_code_select).properties(title="Error Codes and Frequency"))

        station_number_bar = (
            alt.Chart(df)
            .mark_bar(tooltip=True)
            .encode(
               x=alt.X("Frequency", type="quantitative",
                aggregate="sum",
                title="Frequency"),
               y=alt.Y("Station Number", type="nominal"),
                color=alt.Color(field="Error_Code",
                type="nominal")
            ).transform_filter(error_code_select).properties(width=600, title="Station Number and Frequency")
      )
        
        line_bar = (
            alt.Chart(df)
            .mark_bar(tooltip=True)
            .encode(
               x=alt.X("Frequency", type="quantitative",
                aggregate="sum",
                title="Frequency"),
               y=alt.Y("Line", type="nominal"),
                color=alt.Color(field="Error_Code",
                type="nominal")
            ).transform_filter(error_code_select).properties(width=600, title="Linewise Frequency")
      )
        
        full_chart = error_code_pie & station_number_bar & line_bar

        st.altair_chart(full_chart)
    
    elif "Station Number" in df.columns and "Frequency" in df.columns:
        error_codes = df["Error_Code"].to_list()

        colors = ["#aa423a","#f6b404", "#327a88","#303e55","#c7ab84","#b1dbaa",
    "#feeea5","#3e9a14","#6e4e92","#c98149", "#d1b844","#8db6d8"]
        
        error_code_select = alt.selection_point(fields=["Error_Code"])
        error_code_pie = (alt.Chart(df).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(
                "Frequency",
                type="quantitative",
                aggregate="sum",
                title="Frequency",
            ),
            color=alt.Color(
                field="Error_Code",
                type="nominal",
                scale=alt.Scale(domain=error_codes, range=colors),
                title="Error Codes",
            ),
            opacity=alt.condition(error_code_select, alt.value(1), alt.value(0.25)),
        ).add_params(error_code_select).properties(title="Error Codes and Frequency"))

        station_number_bar = (
            alt.Chart(df)
            .mark_bar(tooltip=True)
            .encode(
               x=alt.X("Frequency", type="quantitative",
                aggregate="sum",
                title="Frequency"),
               y=alt.Y("Station Number", type="nominal"),
                color=alt.Color(field="Error_Code",
                type="nominal")
            ).transform_filter(error_code_select).properties(width=600, title="Station Number and Frequency")
      )
        
        full_chart = error_code_pie & station_number_bar

        st.altair_chart(full_chart)

    elif "Line" in df.columns and "Frequency" in df.columns:
        error_codes = df["Error_Code"].to_list()

        colors = ["#aa423a","#f6b404", "#327a88","#303e55","#c7ab84","#b1dbaa",
    "#feeea5","#3e9a14","#6e4e92","#c98149", "#d1b844","#8db6d8"]
        
        error_code_select = alt.selection_point(fields=["Error_Code"])
        error_code_pie = (alt.Chart(df).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(
                "Frequency",
                type="quantitative",
                aggregate="sum",
                title="Frequency",
            ),
            color=alt.Color(
                field="Error_Code",
                type="nominal",
                scale=alt.Scale(domain=error_codes, range=colors),
                title="Error Codes",
            ),
            opacity=alt.condition(error_code_select, alt.value(1), alt.value(0.25)),
        ).add_params(error_code_select).properties(title="Error Codes and Frequency"))

        station_number_bar = (
            alt.Chart(df)
            .mark_bar(tooltip=True)
            .encode(
               x=alt.X("Frequency", type="quantitative",
                aggregate="sum",
                title="Frequency"),
               y=alt.Y("Line", type="nominal"),
                color=alt.Color(field="Error_Code",
                type="nominal")
            ).transform_filter(error_code_select).properties(width=600, title="Station Number and Frequency")
      )
        
        full_chart = error_code_pie & station_number_bar

        st.altair_chart(full_chart)

    elif "Frequency" in df.columns:

        st.altair_chart(
        alt.Chart(df)
        .mark_bar(tooltip=True)
        .encode(
            x="Frequency:Q",
            y=alt.Y("Error_Code:N", sort="-x"),
            color=alt.Color(value=COLOR_BLUE),
        ),
        use_container_width=True,
    )

    else:
        st.write("None of the columns available")