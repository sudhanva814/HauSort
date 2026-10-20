# Housing Ad Scraper Integration --- Implementation Plan

**Project:** Open-source German housing comparison app\
**Backend:** FastAPI + Docker\
**Database:** PostgreSQL\
**Goal:** Accept user-submitted housing-ad URLs, retrieve permitted page
content, extract useful listing text and metadata, and pass a normalized
payload to the housing-ad parser.

------------------------------------------------------------------------

## 1. Scope and principles

### MVP goal

A user submits one or more listing URLs. For each URL, the backend:

1.  Validates the URL and confirms the host is allowed.
2.  Fetches ordinary HTML using HTTPX.
3.  Parses structured metadata and useful HTML using BeautifulSoup.
4.  Uses Trafilatura if the page's main text is missing or too noisy.
5.  Optionally retries with Playwright when JavaScript rendering appears
    necessary and automated access is permitted.
6.  Returns a consistent extraction result with source URL, title,
    description, metadata, status, and warnings.
7.  Sends the extracted text to a separate housing-ad
    extraction/normalization service.
8.  Persists the source and normalized ad in PostgreSQL.

### Non-goals for the first iteration

-   Crawling entire websites or searching for new listings.
-   Bypassing login walls, CAPTCHAs, anti-bot systems, or access
    controls.
-   Supporting every housing platform at launch.
-   Automatically contacting landlords.
-   Guaranteeing every extracted field is correct.

### Design principles

-   **Pasted text remains a first-class fallback.** Scraping can fail or
    be disallowed.
-   **Separate fetching from parsing.** Network access and HTML
    interpretation should be independently testable.
-   **Treat extracted data as untrusted.** Validate all output before
    saving it.
-   **Preserve uncertainty.** Missing rent or unclear Anmeldung status
    should be `null`/`unknown`, not guessed.
-   **Respect site terms and access rules.** Review terms, robots
    directives, rate limits, and any applicable restrictions before
    enabling a site adapter.
-   **Use a provider-adapter design.** Common extraction logic is
    shared; site-specific selectors live in separate modules.

------------------------------------------------------------------------

## 2. Proposed pipeline

``` text
POST /api/v1/scrape-jobs
        |
        v
Validate input URL and allowed host
        |
        v
Create source/job record in PostgreSQL
        |
        v
HTTPX fetch with timeout and size limits
        |
        v
Parse HTML: JSON-LD, metadata, title, selectors
        |
        +---- sufficient content? ---- yes ----+
        |                                      |
        no                                     |
        |                                      |
        v                                      |
Trafilatura main-text fallback                 |
        |                                      |
        +---- still insufficient?              |
                    |                          |
                    v                          |
        Playwright fallback if enabled         |
        and permitted for this site            |
                    |                          |
                    +------------+-------------+
                                 |
                                 v
                       Normalize extraction
                                 |
                                 v
                    Validate extracted payload
                                 |
                                 v
              Housing-ad parser / LLM extraction
                                 |
                                 v
                  Save normalized housing ad
                                 |
                                 v
                   Return status and ad result
```

For the first version, the pipeline can run as a normal async FastAPI
request with a strict timeout. If browser rendering or LLM calls make
processing slow, move the work to a background queue in a later phase.

------------------------------------------------------------------------

## 3. Suggested project structure

``` text
app/
├── main.py
├── api/
│   └── routes/
│       └── scrape.py
├── core/
│   ├── config.py
│   └── url_security.py
├── schemas/
│   └── scraping.py
├── services/
│   ├── scraping/
│   │   ├── orchestrator.py
│   │   ├── fetcher.py
│   │   ├── html_parser.py
│   │   ├── text_extractor.py
│   │   ├── browser_fetcher.py
│   │   ├── normalizer.py
│   │   └── site_adapters/
│   │       ├── base.py
│   │       ├── registry.py
│   │       └── example_site.py
│   └── housing_ad_parser.py
├── models/
│   ├── ad_source.py
│   └── housing_ad.py
├── repositories/
│   └── scrape_repository.py
└── tests/
    ├── fixtures/
    ├── test_url_security.py
    ├── test_html_parser.py
    ├── test_text_extractor.py
    ├── test_orchestrator.py
    └── test_scrape_api.py
```

