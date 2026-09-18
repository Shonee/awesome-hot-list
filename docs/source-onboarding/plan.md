# Implementation plan

1. Add parser and collector tests for Autohome, Gamersky, IT Home and Yicai; run them red.
2. Implement narrowly scoped official adapters and rerun focused tests.
3. Register channels and Yicai's live surface; update registry, site and scheduling tests.
4. Sync the versioned channel catalog with an append-only delta; update README and network probes.
5. Run complete tests, catalog check and read-only collection probes. Review the diff and record outcomes.

SSPAI is added only if its hot-content request is verified without a browser session or RSS.
