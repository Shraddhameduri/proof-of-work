# Proof of work

Four small, self-contained engineering investigations. For each one I took a
real, publicly reported problem at a company I have applied to, reproduced it
before touching anything, built the smallest fix or analysis that addresses
it, and measured the result. Each folder holds the write-up, the code, and the
evidence; nothing here is a claim I did not run myself.

| Company | Problem | Evidence | Write-up |
| --- | --- | --- | --- |
| Plaid | The Python SDK's client configuration silently drops credentials passed as snake_case keys, case variants, or constructor arguments ([plaid-python#587](https://github.com/plaid/plaid-python/issues/587)) | 5 failure modes reproduced on plaid-python 45.0.0; fix passes 29 new unit tests | [Case study](case-studies/plaid.md) · [code](plaid/) |
| New Relic | The Python agent re-parses the entire CA certificate store on every harvest connection ([newrelic-python-agent#1834](https://github.com/newrelic/newrelic-python-agent/issues/1834)) | 20 parses across 20 simulated harvests → 1 after the fix; 62 tests pass | [Case study](case-studies/newrelic.md) · [code](newrelic/) |
| Scale AI | The MCP-Atlas benchmark's README fixture carries no task ID or dataset revision, so its provenance cannot be verified ([mcp-atlas#84](https://github.com/scaleapi/mcp-atlas/issues/84)) | Metadata-only audit; validation fails 8 checks before, passes 10 after | [Case study](case-studies/scaleai.md) · [code](scaleai/) |
| Affirm | Implement Subsampled Smooth Calibration Error (SSCE) from Haghtalab et al. (2024), "Truthfulness of Calibration Measures" ([splinator#10](https://github.com/Affirm/splinator/issues/10)) | 15 new tests pass; SSCE scores a rigged forecaster 0.613 where ECE scores 0.061 | [Case study](case-studies/affirm.md) · [code](affirm/) |

Roles these map to (all applied for): Plaid — Software Engineer, Backend
(Seattle); New Relic — Software Engineer II, Query Gateway (Portland);
Scale AI — Frontier Agents Engineer, Applied AI (New York); Affirm — Software
Engineer II, Backend, requisition 8003028003 (Remote, US).

The patches are against the companies' public repositories and are provided
as evidence of the work; the underlying projects keep their own licences.