Keep the scraper service independent of FastAPI route handlers. The API
layer should validate requests and call the orchestrator; it should not
contain parsing logic.

------------------------------------------------------------------------

## 4. Dependencies

Start with:

``` bash
pip install httpx beautifulsoup4 lxml trafilatura playwright
playwright install chromium
```

Use your existing SQLAlchemy and Alembic dependencies for persistence.
Pin dependency versions in your project dependency file and lock them
for reproducible builds.

### Docker notes

-   Install Playwright's Chromium browser and its required OS
    dependencies in the image only if browser fallback is enabled.
-   Keep the browser image and installed Playwright version compatible.
-   Run the application as a non-root user where practical.
-   Set CPU, memory, request timeout, and container resource limits.
-   Do not run a browser for every URL by default; start with HTTPX and
    invoke Playwright only when needed.
-   Add a health check for the API and a separate readiness check for
    database connectivity.
-   Ensure the container can resolve DNS normally, but enforce
    destination IP checks in the fetcher.

------------------------------------------------------------------------

## 5. Implementation phases

### Phase 0 --- Choose and document the first supported website

**Tasks**

-   Pick one housing website to support first.
-   Review its terms, robots directives, and permitted access methods.
-   Test a small set of representative public listing pages manually.
-   Identify whether the description is present in initial HTML,
    JSON-LD, metadata, or a page API that the site permits.
-   Document expected fields and known failure cases.
-   Keep unsupported domains rejected or routed to pasted-text input.

**Deliverable:** A short site-support document describing the domain,
allowed access assumptions, fields available, and fallback behavior.

**Acceptance criteria**

-   The project has one clearly documented supported site.
-   The implementation does not attempt to evade access controls.
-   Unsupported domains produce a useful error and suggest pasted text.

### Phase 1 --- Define API schemas

Create Pydantic request and response models.

Example request:

``` json
{
  "urls": [
    "https://example.org/public-listing/123"
  ]
}
```

Suggested request model:

-   `urls`: 1--10 URLs per request for the MVP.
-   Optionally accept a client-generated idempotency key later.
-   Reject malformed URLs and unsupported schemes before starting
    network access.

Suggested response fields:

-   `job_id` or `source_id`
-   `submitted_url`
-   `final_url` after permitted redirects
-   `status`: `succeeded`, `partial`, or `failed`
-   `title`
-   `description`
-   `site_name`
-   `published_at`, if available
-   `extracted_at`
-   `warnings`: list of non-fatal issues
-   `error_code`, if failed
-   `housing_ad_id`, when normalization and persistence succeed

Do not expose raw HTML by default in the public API response.

**Acceptance criteria**

-   Valid input passes schema validation.
-   Invalid schemes, malformed URLs, and oversized batches are rejected.
-   Response status is explicit and stable.

### Phase 2 --- Build secure URL validation

User-controlled URLs create a server-side request forgery (SSRF) risk.
URL validation is a security boundary, not merely input cleanup.

**Requirements**

-   Allow only `http` and `https`; prefer HTTPS.
-   Reject embedded usernames/passwords in URLs.
-   Use a host allowlist for the MVP, ideally exact hostnames rather
    than broad suffix matches.
-   Resolve DNS and reject loopback, private, link-local, multicast,
    reserved, and unspecified IP addresses.
-   Revalidate every redirect destination and resolved address.
-   Limit redirect count.
-   Block cloud metadata destinations and internal service hostnames.
-   Protect against DNS rebinding by ensuring the actual connection
    cannot silently reach a disallowed address; consider a vetted egress
    proxy or transport-level enforcement.
-   Set connection/read/overall timeouts.
-   Limit response bytes and reject unsupported content types.
-   Never pass the submitted URL directly into a shell command.
-   Do not allow users to supply arbitrary browser launch arguments or
    proxy settings.

**Acceptance criteria**

