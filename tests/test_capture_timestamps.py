from calewood_movie_preview.media import capture_positions, evenly_spaced_positions


def test_capture_positions_are_nine_tenths() -> None:
    assert capture_positions() == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def test_evenly_spaced_positions_for_six_frames() -> None:
    assert evenly_spaced_positions(6) == [1 / 7, 2 / 7, 3 / 7, 4 / 7, 5 / 7, 6 / 7]
