---
name: Offshore operational semantics
description: Domain rule for distinguishing offshore work/deployment notices from messages that define navigational geometry.
---

An offshore notice should be modeled as an operation first when its coordinates are vessel positions, deployment points, work limits, or source-reference points rather than vertices of a navigational object. Anchor spreads, mooring deployments, tows, rig moves, and similar activity notices must not be converted into inferred polygons or connecting lines without explicit source wording.

**Why:** Historical NAVAREA messages repeatedly use the same operational vocabulary with different geometry semantics. Many pipeline, cable, drilling, and seismic notices explicitly define areas or tracklines, but launch/deployment and movement notices often provide disconnected points or only a current position. Treating every coordinate list as a shape creates false geometry and can produce self-intersections.

**How to apply:** Preserve operation type, time window, vessels, berth/clearance, and raw coordinate roles separately. Use Area/Line/Route/Point/AtoN only when the notice explicitly defines that geometry; otherwise retain unconnected source-reference points and flag the operation as semantically unresolved.

For the first compatible release, add semantic metadata and a geometry-status gate before geometry handlers; defer a full OperationObject until structured operation data must be queried, partitioned, or projected separately from existing Furuno objects.

**Why:** The current message model already carries metadata and the Furuno XML exporters only know Area/Line/Circle/Label-style objects. A metadata-first change can stop unsafe inference without an XML schema migration, while a full object would require changes across counting, partitioning, exporting, and tests.

**How to apply:** Treat `semantic_mode` and `geometry_status` as orthogonal: mode says whether operation or geometry has precedence, while status says how strongly coordinates are evidenced. Fields alone are insufficient; operation-first classification must run before area/line handlers.