from app.services.scraping.html_parser import HTMLParser


def test_html_parser_json_ld():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Old Title</title>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Apartment",
            "name": "Schönes WG-Zimmer in Trier",
            "description": "Helles Zimmer mit Balkon nahe Universität Trier.",
            "publisher": {
                "@type": "Organization",
                "name": "WohnungPortal"
            }
        }
        </script>
    </head>
    <body>
        <h1>Headline</h1>
        <p>Body text</p>
    </body>
    </html>
    """
    parser = HTMLParser()
    page = parser.parse(sample_html, "https://example.com/ad/1")

    assert page.title == "Schönes WG-Zimmer in Trier"
    assert "Helles Zimmer mit Balkon" in (page.description or "")
    assert page.extraction_method == "json_ld"
    assert page.site_name == "WohnungPortal"


def test_html_parser_open_graph_fallback():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="Modern WG Room in Berlin" />
        <meta property="og:description" content="Warmmiete: 450 Euro. Anmeldung möglich. Voll möbliert." />
        <meta property="og:site_name" content="BerlinHousing" />
    </head>
    <body>
        <nav>Navigation links here</nav>
        <p>Main content paragraph.</p>
        <footer>Footer copyright</footer>
    </body>
    </html>
    """
    parser = HTMLParser()
    page = parser.parse(sample_html, "https://example.com/ad/2")

    assert page.title == "Modern WG Room in Berlin"
    assert "Warmmiete: 450 Euro" in (page.description or "")
    assert page.site_name == "BerlinHousing"
    assert page.extraction_method == "og_description"
    # Ensure nav and footer were stripped
    assert "Navigation links here" not in (page.main_text or "")
    assert "Footer copyright" not in (page.main_text or "")
