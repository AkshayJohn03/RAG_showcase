# Supplier Registry — Approved Vendors FY26

## Nordwerk Precision GmbH
- Supplier ID: SUP-044
- Supplies: Component **XK-7** (sole approved source, rev C certified).
- Lead time: 3 weeks standard, 7 days expedited.
- Contact: procurement@nordwerk.example, +49-30-000-114.
- Quality rating: 4.8/5.0 over last 12 months. Zero field failures on XK-7 rev C.

## Aldercroft Electrics
- Supplier ID: SUP-019
- Supplies: Component RK-2 (for Product Y), cabling, enclosures.
- Explicitly NOT approved for XK-7 (failed thermal qualification in Jan 2026).

## Relational note (GraphRAG demo)
Product X → uses → Component XK-7 → supplied_by → Nordwerk Precision GmbH.
A vector-only query for "supplier of Product X" has no direct lexical overlap;
the answer requires traversing Product X → XK-7 → Nordwerk.
