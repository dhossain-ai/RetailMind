"""Generate data/sample_docs/sample_policy.pdf using PyMuPDF.

Run once from the repo root:
    py -3.11 scripts/generate_sample_doc.py

The resulting PDF is committed to the repository so other developers
do not need to run this script.
"""

from pathlib import Path
import fitz  # PyMuPDF

OUTPUT = Path("data/sample_docs/sample_policy.pdf")

PAGES = [
    (
        "RetailMind — Store Operations & Policy Manual",
        """\
1. PURPOSE

This manual sets out the standard operating policies for all RetailMind
stores. It covers customer returns, supplier relationships, store hours,
product handling, and staff responsibilities. All store managers and
department leads are required to read and follow these policies.

2. SCOPE

These policies apply to all RetailMind retail locations across all regions.
Regional managers may issue supplementary guidance, but may not override
any policy in this document without written approval from the Operations
Director.
""",
    ),
    (
        "Section 3 — Customer Returns",
        """\
3. CUSTOMER RETURN POLICY

3.1 Standard return window
Customers may return any unused, undamaged product within 30 days of
purchase with a valid receipt. Items returned within this window are
eligible for a full refund to the original payment method.

3.2 Extended return window
For purchases made between 1 November and 31 December (holiday season),
the return window is extended to 60 days from the date of purchase.

3.3 Non-returnable items
The following categories are non-returnable:
  - Perishable food and beverage items once opened
  - Personal care products once unsealed
  - Digital downloads and software licences

3.4 Damaged or defective goods
Items that are damaged or defective on arrival may be returned or
exchanged at any time within 90 days, regardless of whether the standard
30-day window has passed. Proof of defect (photograph or in-store
inspection) is required.

3.5 Return without receipt
Returns without a receipt are accepted at the store manager's discretion.
The customer will receive store credit at the current selling price,
capped at the maximum 30-day window from the estimated purchase date.
""",
    ),
    (
        "Section 4 — Supplier & Procurement Policy",
        """\
4. SUPPLIER VETTING AND PROCUREMENT

4.1 Approved supplier list
All products sold in RetailMind stores must be sourced from suppliers on
the Approved Supplier List (ASL). The procurement team maintains the ASL
and reviews it quarterly. No store may purchase stock from a supplier
not on the ASL without prior written approval from the Procurement Director.

4.2 Supplier onboarding
New suppliers must complete a four-step vetting process:
  Step 1 — Submit company registration documents and insurance certificates.
  Step 2 — Pass a quality audit conducted by RetailMind's QA team or an
            accredited third-party auditor.
  Step 3 — Agree to RetailMind's Supplier Code of Conduct, which includes
            labour standards, environmental requirements, and anti-bribery
            provisions.
  Step 4 — Complete a trial order of no more than €5,000 before being
            granted full ASL status.

4.3 Pricing and contracts
All supplier pricing must be agreed in writing before any order is placed.
Verbal pricing agreements are not binding. Contracts are renewed annually
in January unless either party gives 60 days' written notice of termination.

4.4 Preferred supplier incentives
Suppliers who achieve an on-time delivery rate of 95% or above and a
defect rate below 0.5% over a rolling 12-month period are designated
Preferred Suppliers. Preferred Suppliers are given priority consideration
for new product line placements.
""",
    ),
    (
        "Section 5 — Store Operations",
        """\
5. STORE HOURS AND OPERATIONS

5.1 Standard store hours
All RetailMind stores operate on the following schedule unless a regional
supplement specifies otherwise:
  Monday to Friday:   08:00 – 20:00
  Saturday:           09:00 – 18:00
  Sunday:             10:00 – 16:00

5.2 Public holidays
Stores are closed on national public holidays. Stores in regions with
local bank holidays must post the closure notice at least 7 days in advance.

5.3 Opening and closing procedures
The store manager or a designated deputy must be present for opening and
closing. The opening checklist includes: cash float verification, safety
walkthrough, and POS system startup. The closing checklist includes:
cash reconciliation, stock count of high-value items, and alarm activation.

5.4 Minimum staffing levels
At no time may a store operate with fewer than two staff members on the
floor. If staffing falls below this level, the store manager must contact
the regional HR coordinator immediately to arrange cover.
""",
    ),
    (
        "Section 6 — Product Handling",
        """\
6. PRODUCT HANDLING AND STORAGE

6.1 Receiving stock
All deliveries must be checked against the purchase order at the point of
receipt. Discrepancies of more than 2% by quantity or value must be reported
to the procurement team within 24 hours. Accepted stock must be logged in
the inventory system on the day of receipt.

6.2 Temperature-sensitive products
Coffee, dairy, and fresh produce must be stored at the temperatures specified
on the product packaging. Temperature logs must be completed twice daily.
Products found outside the safe temperature range must be quarantined and
disposed of according to the Waste Disposal Procedure (Appendix B).

6.3 High-value item security
Items with a retail price above €50 must be stored in a locked display
case or behind the counter when not being shown to a customer. Inventory
counts for high-value items are conducted at the close of every business day.

6.4 Damaged stock
Damaged stock must be removed from the sales floor immediately and logged
in the damage register. Damaged items may not be sold at a discount without
approval from the store manager. Items with a cost value above €20 must be
reported to the regional loss-prevention team before disposal.

6.5 Expiry date management
Staff must check expiry dates during every restocking cycle. Products within
14 days of their expiry date must be moved to the clearance section and
marked with a minimum 25% discount. Products past their expiry date must
be removed from sale immediately.
""",
    ),
    (
        "Section 7 — Data and Privacy",
        """\
7. CUSTOMER DATA AND PRIVACY

7.1 Data collected at point of sale
RetailMind collects transaction data (items purchased, price, date, and
store location) for every sale. No personally identifiable information is
collected at point of sale unless the customer voluntarily provides it
for the loyalty programme.

7.2 Loyalty programme data
Customers who join the loyalty programme consent to the collection of their
name, email address, and purchase history. This data is used solely for
programme administration and personalised offers. It is never sold to third
parties.

7.3 Retention periods
Transaction data is retained for 7 years to satisfy tax and audit
requirements. Loyalty programme data is retained for as long as the account
is active, plus 2 years after the last transaction.

7.4 Data breaches
Any suspected data breach — including unauthorised access to the POS system
or loss of a device containing customer data — must be reported to the Data
Protection Officer within 24 hours of discovery. The DPO will determine
whether regulatory notification is required under applicable law.
""",
    ),
]


def build_pdf(output_path: Path) -> None:
    doc = fitz.open()
    for title, body in PAGES:
        page = doc.new_page(width=595, height=842)  # A4 at 72dpi

        # Title
        page.insert_text(
            (50, 60),
            title,
            fontname="helv",
            fontsize=14,
        )

        # Horizontal rule (drawn as a thin rect)
        page.draw_line((50, 72), (545, 72))

        # Body text — wrap at ~90 chars per line, 14pt leading
        y = 95
        for para in body.split("\n"):
            page.insert_text(
                (50, y),
                para,
                fontname="helv",
                fontsize=10,
            )
            y += 14
            if y > 800:
                break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    print(f"Generated: {output_path}  ({output_path.stat().st_size} bytes)")


if __name__ == "__main__":
    build_pdf(OUTPUT)