-   Localhost and private-IP targets are rejected.
-   Redirects to private addresses are rejected.
-   Excessive redirects and oversized responses fail safely.
-   Unit tests cover IPv4, IPv6, redirects, DNS failures, and malformed
    URLs.

### Phase 3 --- Implement HTTPX fetching

Create `fetcher.py` with a small, well-defined interface.

Responsibilities:

-   Send a normal browser-like but honest user-agent identifying the
    project and contact/documentation URL.
-   Use a shared `httpx.AsyncClient` with connection pooling and
    explicit timeouts.
-   Follow only a bounded number of redirects, validating every
    destination.
-   Request HTML documents; reject downloads and unexpected MIME types.
-   Stream responses and stop after a configured maximum body size.
-   Record status code, content type, final URL, fetch duration, and
    response size.
-   Handle common outcomes distinctly: timeout, DNS/connect error,
    403/429, 404, 5xx, non-HTML, and empty body.
-   Apply conservative per-domain rate limits and avoid repeated
    immediate retries.

Do not interpret a 403 or CAPTCHA page as a valid listing. Return a
structured failure and offer pasted-text input.

**Acceptance criteria**

-   A static HTML fixture fetches successfully.
-   Timeouts, non-HTML responses, and HTTP errors return typed results.
-   A request cannot consume unbounded time or memory.

### Phase 4 --- Parse HTML and metadata

Implement `html_parser.py` using BeautifulSoup and `lxml`.

Try extraction strategies in this order:

1.  JSON-LD structured data, if present and relevant.
2.  Open Graph and standard metadata (`og:title`, description, canonical
    URL).
3.  Document title and relevant semantic elements.
4.  Site-specific selectors from the relevant adapter.
5.  Main text fallback using Trafilatura.

Normalize whitespace and HTML entities. Keep the title, description, and
general page text separate.

Do not assume every page uses the same schema. JSON-LD may describe a
website, breadcrumb, or organization rather than the actual listing;
validate types and relevance.

**Acceptance criteria**

-   Parser tests use saved HTML fixtures rather than live network calls.
-   Empty titles and missing descriptions are handled.
-   Duplicate text and navigation noise are reduced.
-   Parser returns a normalized result even if some fields are missing.

### Phase 5 --- Add Trafilatura fallback

Implement `text_extractor.py`.

Use Trafilatura when the HTML parser cannot find enough meaningful
listing text. Extract the main content and useful metadata, then
normalize whitespace.

Track extraction provenance, for example:

-   `json_ld`
-   `meta_description`
-   `site_adapter`
-   `trafilatura`
-   `playwright`

This makes debugging and quality measurement easier.

**Acceptance criteria**

-   Text extraction works on representative saved HTML fixtures.
-   Navigation and footer noise are reduced.
-   The result records which extraction strategy supplied the text.

### Phase 6 --- Add Playwright selectively

Do not start every scrape in a browser. Browser rendering is slower,
more resource-intensive, and creates a larger security surface.

Invoke Playwright only when:

-   The initial HTML is valid but has too little listing content.
-   The supported site is known to render the relevant fields with
    JavaScript.
-   Automated browser access is permitted.

Implementation notes:

-   Use a separate browser-fetching module.
-   Run Chromium in a restricted container or worker.
-   Disable downloads and unnecessary resource types.
-   Apply navigation and total execution timeouts.
-   Limit page size, concurrency, memory, and browser lifetime.
-   Intercept and reject requests to localhost, private networks, and
    metadata endpoints, including subresources and redirects.
-   Reapply URL and destination validation to browser navigation and
    subresource requests.
-   Do not bypass CAPTCHAs, logins, or access restrictions.

**Acceptance criteria**

-   A saved or controlled JavaScript-rendered test page is extracted
    successfully.
-   Browser failures return a structured failure instead of hanging the
    API.
-   The normal static-HTML path does not launch a browser.

### Phase 7 --- Create site adapters

Create a small adapter interface, such as:

-   `supports(url) -> bool`
-   `extract(html, url) -> ExtractedPage`
-   Optional site-specific field mappings and extraction diagnostics.

Keep adapters deterministic and narrow. They should parse page content,
not make network requests independently unless the adapter explicitly
uses the shared secure fetcher.

