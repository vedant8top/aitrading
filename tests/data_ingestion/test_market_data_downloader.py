import pandas as pd
import pytest

from src.data_ingestion.market_data_downloader import MarketDataDownloader, EmptyDatasetError

def test_clean_data_initially_empty():
    """Test that an initially empty DataFrame raises EmptyDatasetError."""
    # Create an empty DataFrame with the required columns
    df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    with pytest.raises(EmptyDatasetError, match="No valid rows remain after data cleaning"):
        MarketDataDownloader._clean_data(df)

def test_clean_data_empty_after_cleaning():
    """Test that a DataFrame containing only NaNs in required columns raises EmptyDatasetError."""
    # Create a DataFrame with rows, but all required values are NaN
    dates = pd.date_range("2024-01-01", periods=3)
    df = pd.DataFrame(index=dates, columns=["Open", "High", "Low", "Close", "Volume"])
    # Leave all rows as NaN

    with pytest.raises(EmptyDatasetError, match="No valid rows remain after data cleaning"):
        MarketDataDownloader._clean_data(df)
