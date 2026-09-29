# Method boundary

GenCore represents an evolving engineering task as a versioned design-state
graph. Evidence is routed to role-specific views; proposed mutations are checked
by a transaction gateway; deterministic evaluation decides whether generation
can continue, must abstain, requires human input, or has sufficient independent
evidence for acceptance.

The public package retains five method roles: scene and constraint extraction,
solution and parameter reasoning, geometry planning, independent validation,
and repair/reflection. Agent outputs are proposals rather than authoritative
state mutations. CAD writes remain behind deterministic operation contracts.

Production model providers, credential storage, experiment administration, web
interfaces, and organization-specific assets are outside this method boundary.