For each supported site, document:

-   Accepted hostnames.
-   Permitted fetch method.
-   Listing selectors or structured data sources.
-   Known fields.
-   Failure behavior.
-   Fixture pages and tests.

Do not treat a website as supported merely because its homepage can be
fetched. Support should mean that representative listing pages can be
parsed reliably.

### Phase 8 --- Normalize and validate extraction

Create a single internal schema, for example `ExtractedPage`:

``` python
class ExtractedPage:
    submitted_url: str
    final_url: str | None
    site_name: str | None
    title: str | None
    description: str | None
    main_text: str | None
    metadata: dict
    extraction_method: str
    warnings: list[str]
```

Use Pydantic for the actual project schema. Validate URLs, text lengths,
field types, and allowed enum values.

Then pass `main_text`, title, metadata, and source URL to the separate
housing-ad parser. That parser should extract fields such as warm rent,
deposit, room size, city, available date, furnishing, contract length,
and Anmeldung status.

Important data rules:

-   Unknown values stay unknown.
-   Store currency and units consistently.
-   Preserve the original source text when retention is appropriate.
-   Distinguish observed values from inferred values.
-   Keep evidence and confidence/provenance for extracted housing fields
    where practical.
-   Validate LLM output against a strict schema before persistence.

### Phase 9 --- Persist sources and results

Use your existing PostgreSQL models and Alembic migrations.

Recommended flow:

1.  Create an `ad_sources` record with submitted URL and `pending`
    status.
2.  Update the source with fetch and extraction status.
3.  Store extraction diagnostics and a content hash where appropriate.
4.  Create or update the normalized `housing_ads` record only after
    validation.
5.  Link the source to the housing ad.
6.  Commit status changes and results transactionally where possible.

Do not store every full HTML response forever. Define a retention policy
for raw text and diagnostics, and avoid retaining personal contact
details unless the application genuinely needs them.

### Phase 10 --- Add API endpoint and error handling

Suggested endpoints:

-   `POST /api/v1/scrape-jobs` --- submit one or more URLs.
-   `GET /api/v1/scrape-jobs/{job_id}` --- retrieve job status and
    results.
-   `POST /api/v1/housing-ads/from-text` --- submit pasted ad text.
-   `GET /api/v1/housing-ads/{ad_id}` --- retrieve normalized ad data.

For a simple MVP, `POST /scrape-jobs` may process synchronously and
return results. If processing can exceed normal request timeouts, return
`202 Accepted` with a job ID and use a background worker/queue.

Use consistent error codes such as:

-   `unsupported_domain`
-   `invalid_url`
-   `blocked_destination`
-   `fetch_timeout`
-   `http_error`
-   `access_restricted`
-   `non_html_response`
-   `insufficient_content`
-   `parse_failed`
-   `normalization_failed`

Avoid returning internal IP addresses, stack traces, or sensitive server
details to clients.

------------------------------------------------------------------------

## 6. Testing plan

### Unit tests

-   URL validation and SSRF protections.
-   HTML metadata and JSON-LD extraction.
-   Trafilatura fallback.
-   Site adapter selectors.
-   Normalization and field validation.
-   Error mapping and status transitions.

### Integration tests

-   FastAPI endpoint with a mocked HTTPX transport.
-   PostgreSQL persistence and rollback behavior.
-   Full pipeline from URL input to normalized housing ad, using local
    fixtures.
-   Playwright rendering against a controlled local test page only in a
    suitably isolated test environment.

### Test fixtures

Store representative HTML files in `tests/fixtures/`. Include:

-   Complete listing.
-   Missing rent.
-   Missing description.
-   Structured data with irrelevant JSON-LD.
-   JavaScript shell with little initial content.
-   Access-denied page.
-   Expired/deleted listing.
-   Malformed HTML.
-   Non-listing page.

Do not make the normal test suite depend on live third-party sites. Live
smoke tests should be opt-in, rate-limited, and run only where access is
permitted.

### Quality metrics

Track:

