# Vendored specialist personas — agency-agents

Source: <https://github.com/msitarzewski/agency-agents> at commit
`053ddbbf392a1688fc7043d81529f47ef2cf86c8` (MIT — see `LICENSE` in this directory).

These files are copied **unchanged** so they can be diffed against upstream on
refresh. `agents/persona_library.py` maps this repo's `SpecialistFamily` values to
them and distils each one (identity, mission, critical rules, workflow, success
criteria; no code samples) into the `system_prompt` of the specialist agents that
`services/company_agency.py` registers for a company.

Only families with a genuine counterpart are mapped. To add or refresh one:
copy the upstream file here unchanged, add the mapping in `FAMILY_PERSONAS`,
review the text as you would any prompt that reaches a model, and update the
commit above.
