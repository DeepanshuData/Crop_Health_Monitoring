"""Reusable chart components."""

import matplotlib.pyplot as plt
import streamlit as st


def line_chart(frame, x_column, y_column, title):
    fig, axis = plt.subplots(figsize=(9, 4))
    axis.plot(frame[x_column], frame[y_column], marker="o", linewidth=1.5)
    axis.set_title(title)
    axis.set_xlabel("Acquisition date")
    axis.set_ylabel(y_column.replace("_", " ").upper())
    axis.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