-   Fetch success rate by supported domain.
-   Percentage of pages with a non-empty title and description.
-   Percentage of normalized ads with warm rent and city.
-   Partial extraction rate.
-   Median and p95 processing time.
-   Failure categories by site.
-   Field-level extraction accuracy on a manually labeled test set.

------------------------------------------------------------------------

## 7. Observability and operations

Log structured events with a correlation/job ID. Useful fields include:

-   Source ID and supported domain.
-   Fetch status and duration.
-   HTTP status code.
-   Response size.
-   Extraction method.
-   Parser warnings.
-   Overall pipeline duration.
-   Error category.

Avoid logging full descriptions, phone numbers, email addresses, or raw
HTML by default.

Set conservative limits for:

-   URLs per request.
-   Concurrent fetches per host.
-   Global scraping concurrency.
-   Response size.
-   Redirects.
-   HTTP and browser timeouts.
-   Retries.
-   Browser memory and lifetime.

Use bounded retries only for transient failures such as selected 5xx
responses. Do not repeatedly retry 403, 404, CAPTCHA, or rate-limit
responses.

------------------------------------------------------------------------

## 8. Suggested environment configuration

Example configuration names (set actual values based on deployment
needs):

``` env
SCRAPER_ENABLED=true
SCRAPER_ALLOWED_HOSTS=example.org
SCRAPER_REQUEST_TIMEOUT_SECONDS=15
SCRAPER_MAX_RESPONSE_BYTES=5000000
SCRAPER_MAX_REDIRECTS=5
SCRAPER_MAX_URLS_PER_BATCH=10
SCRAPER_MAX_CONCURRENT_FETCHES=5
SCRAPER_BROWSER_FALLBACK_ENABLED=false
SCRAPER_BROWSER_TIMEOUT_SECONDS=20
SCRAPER_USER_AGENT=WohnMatchBot/0.1 (+https://your-project-docs.example)
```

These are configuration examples, not recommended production values for
every website. Tune them based on the supported sites, testing, and
deployment constraints. Use your actual project contact/documentation
URL for the user-agent.

The allowed-host setting should be enforced by code, not treated as a
documentation-only setting.

------------------------------------------------------------------------

## 9. Definition of done for the first MVP

The integration is ready when:

-   [ ] One supported listing domain is documented and tested.
-   [ ] URLs are validated against an explicit allowlist.
-   [ ] Redirects and DNS resolution cannot reach private/internal
    destinations.
-   [ ] HTTPX fetches static HTML with bounded time and memory.
-   [ ] BeautifulSoup extracts metadata and page structure.
-   [ ] Trafilatura provides a main-text fallback.
-   [ ] Playwright is optional and only used for supported cases.
-   [ ] Extracted output follows one Pydantic schema.
-   [ ] Housing-ad parsing is separate from page fetching.
-   [ ] PostgreSQL records source status and normalized ad data.
-   [ ] Failures return useful typed errors and preserve pasted-text
    fallback.
-   [ ] Unit and integration tests pass without depending on live
    websites.
-   [ ] Logs and retention settings avoid unnecessary personal data.
-   [ ] Docker can build and run the API with the configured
    dependencies.

------------------------------------------------------------------------

## 10. Recommended order of work

Build in this order to avoid spending too much time on browser
automation before the basic pipeline is reliable:

1.  Pydantic request/response schemas.
2.  Secure URL validation and explicit domain allowlist.
3.  HTTPX fetcher.
4.  BeautifulSoup metadata/HTML parser.
5.  Trafilatura fallback.
6.  Fixture-based tests.
7.  Connect the housing-ad normalization service.
8.  Persist sources and normalized ads in PostgreSQL.
9.  Add the FastAPI endpoint.
10. Add one site adapter.
11. Add Playwright only if tests demonstrate that the site needs it and
    access is permitted.
12. Add job queueing and operational metrics if processing becomes slow.

**Final recommendation:** make the scraper a replaceable ingestion
service, not the core of the entire product. The core product is the
normalized housing-ad schema and transparent comparison engine. Scraping
is one way to populate that schema; pasted text and manual entry must
continue to work even when a site changes its markup or blocks automated
fetching.
