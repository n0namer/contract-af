"""Shared test fixtures for contract-af."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_app():
    """Mock AgentField application for testing agents without a live server."""
    app = MagicMock()
    app.ai = AsyncMock()
    app.call = AsyncMock()
    return app


@pytest.fixture
def sample_first_pages() -> str:
    """First 2-3 pages of a simple SaaS agreement for intake testing."""
    return """
SOFTWARE AS A SERVICE AGREEMENT

This Software as a Service Agreement ("Agreement") is entered into as of
January 15, 2026 ("Effective Date"), by and between:

Acme Cloud Inc., a Delaware corporation ("Provider"), and
TechStart LLC, a California limited liability company ("Customer").

RECITALS

WHEREAS, Provider offers a cloud-based project management platform; and
WHEREAS, Customer desires to subscribe to such platform;

NOW, THEREFORE, in consideration of the mutual covenants herein, the parties
agree as follows:

1. DEFINITIONS

1.1 "Authorized Users" means Customer's employees and contractors who are
    authorized to access the Service.
1.2 "Customer Data" means all data submitted by Customer through the Service.
1.3 "Service" means Provider's cloud-based project management platform.
1.4 "Work Product" means any and all inventions, discoveries, improvements,
    and works of authorship conceived during the Term, whether or not related
    to Provider's business.

2. GRANT OF LICENSE

2.1 Subject to the terms of this Agreement, Provider grants Customer a
    non-exclusive, non-transferable right to access and use the Service
    during the Term.
""".strip()


@pytest.fixture
def sample_contract_text() -> str:
    """Full text of a sample SaaS agreement with intentional risks."""
    return """
SOFTWARE AS A SERVICE AGREEMENT

This Software as a Service Agreement ("Agreement") is entered into as of
January 15, 2026 ("Effective Date"), by and between:

Acme Cloud Inc., a Delaware corporation ("Provider"), and
TechStart LLC, a California limited liability company ("Customer").

1. DEFINITIONS
1.1 "Authorized Users" means Customer's employees and contractors.
1.2 "Customer Data" means all data submitted by Customer through the Service.
1.3 "Confidential Information" means any non-public information disclosed
    by either party, including but not limited to trade secrets, business
    plans, and technical information.
1.4 "Service" means Provider's cloud-based project management platform.
1.5 "Work Product" means any and all inventions, discoveries, improvements,
    and works of authorship conceived during the Term, whether or not related
    to Provider's business.

2. GRANT OF LICENSE
2.1 Provider grants Customer a non-exclusive, non-transferable right to
    access and use the Service during the Term.
2.2 Customer shall not reverse engineer, decompile, or disassemble the Service.

3. FEES AND PAYMENT
3.1 Customer shall pay the fees set forth in the Order Form.
3.2 All fees are non-refundable.
3.3 Provider may increase fees upon 30 days written notice.

4. CUSTOMER DATA
4.1 Customer retains all rights to Customer Data.
4.2 Provider shall maintain reasonable security measures.
4.3 Upon termination, Provider shall delete Customer Data within 90 days.

5. INTELLECTUAL PROPERTY
5.1 All Work Product shall be the sole property of Provider.
5.2 Customer hereby assigns all right, title, and interest in any
    Work Product to Provider.

6. CONFIDENTIALITY
6.1 Each party shall maintain the confidentiality of the other party's
    Confidential Information for a period of five (5) years.
6.2 Confidential Information excludes information that is publicly available.

7. REPRESENTATIONS AND WARRANTIES
7.1 Provider warrants that the Service will perform substantially in
    accordance with the documentation.
7.2 EXCEPT AS EXPRESSLY SET FORTH HEREIN, PROVIDER MAKES NO WARRANTIES.

8. LIMITATION OF LIABILITY
8.1 IN NO EVENT SHALL PROVIDER'S AGGREGATE LIABILITY EXCEED THE FEES
    PAID BY CUSTOMER IN THE TWELVE MONTHS PRECEDING THE CLAIM.
8.2 IN NO EVENT SHALL PROVIDER BE LIABLE FOR ANY INDIRECT, INCIDENTAL,
    SPECIAL, OR CONSEQUENTIAL DAMAGES.

9. INDEMNIFICATION
9.1 Customer shall indemnify Provider against all claims arising from
    Customer's use of the Service, including attorney's fees.
9.2 Provider shall have no obligation to indemnify Customer.

10. TERM AND TERMINATION
10.1 This Agreement commences on the Effective Date and continues for
     one (1) year ("Initial Term"), automatically renewing for successive
     one-year periods unless either party provides 90 days written notice.
10.2 Provider may terminate immediately upon Customer's breach.
10.3 Customer may terminate only at the end of a renewal period.

11. NON-COMPETE
11.1 During the Term and for two (2) years thereafter, Customer shall not
     develop or market any product that competes with the Service in any
     jurisdiction where Provider does business.

12. PERPETUAL LICENSE
12.1 Customer grants Provider an exclusive, perpetual, irrevocable,
     worldwide license to use, modify, and distribute any feedback,
     suggestions, or improvements provided by Customer.

13. GOVERNING LAW
13.1 This Agreement shall be governed by the laws of the State of Delaware.

14. SURVIVAL
14.1 Sections 5, 6, 8, 9, 11, 12, and 14 shall survive termination
     of this Agreement.

15. MISCELLANEOUS
15.1 Entire Agreement. This Agreement constitutes the entire agreement.
15.2 Amendments. No amendment shall be effective unless in writing.
15.3 Notices. All notices shall be in writing.
15.4 Counterparts. This Agreement may be executed in counterparts.
""".strip()
