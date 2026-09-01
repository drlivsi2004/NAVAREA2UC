# Physical ECDIS Case Register

This register is the source of truth for cases checked on a physical ECDIS.
Screenshots, source messages, generated XML, and code-only regression cases are
kept distinct.

## Review checkpoint — 2026-08-30 (in progress)

The physical-ECDIS review has covered **8 NAVAREA regions** so far:
`NAVAREA I` was reviewed without reported objections and therefore has no
photo; `NAVAREA II`, `III`, `IV`, `V`, `VII`, `VIII`, and `IX` have photo
evidence. This must not be described as eight physically photo-confirmed
regions: physical photo confirmation currently covers seven.

The latest eighteen register cases are `ECDIS-003` through `ECDIS-020`. The review
is **not complete**.

### Current physical-ECDIS testing stage

**Stage: ACTIVE — physical ECDIS verification in progress; release is not
physically closed.**

- Eight NAVAREA regions have been reviewed on the real ECDIS. Seven have
  photographic evidence: `II`, `III`, `IV`, `V`, `VII`, `VIII`, and `IX`.
  `NAVAREA I` was reviewed without a photograph and is not counted as
  photo-confirmed.
- The current register contains 18 physical cases, `ECDIS-003` through
  `ECDIS-020`, plus two source-only cases that are not physical confirmation.
- Geometry and source-coordinate presentation are confirmed for the cases
  where the register marks them as confirmed; those confirmations do not
  automatically close color/Danger or Description review.
- The bounded-area retest checkpoint now has fresh physical evidence for
  `IX 299/2024`, `IX 246/2025`, `IX 379/2025`, and the `IX 48/2024` control.
  The next physical checkpoint must retest the pre-fix danger artifacts
  (`VIII 467/26`, `VIII 789/26`), the capsized-vessel color issue in
  `IX 112/2022`, and the grouped buoy status isolation in `IX 34/2023`.
- `ECDIS-018` is currently **open**: the fresh retest confirms the corrected
  Red/Danger presentation for buoy 104, but does not select buoy 102 or prove
  the complete 39-object geometry set. The real-ECDIS stage therefore remains
  a finding-and-retest stage, not a release sign-off.
- The current code-side state is a release-freeze candidate: the full suite
  passes, the release geometry gate passes, and the RIGLIST Description path
  is verified across five NAVAREA regions (I, II, IV, VII, XIX) and 178
  entries. The next release action is one freshly built EXE followed by the
  physical Furuno batch; the release is not physically signed off yet.

Accepted or code-fixed decisions:

- Multi-vertex Lines now use one engine-wide geometry policy. The parser checks
  non-adjacent segment crossings, repeated non-adjacent vertices, suspiciously
  long legs, and track connectivity. A validated single-track candidate may
  be reordered; clearly separate tracks are emitted independently; ambiguous
  cases retain the raw Line plus reference points. Raw/selected coordinates
  and the decision are recorded in geometry audit/provenance, and no message
  is rejected for ordering alone.
- `V 502/26`: explicit multi-vertex Line with all 11 coordinates preserved.
  The generic Line validator selects the non-crossing single-track candidate
  order and retains the published sequence as raw provenance. This is a
  geometry-based repair, not a case-specific override; authoritative/physical
  confirmation remains a separate review item.
- `V 527/26`, `V 528/26`, `V 589/25`, and `V 593/25`: release 1.3.0
  endpoint-only fallback is exactly two Labels, with no Line, Area, or
  Circle; no invented straight route.
- `VIII 467/26`: one dangerous Point; current code emits `CHRED` and
  `checkDanger=1`; physical photo is from before the fix.
- `VIII 789/26`: `AGROUND` is a dangerous Wreck Point; current code emits
  `style=3`, `CHRED`, and `checkDanger=1`; physical photo is from before the
  fix.
- `IX 34/2023`: the grouped buoy table now isolates each row's status and
  danger semantics. The code-side export remains 39 Labels with no Area,
  Line, or Circle; buoy `102` is `style=4`, `NINFO`, `checkDanger=0`, while
  buoy `104` remains `style=4`, `CHRED`, `checkDanger=1`. Physical retest is
  still required.
- `VIII 806/26`: `UNLIT` remains an informational Orange/NINFO Point;
  only Description context is open.
- Five previously rejected bounded Areas (`IX 94/2024`, `IX 289/2024`,
  `IX 254/2026`, `XIII 42/2026`, and `XVIII 87/2026`) now use the restored
  repair-first Area path. The centroid-angle candidate is revalidated, emits
  one Area with no Line/Circle fallback, and records
  `GEOMETRY_ORDER_REPAIRED`; this is code-side confirmation only and still
  requires a physical ECDIS retest.

Open review items:

- Description/header context: `IV 616/2025`, `IV 653/2026`, `VII 124/2026`,
  `VII 154/2026`, `VII 210/2026`, `VII 221/2026`, `VIII 806/26`, and
  `IX 208/2026`.
- Offshore semantic/color loss: the Run #96 artifact reports `V 449/26` as
  Orange on Furuno instead of the intended offshore-activity presentation.
  The current code-side mapping is corrected to `RESBL` with
  `checkDanger=0`; physical confirmation of that new output remains open.
  This is separate from geometry and Description completeness.
