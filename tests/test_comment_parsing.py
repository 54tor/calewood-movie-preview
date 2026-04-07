from calewood_movie_preview.utils import find_imgbb_links


def test_find_imgbb_links_counts_multiple_domains() -> None:
    comment = "https://imgbb.com/a https://i.ibb.co/foo/bar.jpg"
    assert len(find_imgbb_links(comment)) == 2
