import streamlit as st
import requests


@st.cache_data(ttl=3600)
def get_exchange_rates(base_currency: str) -> dict:
    """Fetch exchange rates from open.er-api.com. Cached for 1 hour."""
    url = f"https://open.er-api.com/v6/latest/{base_currency}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    return {
        "rates": data.get("rates", {}),
        "time_last_update_utc": data.get("time_last_update_utc", ""),
    }


def convert_amount(amount: float, from_currency: str, to_currency: str, rates: dict) -> float:
    """Convert amount from one currency to another using provided rates (base = to_currency)."""
    if from_currency == to_currency:
        return amount
    rate = rates.get(from_currency)
    if rate is None or rate == 0:
        return amount
    return amount / rate