- The four bounded-area retest photographs show the beginning of the
  Description field, not its complete contents. Their frames alone do not
  prove that the XML contains the complete text. ECDIS is treated as a
  faithful renderer of the XML, so any missing Description content must be
  located upstream in source parsing, handler construction, or XML
  serialization. Code-side descriptions for these cases are below the
  999-character Legacy ceiling; compare the generated XML directly with the
  source section.
- Danger/context carry-through: `VII 154/2026`; physical retests for
  `VIII 467/26`, `VIII 789/26`, and `IX 34/2023`/`ECDIS-018`.
- Geometry/classification: `V 502/26` has a source-order geometry defect with
  non-adjacent segment crossings; the generic repair candidate is emitted but
  still needs authoritative/physical confirmation. `VII 217/2026` is
  code-side corrected to six independent `RESBL` Labels; its physical
  geometry is already confirmed, while the corrected color and full
  Description require retest. `VIII 729/26` is code-side resolved as two
  independent informational Points with no Line; its historical physical
  Line remains pre-fix evidence. `VIII 895/26` is code-side resolved by the
  extensible implicit operational Area profile as one validated four-vertex
  Area; its historical physical Point remains pre-fix evidence. `III 122/26`
  is physically closed for geometry and blue styling by Run #96. The five
  repaired Areas above remain open only for physical import confirmation.
- `V 449/26`: the blue Point/Label remains the manual design reference and is
  now also the current code-side `RESBL` output; physical runtime confirmation
  remains open.

## Physical ECDIS cases

