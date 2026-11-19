"""Reusable Streamlit metric presentation."""

import streamlit as st


def metric_row(cards):
    for index in range(0, len(cards), 4):
        columns = st.columns(4)
        for column, card in zip(columns, cards[index:index + 4]):
            column.metric(card["label"], card["value"], card.get("delta"))
