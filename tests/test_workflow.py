from calewood_movie_preview.calewood_api import CalewoodApiClient


def test_to_model_missing_required_fields_returns_none() -> None:
    assert CalewoodApiClient.to_model({}, "info_hash") is None
