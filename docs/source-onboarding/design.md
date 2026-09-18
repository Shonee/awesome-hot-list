# Official hotlist onboarding

## Scope

Add Autohome's daily hot topics, Gamersky's hot-news sidebar, IT Home's daily ranking, Yicai's editorial homepage headlines and its separate 7x24 brief feed. SSPAI's hot-content view is conditional on verifying a direct background request; its RSS feed is not a substitute.

## Approach

Each adapter reads only its named official ranking, validates source-owned links and a nonempty result, and returns the existing `ChannelSnapshot` contract. Yicai's `collect_live` uses the official brief JSON and the shared recent-item window; live failure does not discard homepage headlines. Register the live surface in the current 15-minute workflow and leave ordinary rankings on the hourly schedule.

## Risks And Verification

HTML modules and unauthenticated endpoints can change. Parser fixtures check ranking isolation and link validation; collection probes verify real items. The catalog baseline stays immutable, with a new delta for registry additions. No RSS parsing or unverified intermediary requests are introduced.
