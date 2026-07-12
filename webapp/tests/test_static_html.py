from app.scraping.static_html import extract_page_urls


def test_extracts_ordered_urls_from_astro_island_props():
    page_html = (
        '<astro-island props="{&quot;pages&quot;:[1,['
        '[0,{&quot;url&quot;:[0,&quot;https://cdn.example.com/a/1.webp?v=1&quot;]}],'
        '[0,{&quot;url&quot;:[0,&quot;https://cdn.example.com/a/2.webp?v=1&quot;]}]'
        ']]}"></astro-island>'
    )
    assert extract_page_urls(page_html) == [
        "https://cdn.example.com/a/1.webp?v=1",
        "https://cdn.example.com/a/2.webp?v=1",
    ]


def test_returns_empty_list_when_no_embedded_pages_json():
    assert extract_page_urls("<html><body>no reader data here</body></html>") == []
