I'd implement the seven core tables below. The diagram also shows two concepts that can remain columns or JSON fields initially, so you don't have to create nine tables immediately.
2. The seven tables I'd create
Table 1 — users
Stores application users. You can defer authentication, but having a user entity ready makes ownership and saved comparisons straightforward.
Column	Type	Purpose
id	UUID, PK	Unique user ID
email	VARCHAR(255), nullable, unique	Login identity
display_name	VARCHAR(100), nullable	Display name
created_at	TIMESTAMPTZ	Account creation
updated_at	TIMESTAMPTZ	Last update
If the first version is entirely anonymous, you can skip this table and authentication until later.
Table 2 — user_preferences
Stores reusable housing-search criteria. A user can update their preferences without modifying previously completed comparisons.
Column	Type	Purpose
id	UUID, PK	Preference profile ID
user_id	UUID, FK	Owner
name	VARCHAR(100)	E.g. “Trier student housing”
max_warm_rent	NUMERIC(10,2), nullable	Maximum monthly warm rent
max_cold_rent	NUMERIC(10,2), nullable	Optional cold-rent ceiling
max_deposit	NUMERIC(10,2), nullable	Maximum deposit
preferred_city	VARCHAR(100)	E.g. Trier
target_location	JSONB, nullable	University or other destination
max_commute_minutes	SMALLINT, nullable	Travel-time ceiling
require_anmeldung	BOOLEAN	Whether registration is mandatory
require_furnished	BOOLEAN, nullable	true = mandatory, false = not required, NULL = no preference
min_contract_months	SMALLINT, nullable	Minimum contract duration
max_flatmates	SMALLINT, nullable	Maximum preferred flatmates
weights	JSONB	Relative importance of criteria
created_at	TIMESTAMPTZ	Creation time
updated_at	TIMESTAMPTZ	Last update
Example weights value:
{
  "price": 30,
  "university_commute": 25,
  "supermarket": 15,
  "anmeldung": 15,
  "furnished": 10,
  "contract_length": 5
}


Treat these as relative weights; normalize them to 100 when calculating scores. Hard requirements should be handled separately from weights.
Design tip: Keep weights flexible with JSONB because you will likely introduce new criteria as the project evolves. Store frequently queried numeric values as normal columns.
Table 3 — housing_ads
This is the central table. It stores normalized information extracted from an advertisement, independent of the user comparing it.
Column	Type	Purpose
id	UUID, PK	Ad ID
title	TEXT	Advertisement title
description	TEXT	Cleaned description
property_type	VARCHAR(30)	WG room, apartment, studio, etc.
city	VARCHAR(100)	City
district	VARCHAR(100), nullable	Neighborhood
postal_code	VARCHAR(10), nullable	Postal code
street_address	TEXT, nullable	Address if available
latitude	DOUBLE PRECISION, nullable	Geocoded latitude
longitude	DOUBLE PRECISION, nullable	Geocoded longitude
cold_rent	NUMERIC(10,2), nullable	Monthly Kaltmiete
additional_costs	NUMERIC(10,2), nullable	Nebenkosten
heating_costs	NUMERIC(10,2), nullable	Heating if separately stated
warm_rent	NUMERIC(10,2), nullable	Monthly Warmmiete
deposit	NUMERIC(10,2), nullable	Kaution
room_size_sqm	NUMERIC(8,2), nullable	Room or property size
furnished	BOOLEAN, nullable	Furnishing status
available_from	DATE, nullable	Availability date
minimum_contract_months	SMALLINT, nullable	Minimum rental duration
registration_status	VARCHAR(20)	Yes, no, likely, unknown
flatmates_count	SMALLINT, nullable	Other residents
amenities	JSONB	Balcony, washing machine, etc.
extraction_status	VARCHAR(20)	Pending, succeeded, failed, partial
created_at	TIMESTAMPTZ	Record creation
updated_at	TIMESTAMPTZ	Last update
A critical decision: unknown must not equal false or zero. For example, if an ad doesn't mention whether Anmeldung is possible, use unknown. If the rent is missing, store NULL, not 0.
Also, distinguish flatmates_count from total occupants, and distinguish the advertised rent from any calculated rent estimate.
Table 4 — ad_sources
Separates where the advertisement came from from the advertisement's structured data.
Column	Type	Purpose
id	UUID, PK	Source ID
housing_ad_id	UUID, FK	Associated ad
source_type	VARCHAR(20)	url, pasted_text, manual
source_url	TEXT, nullable	Original listing URL
source_domain	VARCHAR(255), nullable	Listing website
raw_text	TEXT, nullable	Original pasted/extracted text
raw_content_hash	VARCHAR(64), nullable	Detect duplicate input
scraped_at	TIMESTAMPTZ, nullable	Last successful fetch
last_attempt_at	TIMESTAMPTZ, nullable	Last extraction attempt
status	VARCHAR(20)	Pending, processing, succeeded, failed
error_message	TEXT, nullable	Failure reason
created_at	TIMESTAMPTZ	Record creation
Why separate this from housing_ads? One ad might be submitted through a URL first and later pasted manually. It also lets you retry extraction without losing the original input.
For an open-source project, avoid storing more personal contact information than you need, and make raw-content retention configurable.
Table 5 — comparisons
Represents one comparison session: the user submits several ads, chooses criteria, and receives a ranked result.
Column	Type	Purpose
id	UUID, PK	Comparison ID
user_id	UUID, FK, nullable	Owner, if accounts exist
preference_id	UUID, FK, nullable	Reusable preference profile
name	VARCHAR(150), nullable	E.g. “Trier WG shortlist”
status	VARCHAR(20)	Draft, processing, completed, failed
criteria_snapshot	JSONB	Exact criteria used for this run
scoring_version	VARCHAR(30)	Version of the scoring algorithm
created_at	TIMESTAMPTZ	Start time
completed_at	TIMESTAMPTZ, nullable	Completion time
The criteria_snapshot is important. If the user changes their budget tomorrow, you shouldn't silently change the explanation or score of yesterday's comparison.
Example snapshot:
{
  "max_warm_rent": 650,
  "require_anmeldung": true,
  "max_commute_minutes": 30,
  "weights": {
    "price": 30,
    "university_commute": 25,
    "supermarket": 15,
    "anmeldung": 15,
    "furnished": 10,
    "contract_length": 5
  }
}