| Case | ECDIS evidence | Source message | What the ECDIS confirms | Observed gap | Status |
|---|---|---|---|---|---|
| ECDIS-001 | `attached_assets/image_1787929587528.jpg` (earlier artifact); `attached_assets/IMG_6713_1788093313089.jpeg` (Run #96 physical evidence) | `tests/fixtures/navarea_iii_spain_122_26.txt`, `NAVAREA III 122/26` | Run #96 shows the correct blue four-vertex Area presentation, labelled `NAV III 122/26`. The Area geometry and blue styling are physically confirmed. | The visible Description evidence covers only the beginning of the field; complete physical Description carry-through is not established by the frame. | Geometry and blue Area styling physically confirmed; no geometry retest is required. Keep only the Description evidence boundary open. |
| ECDIS-002 | `attached_assets/image_1787931172805.jpg` | `NAVAREA II - FRANCE.txt`, `NAVAREA II 307/2026` | One Point/Label is imported at `23°07.000′ N, 017°12.000′ W`; the label and source text are visible. | The photographed build shows `Orange` and an empty `Danger` column even though the message contains `DRIFTING HAZARDS` and `ADRIFT`. The source fix now expects `CHRED` and `checkDanger=1`. | Physical retest pending after next build |
| ECDIS-003 | `attached_assets/image_1787932526833.jpg` | `NAVAREA IV - USA.txt`, `NAVAREA IV 616/2025` | Point/Label coordinates are displayed correctly; the message produces five point objects and remains informational Orange. | The selected Description contains only `41-42.00N 070-30.30W`; it is missing the message header and `BOSTON (F)`. The `(F)` token was misread as an inline sublabel marker. | Case recorded; fix deferred until the collected-case batch |
| ECDIS-004 | `attached_assets/image_1787932566611.jpg` | `NAVAREA IV - USA.txt`, `NAVAREA IV 653/2026` | Point/Label coordinates and `BOSTON` are displayed correctly; the message produces six point objects and remains informational Orange. | The selected Description contains `BOSTON` and its coordinate but is missing the message header and operational context. | Case recorded; fix deferred until the collected-case batch |
| ECDIS-005 | `attached_assets/IMG_6663_1787886286920.jpeg` | `NAVAREA V - BRAZIL.txt`, `NAVAREA V 502/26` | A multi-vertex Line/Label is displayed. The visible ECDIS list shows the first four V 502 coordinates in the earlier published source order. The current release emits one repaired Line and one Label with all 11 coordinates, records `GEOMETRY_LINE_ORDER_REPAIRED`, and retains the raw order in provenance without component loss. | The earlier photograph is not evidence for the newly selected full traversal: it shows only the first four rows and predates the generic repair. The same coordinate set appears in `NAVAREA IV 789/2026` in the selected non-crossing trackline order (`D,E,G,F,C,H,A,I,J,K,B`), which is comparative evidence only. The CHM Brasil page exposes no archived V 502/26 message text, and the public mirror is not treated as a primary authority. | Earlier physical artifact confirms Line/Label presentation and source-list prefix; generic geometry repair is code-side validated; full physical/authoritative traversal confirmation remains open |
| ECDIS-006 | `attached_assets/IMG_6690_1788013231610.jpeg` (observed Furuno build); `attached_assets/image_1788013488728.jpg` (NAV Station reference, not Furuno) | `NAVAREA V - BRAZIL.txt`, `NAVAREA V 589/25` and sibling `V 593/25` | The NAV Station reference shows the tow warnings as a route following the coast, with `593/25` and `589/25` selectable at the shared route. This is evidence of another platform's route-engine result, not a Furuno result or a direct source of route vertices. The release 1.3.0 corpus and regression contract preserve both published endpoints as two Labels, with no Line, Area, or Circle. | The observed Furuno build showed only one Point/Label at the first position and is not evidence of the current 1.3.0 output. The NAVAREA text provides endpoints but no intermediate route points; drawing a straight A–B segment would not reproduce the NAV Station route and would falsely look like a safe route. | Release 1.3.0 contract: two endpoint Labels confirmed in corpus/XML; physical retest pending; future route-source or ENC-routing design required; no straight-line fix accepted |
| ECDIS-007 | `attached_assets/IMG_6691_1788015974418.jpeg` (manual User Chart edit); Run #96 physical observation | `NAVAREA V - BRAZIL.txt`, `NAVAREA V 449/26` | The manual User Chart reference demonstrates the intended blue Point/Label semantics for the preparatory offshore activity. The Run #96 physical check instead reports the generated `V 449/26` object as Orange. | Offshore-operation semantics are lost in the generated presentation: Orange does not preserve the intended offshore-activity classification. This is a semantic/color defect, separate from geometry and Description completeness. The manual reference is not evidence of a hidden route or provider algorithm. | Open: reproduce from Run #96 XML/EXE, restore the approved offshore semantic mapping, then retest color and Description on physical Furuno; `V 515/26` remains normal informational |
| ECDIS-008 | `attached_assets/IMG_6692_1788016839777.jpeg` (pre-fix artifact); `attached_assets/0_image_1788182297721.jpg`, `attached_assets/0_image_1788182348926.jpg`, `attached_assets/0_image_1788182429802.jpg`, `attached_assets/0_image_1788182440629.jpg`, `attached_assets/0_image_1788182574230.jpg`, `attached_assets/0_image_1788182586813.jpg`, `attached_assets/0_image_1788182605189.jpg`, `attached_assets/0_image_1788182615599.jpg`, `attached_assets/0_image_1788182626933.jpg` (post-fix geometry retest; build identity not provided) | `NAVAREA VII - SOUTH AFRICA.txt`, `NAVAREA VII 217/2026` | The physical retest selects all six source positions A–F individually. Every selected object is one-coordinate `Point`, and the displayed coordinates match the source in A–F order: A `28-42.640 S 015-56.700 E`, B `28-23.100 S 015-46.230 E`, C `28-38.210 S 016-01.330 E`, D `28-43.100 S 015-54.500 E`, E `28-20.660 S 015-49.330 E`, F `28-41.900 S 015-59.000 E`. The map frames show separate point labels with no connecting Line/ROUTE/TRACKLINE. | The supplied physical build shows Orange, but the reviewed offshore-activity presentation for `MINING/AMPLING/EXPLORATION VESSELS` is blue (`RESBL`); a new physical retest is required after the color correction. Physical Description is also incomplete: A shows `M/V BENGUELA GEM (C/S V5ID) - ON DP` only across the two A views, while B–F show clipped prefixes and do not expose their DP/anchor-spread roles. The old three-vertex D–F line remains linked as the pre-fix comparison artifact. | Physical retest: six independent Point positions, A–F coordinate order, and no-line behavior confirmed; color correction and all-six vessel/role Description confirmation remain open |
| ECDIS-009 | `attached_assets/IMG_6693_1788020413895.jpeg`, `IMG_6694_1788020493895.jpeg`, `IMG_6695_1788020493895.jpeg` (system-generated ECDIS artifacts) | `NAVAREA VII - SOUTH AFRICA.txt`, `NAVAREA VII 124/2026`, `VII 154/2026`, and `VII 210/2026` | All three artifacts show the expected one-coordinate Orange/Point presentation. The coordinates match the source: `VII 124/2026` at 29-19.170 S 014-07.180 E, `VII 154/2026` at 18-05.030 S 041-24.490 E, and `VII 210/2026` at 28-06.000 S 014-15.000 E. `VII 210/2026` is a towing-FPSO notice but publishes only one position, so no line is created. | The selected coordinate Description loses operational context in all three cases: `VII 124/2026` omits `CAPRICORNUS-1A CONDUCTING DRILLING OPERATION` and the 2 NM berth request; `VII 154/2026` omits `NOT UNDER COMMAND AND ADRIFT` and its danger semantics; `VII 210/2026` omits the towing-FPSO operation and destination Guyana. | Physical artifacts confirm single-point geometry; Description/context carry-through remains open for all three |
| ECDIS-010 | `attached_assets/IMG_6696_1788054988024.jpeg`, `IMG_6697_1788054988024.jpeg`, `IMG_6699_1788054988024.jpeg`, `attached_assets/IMG_6711_1788058309074.jpeg` (system-generated ECDIS artifacts) | `NAVAREA VII - SOUTH AFRICA.txt`, `NAVAREA VIII - INDIA.txt`, `NAVAREA IX - PAKISTAN.txt`, `NAVAREA VII 221/2026`, `NAVAREA VIII 729/26`, `NAVAREA VIII 467/26`, and `NAVAREA IX 112/2022` | `VII 221/2026` matches one Orange/Point at 28-35.800 S 013-54.700 E. `VIII 729/26` matches an Orange `NAV` object with width 3 and two vertices at 18-17.720 N 072-55.180 E and 18-17.770 N 072-55.920 E. `VIII 467/26` matches one Point at 02-54.840 N 090-03.070 E. The additional `IX 112/2022` artifact matches one Orange/Point at 26-52.100 N 052-19.400 E for a capsized vessel. | The `VIII 467/26` source says `CAPSIZED FISHING BOAT ... ADRIFT`; the photographed artifact is Orange, while the current parser expects `CHRED` with `checkDanger=1`. The artifact therefore records the earlier/physical color state, not the final danger expectation. The `IX 112/2022` photograph shows the same Orange/Point presentation for `VESSEL REPORTED CAPSIZED`, providing additional physical corroboration of the existing capsized-vessel danger-color issue. | Physical artifacts recorded; geometry confirmed; capsized-vessel danger-color retest remains open and is corroborated by the added `IX 112/2022` evidence |

| ECDIS-011 | `attached_assets/IMG_6702_1788020649477.jpeg`, `IMG_6701_1788020649477.jpeg`, `IMG_6700_1788020649477.jpeg` (system-generated ECDIS artifacts) | `NAVAREA VIII - INDIA.txt`, `NAVAREA VIII 895/26`, `VIII 806/26`, and `VIII 789/26` | `VIII 895/26` displays an Orange/Point at 22-24.850 N 067-30.660 E; `VIII 806/26` displays an Orange/Point at 15-21.160 N 073-45.770 E; `VIII 789/26` displays an Orange/Point at 19-11.500 N 072-46.400 E. All three coordinates match the source and the historical parser output. | `VIII 895/26` publishes one undivided hydrographic-survey vicinity list of four coordinates plus `WIDE BERTH REQUESTED`. The current extensible semantic profile maps it to one validated NINFO Area with those four source vertices, no Line, and no separate Labels. The historical Point is retained as physical evidence of the earlier build, not as source-semantic proof. | Physical artifact confirms the earlier single-point presentation; the corrected inferred Area and complete physical Description require retest |

| ECDIS-012 | `attached_assets/IMG_6704_1788054988024.jpeg` (historical system-generated ECDIS artifact) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 58/2023` | The historical physical ECDIS shows an Orange `NAV` object with width 3 and a three-vertex table containing the source positions: `26-35.496N 052-01.986E`, `26-38.808N 051-53.496E`, and `26-40.375N 051-53.896E`. The visible Description retains the message number, timestamp, `CENTRAL GULF`, and `QATAR` context. | The source describes 1500-meter safety zones around SPM2, SPM3, and SPM4. It provides three named centers and one common radius, but no connecting route. The reviewed source-to-XML mapping now emits three independent Circles at those centers with radius `1500/1852` NM (`0.809935...`), `NINFO`, and `checkDanger=0`; no Line or Label is emitted. Furuno is expected to render that XML faithfully; the old Line is not semantic evidence. | Code-side: three Circle objects confirmed in Modern and Legacy XML; physical retest of the corrected XML remains pending |
| ECDIS-013 | `attached_assets/IMG_6705_1788055292464.jpeg` (pre-fix system-generated artifact); `attached_assets/image_1788093077079.jpg` (supplied physical retest) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 299/2024`, Section 1 | The pre-fix artifact shows an Orange `NAV` object with width 3 and the first four visible vertices of a 10-coordinate object; that build produced one Label and one Line. The supplied retest shows the same source object as a closed bounded outline with `Orange`, width `2`, density `25%`, and the first four Area rows in source order: `26-10.030N 050-39.570E`, `26-10.050N 050-39.720E`, `26-10.070N 050-40.000E`, and `26-09.980N 050-40.280E`. | The source explicitly says `IN THE FOLLOWING BOUNDED AREA`; the retest now physically confirms the intended Area presentation rather than the old Line fallback. The current corpus export contains one closed Area with 10 unique source vertices, no Line, and no Label. The retest frame shows only four of the ten rows and the beginning of the Description; the remaining six row order and complete physical Description carry-through are not confirmed. Code-side Description length is below the 999-character Legacy ceiling. | Physical retest: Area geometry, color/width/density, and first four source rows confirmed; remaining row order and full physical Description carry-through remain open |
| ECDIS-014 | `attached_assets/IMG_6706_1788055436061.jpeg` (historical system-generated ECDIS artifact) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 7/2026`, Section 1 | The historical physical ECDIS shows an Orange `NAV` object with width 3 and two visible vertices matching source positions A and B: `24-12.360N 052-38.160E` and `24-11.870N 052-37.860E`. The visible Description retains the message number, timestamp, `SOUTHERN GULF`, and `UAE` context. | The source explicitly identifies a `DISPOSAL PIPELINE` and separately states that two `YELLOW MARK BUOYS` are deployed at positions A and B. The reviewed mixed-geometry mapping therefore emits one pipeline Line from A to B plus two independent buoy Labels at A and B (`style=4`, `CHYLW`, `checkDanger=0`). Repeated endpoint coordinates across the Line and Labels are intentional: they represent distinct objects. Furuno is expected to render this XML faithfully; the old single generic Label is not buoy evidence. | Code-side: mixed package confirmed in Modern and Legacy XML; physical retest of Line plus two yellow buoy Labels remains pending |
| ECDIS-015 | `attached_assets/IMG_6707_1788055664211.jpeg` (system-generated ECDIS artifact) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 208/2026`, Section 9 | The physical ECDIS shows the Orange `NAV` route object with width 3 and the first four visible vertices in source order: `26-02.720N 056-00.680E`, `26-22.560N 056-16.930E`, `26-24.350N 056-23.000E`, and `26-24.750N 056-31.110E`. The selected object carries the correct Section 9 content, and the release report records six route vertices in total, one Line and one Label; the related Section 8 contains a separate explicit 3 NM Circle. | This is a complex partitioned message. Section 8's Circle and Section 9's Line/Label receive the shared parent header plus only their relevant section. The frame does not show the complete Description field. The current partitioned code path builds the relevant Section 9 Description below 999; Legacy remains an exact Modern copy subject only to its mandatory 999 cap. The background circular mark is not independently counted as physical confirmation because its object details are not selected. | Physical artifact confirms the route geometry under review and the correct Section 9 selection; complete physical Description carry-through remains open, with no exporter or Legacy-format change authorized |
| ECDIS-016 | `attached_assets/IMG_6708_1788056651203.jpeg` (earlier system-generated ECDIS artifact); `attached_assets/image_1788093105809.jpg` (supplied physical retest) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 48/2024`, Section 1 | Both physical artifacts show an Orange Area with width 2 and density 25%. The supplied retest again shows all four source vertices in source order: `26-12.060N 050-39.610E`, `26-11.150N 050-39.240E`, `26-10.100N 050-39.200E`, and `26-09.790N 050-39.140E`. The source says two new pipelines are established in routes bounded by these coordinates; it does not literally use the word `AREA`. The release report confirms one Area and four source coordinates; the XML Description retains the operational section and removes the cancellation reference. | This is the positive physical Area confirmation and implicit-bounded-geometry control for comparison with `NAVAREA IX 299/2024` (`ECDIS-013`). `ROUTES BOUNDED BY FOLLOWING COORDINATES` is bounded-geometry evidence, not a Line instruction. The parser internally closes the polygon by repeating the first coordinate, while the ECDIS table displays four unique source vertices without an extra closing row; no source-position loss is observed. The supplied retest shows only the beginning of the Description; the code-side Description is below the 999-character Legacy ceiling, so exporter or Legacy truncation is not proven. | Physical retest confirms Area classification, all four unique vertices, source order, color/width/density, and no observed coordinate loss; full physical Description carry-through remains unconfirmed |
| ECDIS-017 | `attached_assets/IMG_6709_1788057916188.jpeg` (system-generated ECDIS artifact) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 102/2022`, Section 3 | The historical physical ECDIS artifact shows the earlier Orange generic Point for `NEW BOUY NO-3 ... FL(3)G 7S ... LAYED IN POSITION 24 34.68N 067 04.07E`. The current code-side classifier recognizes `BOUY` as a buoy alias and routes the case through `handle_buoy_semantics`. | Current code-side output is two buoy Labels for the two source positions, each `style=4`, `CHYLW` (yellow), and `checkDanger=0`; no Area, Line, or Circle is emitted. The historical Orange photograph is retained as pre-fix evidence. Description completeness remains unassessed from the clipped frame. | Code-side buoy classification and Yellow/non-danger presentation corrected; physical retest remains open |
| ECDIS-018 | `attached_assets/IMG_6712_1788060306592.jpeg` (pre-fix system-generated ECDIS artifact); `attached_assets/0_image_1788183833804.jpg`, `attached_assets/0_image_1788183850500.jpg` (fresh physical retest) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 34/2023`, Section 2, selected buoys `108` and `104` in the fresh frames | The fresh frame for `104` shows `16°59.720'N 041°19.280'E`, `Red`, `Triangle`, and a checked `Danger` column, matching source row `104 ISOLATED DANGER (MISSING)` and the corrected `style=4`, `CHRED`, `checkDanger=1` expectation. The other fresh frame selects `17°08.410'N 041°24.400'E`, which is source row `108 STBD LATERAL (MISSING)`, and shows Orange/Triangle with no Danger check. | Buoy `102` (`16°56.710'N 041°18.840'E`, `STBD LATERAL (UNLIT)`) is not selected in either fresh frame, so its required Orange/NINFO, `checkDanger=0` state is not physically confirmed. The visible table is only a partial view and `Total Object: 499` is the chart total, not proof of 39 NAVAREA objects. The Description field is clipped, so it cannot independently identify every selected buoy or prove full Description carry-through. | Partial physical retest: buoy `104` danger/red state confirmed and buoy `108` non-danger/orange behavior observed; code-side XML isolation remains verified in both Modern and Legacy exports, while buoy `102` and the complete 39-Label/no-Area/Line/Circle check remain open |
| ECDIS-019 | `attached_assets/image_1788093163545.jpg` (supplied physical retest; build identity not visible in frame) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 246/2025` | The physical ECDIS shows the selected bounded object as an Orange Area with width 2 and density 25%. The four displayed rows match the source exactly and remain in source order: `26-41.990N 051-53.260E`, `26-41.940N 052-00.750E`, `26-37.650N 052-00.720E`, and `26-37.700N 051-53.230E`. The Description field is at its beginning and shows `241500 UTC MAY 25`, `CENTRAL GULF`, `QATAR`, and the `HYSY289` operation. Other NAV labels visible in the chart background are not the selected object. | This fresh physical evidence confirms that the explicit `IN FOLLOWING BOUNDED AREA` case is imported as one four-vertex Area rather than a fallback Point or Line. The frame shows only the beginning of the Description; the code-side Description is below the 999-character Legacy ceiling, so exporter or Legacy truncation is not proven. The EXE/version identity is not visible in the frame. | Physical retest: Area geometry, four source vertices, and source order confirmed; full physical Description carry-through and build identity review pending |
| ECDIS-020 | `attached_assets/image_1788093188609.jpg` (supplied physical retest; build identity not visible in frame) | `NAVAREA IX - PAKISTAN.txt`, `NAVAREA IX 379/2025`, Section 1 | The physical ECDIS shows the selected restricted area as an Orange Area with width 2 and density 25%. The four displayed rows match the source exactly and remain in source order: `25-07.990N 055-10.770E`, `25-08.290N 055-10.630E`, `25-08.980N 055-11.220E`, and `25-08.910N 055-11.380E`. The Description field is at its beginning and shows `221500 UTC AUG 25`, `SOUTHERN GULF`, `UAE`, and the `RESTRICTED` notice context. | This fresh physical evidence confirms the bounded restricted-area case as one four-vertex Area rather than a fallback Line/Point. Only the beginning of the scrollable Description is visible; complete physical Description carry-through and the EXE/version identity, which is not visible in the frame, remain unconfirmed. | Physical retest: Area geometry, four source vertices, and source order confirmed; complete physical Description and build identity review pending |

### Bounded-area retest detail — 2026-08-31

The four photographs below are the supplied physical retest for the corrected
bounded-area build. The exact EXE/version is not legible in the frames, so the
photos are recorded as new-build retest evidence without claiming an
independently verified executable identity. In every selected object, the
ECDIS visibly shows a closed filled Area with `Orange`, `Width: 2`, and
`Density: 25%`. The physical frames do not expose a separate Danger field;
the corresponding current Modern XML checks confirm
`S52colorcode="NINFO"` and both Modern and Legacy XML checks confirm
`checkDanger="0"`. Legacy Area XML has no Modern `<display>` element, so its
color is not restated as a Legacy `S52colorcode` attribute here.

#### ECDIS-013 — NAVAREA IX 299/2024, Section 1

- **Evidence:** `attached_assets/image_1788093077079.jpg` is the new retest.
  The original `attached_assets/IMG_6705_1788055292464.jpeg` remains linked
  above as the pre-fix artifact and is not replaced.
- **Geometry:** The retest visibly shows a closed bounded outline and rows
  1–4 in source order:
  `26-10.030N 050-39.570E`, `26-10.050N 050-39.720E`,
  `26-10.070N 050-40.000E`, `26-09.980N 050-40.280E`. Code-side
  Modern/Legacy output is one Area with all 10 unique source vertices and no
  Line, Circle, or Label.
- **Semantics:** `IN THE FOLLOWING BOUNDED AREA` takes precedence over the
  construction/pipeline wording. The Area represents the trestle
  construction, seabed excavation, and pipeline-laying activity between
  BAPCO Terminal and Sitra Port; it is not a route Line.
- **Color/Danger:** Physical Area presentation is Orange, width 2, density
  25%. Code-side status is informational/non-danger (`NINFO`, `checkDanger=0`);
  no red/danger presentation is observed.
- **Description:** The physical field visibly begins
  `151500 UTC AUG 2024 / CENTRAL GULF / BAHRAIN`. The generated description
  retains the charts, the complete construction/excavation/pipeline
  operation, the caution/VHF 16/72/74 instruction, and excludes the
  cancellation reference. The frame shows only the beginning, so the full
  physical field is not independently confirmed.
- **Result:** Area geometry and the first four displayed source rows pass;
  remaining six physical row positions, complete on-screen Description, and
  executable identity remain open evidence items.

#### ECDIS-019 — NAVAREA IX 246/2025

- **Evidence:** `attached_assets/image_1788093163545.jpg`.
- **Geometry:** The selected object is one closed bounded Area, with all four
  displayed rows matching source order:
  `26-41.990N 051-53.260E`, `26-41.940N 052-00.750E`,
  `26-37.650N 052-00.720E`, `26-37.700N 051-53.230E`. Modern/Legacy
  output contains one Area with four unique vertices and no Line, Circle, or
  Label.
- **Semantics:** `SELF PROPELLED DP2 VESSEL HYSY289` carrying out sleepers
  installation is the operation located in the `FOLLOWING BOUNDED AREA`.
  The bounded coordinates are an Area boundary, not a fallback Point or
  connecting route.
- **Color/Danger:** Physical Area presentation is Orange, width 2, density
  25%. Code-side status is informational/non-danger (`NINFO`,
  `checkDanger=0`); no red/danger presentation is observed.
- **Description:** The physical field visibly begins
  `241500 UTC MAY 25 / CENTRAL GULF / QATAR` and includes the `HYSY289`
  operation context. The generated description retains the chart and
  sleepers-installation text. Only the beginning of the physical field is
  visible; complete carry-through and executable identity are unconfirmed.
- **Result:** Four-vertex Area geometry, source order, and visual styling
  pass; complete physical Description and build identity remain open.

#### ECDIS-020 — NAVAREA IX 379/2025, Section 1

- **Evidence:** `attached_assets/image_1788093188609.jpg`.
- **Geometry:** The selected object is one closed bounded Area, with all four
  displayed rows matching source order:
  `25-07.990N 055-10.770E`, `25-08.290N 055-10.630E`,
  `25-08.980N 055-11.220E`, `25-08.910N 055-11.380E`. Modern/Legacy
  output contains one Area with four unique vertices and no Line, Circle, or
  Label. Section 2 is a caution instruction and does not create another
  geometry object.
- **Semantics:** `RESTRICTED AREA ESTABLISHED IN VICINITY OF BURJ AL ARAB
  AND MADINAT JUMEIRAH BOUNDED BY FOLLOWING COORDINATES` is explicit Area
  evidence. The object is a restricted-area boundary, not a route Line.
- **Color/Danger:** Physical Area presentation is Orange, width 2, density
  25%. Code-side status is informational/non-danger (`NINFO`,
  `checkDanger=0`); no red/danger presentation is observed.
- **Description:** The physical field visibly begins
  `221500 UTC AUG 25 / SOUTHERN GULF / UAE` and shows the restricted-area
  context. The generated Section 1 description retains the charts, named
  vicinity, and bounded restricted-area instruction. Only the beginning of
  the physical field is visible; complete carry-through and executable
  identity are unconfirmed.
- **Result:** Four-vertex Area geometry, source order, and visual styling
  pass; complete physical Description and build identity remain open.

#### ECDIS-016 — NAVAREA IX 48/2024, Section 1 positive control

- **Evidence:** `attached_assets/image_1788093105809.jpg`, with the earlier
  `attached_assets/IMG_6708_1788056651203.jpeg` retained in the case row
  above.
- **Geometry:** The retest visibly shows one closed Area and all four unique
  source rows in order:
  `26-12.060N 050-39.610E`, `26-11.150N 050-39.240E`,
  `26-10.100N 050-39.200E`, `26-09.790N 050-39.140E`. Modern/Legacy
  output contains one Area with four unique vertices and no Line, Circle, or
  Label.
- **Semantics:** `ROUTES BOUNDED BY FOLLOWING COORDINATES` is the positive
  implicit-bounded control: two pipeline routes are represented by the
  published boundary Area, not by an invented straight Line.
- **Color/Danger:** Physical Area presentation is Orange, width 2, density
  25%. Code-side status is informational/non-danger (`NINFO`,
  `checkDanger=0`); no red/danger presentation is observed.
- **Description:** The physical field visibly begins
  `291500 UTC JAN 2024 / CENTRAL GULF / BAHRAIN`. The generated description
  retains the charts, the two-new-pipelines operation, the bounded-routes
  wording, and `MARINERS CAUTIONED`, while excluding the cancellation
  reference. Only the beginning of the physical field is visible, so full
  physical carry-through and executable identity are unconfirmed.
- **Result:** Positive-control Area geometry, source order, styling, and
  bounded semantics pass; complete physical Description and build identity
  remain open.

### ECDIS-010 clarification

`NAVAREA VII 221/2026` has correct single-point geometry, but its selected
Description does not show the source's buoy special-mark/yellow-light details
or the `VESSELS TO NAVIGATE WITH CAUTION` instruction. This is an open
Description/context carry-through issue, separate from the `VIII 467/26`
danger-color retest.

`NAVAREA VIII 729/26` reports lesser depths of about 6.2 m at two positions in
the channel and does not define a route, trackline, or segment between them.
The current code-side result is therefore two independent informational
Point/Label objects (`NINFO`, `checkDanger=0`) with no Line. The historical
Orange Line artifact is retained as pre-fix evidence; physical confirmation
of the corrected two-point presentation remains open.

`NAVAREA VIII 789/26` has correct one-point geometry, and the current parser
retains the full `AL JAFZIA UNMANNED AND REPORTED AGROUND` text in its
Description. The confirmed semantic decision is that `AGROUND` is a
dangerous Wreck Point, so the code now emits `style=3`, `CHRED`, and
`checkDanger=1`. The photographed Orange artifact predates this fix and
requires a physical retest.

`NAVAREA VIII 806/26` has correct one-point geometry and retains the local
`ST. GEORGE'S ISLAND LT ... UNLIT` text, but its Description omits the
message number, timestamp, region, location, and chart header present in the
source. Description header/context carry-through remains open. Orange/NINFO
with `checkDanger=0` is accepted for this unlit-aid notice.

## Source-only regression inputs

These inputs have code/XML checks but do not yet have a physical ECDIS
photograph and must not be counted as physical confirmation.

| Case | Source | Code-side result | Physical status |
|---|---|---|---|
| SRC-001 | `tests/fixtures/navarea_i_uk_181_26.txt`, `NAVAREA I 181/26` | Explicit Circle, center `55.083333, -19.000000`, radius `41`; ECDIS description retains operation/contact text without coordinate duplication. | Not physically tested |
| SRC-002 | `NAVAREA V - BRAZIL.txt`, `NAVAREA V 527/26` and `NAVAREA V 528/26` | Each message is recognized as a two-position tow operation, but no safe route geometry is emitted because the source provides no intermediate route vertices. | Not physically tested; route source required |

## Corpus impact inventory

The same source shape appears in two primary-corpus messages and currently
enters the sublabel path that drops shared context. This inventory is not a
physical-ECDIS confirmation; it identifies cases that must be covered before
the next build.

| Source message | Items | Current code-side symptom |
|---|---:|---|
| `NAVAREA IV 616/2025` in `NAVAREA IV - USA.txt` | 5 | Code-side audit now preserves the shared header and each local facility fragment, including `BOSTON (F)`, without creating a sixth label from `(G)`. Physical Description confirmation remains open. |
| `NAVAREA XII 354/2025` in `NAVAREA XII - USA.txt` | 5 | Code-side audit now preserves the shared header and each local facility fragment, including wrapped `CAMBRIA (Q)`, without retaining the separator. Physical Description confirmation remains open. |

The code-side correction covers **10 facility-list point objects across 2
messages** in the global primary corpus. Coastal sources were excluded from
this count and require a separate review.

## Description audit correction — complex and multi-geometry messages

The normal Description contract is **shared parent header/context plus the
section or local fragment relevant to the generated object**. The complete
parent notice is not copied onto every Area, Line, Circle, or Point. Grouped
Areas additionally receive their own group header and group coordinates.

This is confirmed by the current partitioned processing of `NAVAREA IX
208/2026`: Section 8's Circle receives the shared header plus Section 8;
Section 9's Line/Label receives the shared header plus Section 9. The
irrelevant sections are not copied into either object. The four RC1 Superboss
controls follow the same object-specific rule:

- `III 92/22`: seven valid Areas with zone-specific descriptions;
- `III 124/22`: one Line and one Label with the North-of-Line operational
  context, and no Area;
- `III 34/24`: two waiting Areas plus six route/section Lines and Labels,
  each retaining its relevant section;
- `IX 208/2026`: one six-vertex route Line, one 3 NM Circle, and one Label,
  with section-scoped descriptions and no Area.

These are code/XML conclusions, not physical confirmation for the three
Spain controls. `IX 208/2026` has physical confirmation of the selected
Section 9 route and its geometry; complete physical Description carry-through
remains open.

The earlier broad wording that the four bounded-area photographs show
“incomplete ECDIS Description output” is superseded by the narrower finding:
the frames show only the beginning of the field, while the code-side
Descriptions are below 999 and therefore do not implicate the Legacy cap.

## Planned changes and regression guards

These are the intended changes for the collected cases. They are recorded
before implementation so a fix does not silently alter geometry or unrelated
message classes.

## Code-side Description audit — 2026-08-31

The release corpus audit now records the source section, parent context,
handler-built Description, Modern XML Description, Legacy XML Description,
lengths, Legacy-cap state, and a mismatch classification for every emitted
object. The primary corpus audit covers **21 source files, 653 blocks, and 995
messages**. It reports **1,273 objects**, with 1,270 intentional
handler-to-Modern serializer sanitizations, three exact handler/Modern
matches, and no Modern-to-Legacy mismatches. No Legacy Description exceeded
the 999-character cap in this audit.

`NAVAREA IX 208/2026` was checked section-by-section: Section 8's Circle
contains the shared advisory context plus Section 8 only, while Section 9's
Line and Label contain the shared context plus Section 9 only. These are
code/XML results, not new physical-ECDIS confirmation.

| Case | Change to make | Must remain unchanged |
|---|---|---|
| `NAVAREA II 307/2026` | Keep one Point/Label, but classify `DRIFTING HAZARDS` / `ADRIFT` as danger metadata: `checkDanger=1`, dangerous color. | Coordinate, Point style, one-object geometry, and non-Circle classification |
| `NAVAREA IV 616/2025` | Preserve the shared message header and the point name `BOSTON (F)` in the point Description. Treat `(F)` as a facility code, not as a new sublabel marker. | Five Labels, source coordinate order, Orange/informational status, no Area/Line/Circle |
| `NAVAREA IV 653/2026` | Prefix each point Description with the shared message header and preserve the local name, e.g. `BOSTON`. | Six Labels, source coordinate order, Orange/informational status, no Area/Line/Circle |
| `NAVAREA III 122/26` | Preserve the confirmed four-vertex blue Area and verify the cleaned Description on ECDIS. | Area vertex order/count, four-sided geometry, blue styling, operation text, and cancellation removal |

### Required regression checks before the next EXE

- Compare object counts and coordinates before and after each fix.
- Assert that the common header is added to descriptions only; it must not
  change object names, coordinates, or geometry type.
- Assert that parenthetical facility codes such as `(F)`, `(N)`, `(E)`,
  `(A)`, and `(G)` are not emitted as separate objects.
- Assert that communication-service messages remain informational and do not
  inherit the drifting-hazard danger classification.
- Generate and inspect both Legacy and Modern XML.
- Run the full Python suite and the release geometry gate.
- Only then build the next EXE and repeat the physical ECDIS checks.

## Rules for closing a case

1. Do not mark a source-only case as physically verified.
2. Keep the original screenshot linked to the exact source message.
3. Record geometry, object semantics, color/Danger state, and Description separately.
4. A source-code test or generated XML check does not replace a physical ECDIS check.
5. Build a new EXE only after the current collection batch is explicitly frozen.