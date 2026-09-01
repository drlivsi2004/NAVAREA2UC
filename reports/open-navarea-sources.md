# Open NAVAREA Source Reconnaissance

Checked on 2026-08-28. This is a source-discovery report for the future
online platform, not a statement that any web page replaces the official
SafetyNET, SafetyCast, NAVTEX, or other approved broadcast channels.

## Official global directory

The International Hydrographic Organization maintains the authoritative
discovery page for the 21 operational NAVAREAs:

- https://iho.int/navigation-warnings-on-the-web

The IHO page links each NAVAREA to its coordinator and explicitly warns that
not all coordinators publish warnings on the web. It also states that web
availability does not relieve vessels from receiving navigational warnings
through approved broadcast systems.

The IHO directory is therefore a coordinator registry and discovery source,
not the single data feed for the product.

## Source matrix

| NAVAREA | Coordinator | Public source | Initial assessment |
|---|---|---|---|
| I | United Kingdom | [UKHO Radio Navigation Warnings](https://msi.admiralty.co.uk/RadioNavigationalWarnings) | Public HTML table with current NAVAREA I warnings and detail text. Good first HTML adapter candidate. |
| II | France | [PING warnings and notices](https://portail.ping-info-nautique.fr/avurnav-notice) | Public page explicitly covering NAVAREA II. Data rendering and stable retrieval format still need investigation. |
| III | Spain | [IHM NAVAREA III](https://armada.defensa.gob.es/ihm/Aplicaciones/Navareas/Index_Navareas_xml_eng.htm) | Public in-force list with warning details; the official URL identifies an XML-oriented page. Strong candidate, but the actual detail endpoint/schema must be captured. |
| IV | USA | [NGA Maritime Safety Information](https://msi.nga.mil/NavWarnings) and [NGA public API](https://msi.nga.mil/api/swagger-ui.html) | Strongest source. Public HTML/XML/CSV search plus public API endpoints for current warnings, in-force numbers, and NAVAREA values. |
| V | Brazil | [CHM NAVAREA V](https://www.marinha.mil.br/chm/dados-do-segnav-avradio-script/navarea-v) | Official public page found. The older IHO-linked page returned 404, so current page and format require adapter validation. |
| VI | Argentina | [Radioavisos Náuticos](https://www.hidro.gov.ar/nautica/RadioavisosNauticos.asp?op=8) | Public page with in-force NAVAREA VI messages and a visible update date. Good HTML/text adapter candidate. |
| VII | South Africa | [SANHO](http://www.sanho.co.za/) | Official coordinator site identified by IHO; direct warning data endpoint was not verified during this pass. |
| VIII | India | [NHO NAVAREA warnings](https://hydrobharat.gov.in/navigational-warnings/) | Official public NAVAREA VIII page. It appears to use a dynamic or very small rendered page, so download/API behavior still needs capture. |
| IX | Pakistan | [Pakistan Navy](https://www.paknavy.gov.pk/) | Official coordinator site identified by IHO; no direct public warning endpoint was verified. |
| X | Australia | [AMSA Maritime Safety Information](https://www.amsa.gov.au/safety-navigation/navigation-systems/maritime-safety-information) | Public MSI page and database search. It explicitly covers NAVAREA X current warnings. Good candidate, with query/form behavior to document. |
| XI | Japan | [JHOD Navigational Warnings](https://www1.kaiho.mlit.go.jp/TUHO/keiho/navarea11_en.html) | Public official navigational-warning page linked from JHOD. Format and current-message endpoint need capture. |
| XII | USA | [NGA Maritime Safety Information](https://msi.nga.mil/NavWarnings) and [NGA public API](https://msi.nga.mil/api/swagger-ui.html) | Same strong public API and HTML/XML/CSV source as NAVAREA IV. |
| XIII | Russian Federation | [Russian hydrographic notices](https://structure.mil.ru/structure/forces/hydrographic/info/notices.htm) | Official directory target identified, but the page was not retrievable in this pass. Do not treat as an available automated source yet. |
| XIV | New Zealand | [IHO-listed Maritime NZ link](https://services.maritimenz.govt.nz/navigational-warnings/) | The IHO-listed URL returned 404. Current official endpoint must be resolved before integration. |
| XV | Chile | [IHO-listed SHOA link](http://www.shoa.mil.cl/php/radioavisos.php?idioma=es) | IHO-listed HTTP URL was not retrievable in this pass. Current official endpoint must be resolved. |
| XVI | Peru | [DHN Peru](https://www.dhn.mil.pe/) | Official site is publicly reachable; a direct NAVAREA XVI warning endpoint was not verified. |
| XVII | Canada | [Canadian Coast Guard NAVAREA page](https://www.ccg-gcc.gc.ca/mcts-sctm/navwarn-avnav-ca-eng.html) and [public NAVWARN service](https://nis.ccg-gcc.gc.ca/public/rest/menu/en/topics) | Strong candidate. Public service exposes search for NAVAREAs, including an `onlyInForce=true` view, and public subscription/search paths. |
| XVIII | Canada | [Canadian Coast Guard NAVAREA page](https://www.ccg-gcc.gc.ca/mcts-sctm/navwarn-avnav-ca-eng.html) and [public NAVWARN service](https://nis.ccg-gcc.gc.ca/public/rest/menu/en/topics) | Same public Canadian service as NAVAREA XVII. |
| XIX | Norway | [NAVAREA XIX](http://www.navarea-xix.no/) | Public current-warning table with warning number, date, and full text. Good HTML adapter candidate. |
| XX | Russian Federation | [Russian hydrographic notices](https://structure.mil.ru/structure/forces/hydrographic/info/notices.htm) | Same unresolved official source as NAVAREA XIII. |
| XXI | Russian Federation | [Russian hydrographic notices](https://structure.mil.ru/structure/forces/hydrographic/info/notices.htm) | Same unresolved official source as NAVAREA XIII. |

## Verified machine-oriented candidates

### USA: NGA public API

The public Swagger page documents these relevant endpoints:

- `GET /api/publications/broadcast-warn/current-warnings`
- `GET /api/publications/broadcast-warn/inforce`
- `GET /api/publications/broadcast-warn/navareas`

The current-warnings endpoint was reachable without credentials during this
check and returned structured JSON content. The in-force endpoint should be
used together with issue time and cancellation logic; an endpoint being
reachable is not by itself proof that every returned record is current.

### Canada: public NAVWARN service

The public service exposes:

- `https://nis.ccg-gcc.gc.ca/public/rest/messages/en/search-navareas`
- `https://nis.ccg-gcc.gc.ca/public/rest/messages/en/search-navareas?onlyInForce=true`

The menu page describes active NAVAREAs as remaining in force until cancelled
or transmitted by other means. The exact response shape and stable query
contract still need to be captured before implementation.

## Secondary aggregation option

[SeaLagom API documentation](https://www.sealagom.com/api/docs) advertises
live routes for all 21 NAVAREAs and JSON responses. It requires an API token;
anonymous requests are not the same as an open unauthenticated feed. It may be
useful as a comparison or temporary coverage source, but it is not a
replacement for coordinator sources and must not become the sole authority for
freshness or validity.

## Recommended first online source wave

Start with sources that are both official and reachable:

1. USA: NAVAREA IV and XII through the NGA public API.
2. Canada: NAVAREA XVII and XVIII through the public NAVWARN service.
3. UK: NAVAREA I through the public UKHO HTML page.
4. Spain: NAVAREA III through the public IHM page.
5. Argentina: NAVAREA VI through the public in-force page.
6. Australia: NAVAREA X through the public AMSA MSI search.
7. Norway: NAVAREA XIX through the public warning table.
8. France, India, Brazil, and Japan after their rendered data/detail formats
   are captured and regression-tested.

The remaining coordinator links should be resolved in a dedicated source
onboarding pass rather than silently substituted with a third-party mirror.

## Adapter requirements

Every online source adapter must record:

- coordinator and source URL;
- retrieval time;
- source response or snapshot checksum;
- source-provided issue and validity/cancellation information;
- parser/profile version;
- source availability and freshness status;
- raw message text before normalization;
- diagnostics when the source is stale, partial, unavailable, or changed.

The site must show freshness and source status to the user. A cached response
must never be presented as current without an explicit warning.

## Field validation reminder

During the next watch, verify the official NAVAREA message sources actually
used in the vessel's working publications and onboard operational workflow.
This is a separate validation track from the public-web reconnaissance.

Record for each checked region:

- publication or service title and issuing authority;
- edition/revision and publication date;
- whether the message is an original coordinator notice or a reproduced copy;
- source channel used onboard (publication, portal, SafetyNET, SafetyCast,
  NAVTEX, or other approved channel);
- warning number, issue time, validity/cancellation status, and full text;
- whether the same notice is available from the public web source;
- any delay, missing message, formatting difference, or regional coverage gap.

Do not use a vessel working publication as proof that a web endpoint is
official without recording its issuing authority and publication identity.