Table 6 — comparison_ads
This is the many-to-many join table connecting comparisons to ads. It stores the outcome of evaluating each ad against one particular set of criteria.
Column	Type	Purpose
id	UUID, PK	Result ID
comparison_id	UUID, FK	Comparison session
housing_ad_id	UUID, FK	Evaluated ad
overall_score	NUMERIC(5,2), nullable	Overall match percentage
rank	INTEGER, nullable	Position in this comparison
eligible	BOOLEAN	Whether hard constraints pass
exclusion_reasons	JSONB	Reasons for failing hard constraints
summary	TEXT, nullable	AI-generated explanation
pros	JSONB	Positive factors
cons	JSONB	Drawbacks
created_at	TIMESTAMPTZ	Result creation
Add a unique constraint on (comparison_id, housing_ad_id) to prevent the same ad appearing twice in one comparison.
Important: An ad scoring 92% should not automatically rank above an ad that satisfies all mandatory criteria if the first one fails a hard requirement. Keep eligibility and preference scoring distinct.
Table 7 — comparison_score_details
Stores the individual criterion scores so that the UI can explain exactly how the final percentage was calculated.
Column	Type	Purpose
id	UUID, PK	Score detail ID
comparison_ad_id	UUID, FK	Evaluated result
criterion_key	VARCHAR(50)	price, university_commute, etc.
criterion_score	NUMERIC(5,2), nullable	Score from 0 to 100
weight	NUMERIC(5,2)	Weight used for this criterion
weighted_contribution	NUMERIC(7,3), nullable	Contribution to final score
status	VARCHAR(20)	Pass, fail, unknown, not_applicable
explanation	TEXT, nullable	Human-readable reason
evidence	JSONB, nullable	Extracted value and supporting evidence
Add a unique constraint on (comparison_ad_id, criterion_key).
For example:
Criterion	Score	Weight	Contribution
Price	100	30	30
University commute	80	25	20
Supermarket	90	15	13.5
Anmeldung	100	15	15
Furnished	100	10	10
Contract length	60	5	3
Total		100	91.5%
This makes the ranking explainable and lets you change the scoring algorithm later without losing the ability to inspect past results.
3. Relationships and constraints
Here are the key relationships to implement using foreign keys.
Relationship	Cardinality
User → Preferences	One-to-many
User → Comparisons	One-to-many
Preference → Comparisons	One-to-many
Housing ad → Sources	One-to-many
Comparison → Comparison ads	One-to-many
Housing ad → Comparison ads	One-to-many
Comparison ad → Score details	One-to-many
I'd add these database constraints and indexes from the beginning:
- Primary keys: UUIDs, generated by the application or PostgreSQL.
- Foreign keys: enforce referential integrity.
- Unique: (comparison_id, housing_ad_id) and (comparison_ad_id, criterion_key).
- Indexes: housing_ads.city, housing_ads.warm_rent, housing_ads.available_from, comparisons.user_id, and all foreign keys used in joins.
- Checks: rents and deposits cannot be negative; scores must be between 0 and 100; weights cannot be negative.
- Timestamps: use TIMESTAMPTZ and UTC for stored timestamps.
For fields like registration_status, extraction_status, and property_type, use Python enums or validated string values initially. You don't need a separate lookup table for every category.
4. What about nearby supermarkets, pharmacies and the university?
I'd leave these out of the initial seven tables. You can extend the schema when you implement geospatial features.
Eventually, a separate ad_locations or nearby_places table could store:
- id
- housing_ad_id
- place_type — supermarket, pharmacy, university, bus stop
- name
- latitude
- longitude
- walking_minutes
- cycling_minutes
- transit_minutes
- provider
- fetched_at
This avoids repeatedly geocoding the same advertisement for every comparison. You could also use PostGIS later for spatial queries.
One important detail: distinguish straight-line distance from actual travel time. For a housing recommendation, a 2 km walking route or a 20-minute bus journey is more useful than simply knowing that a destination is 2 km away.
5. The scoring logic I'd implement
Keep this logic in Python, not inside the database.

Step 1: Hard constraints
Check mandatory budget, registration, move-in date and other non-negotiables. Record every failure.




Step 2: Soft preference scoring
Calculate individual 0–100 scores for price, commute, amenities and other preferences.




Step 3: Rank and explain
Persist the overall score, criterion breakdown, eligibility and explanations against the comparison.