# Test Fixtures: Sample Contracts

Realistic contract fixtures for testing the contract-af analysis pipeline. Each
contract contains intentional risks at varying levels of subtlety so tests can
assert on detection capabilities.

## Fixtures

### sample_nda.txt (~3 pages, simple)

Mutual NDA between TechCorp Inc. and DataFlow LLC.

**Intentional risks:**

1. **Overly broad Confidential Information definition** (Section 1.1) — covers
   "any information shared, whether written, oral, electronic, or observed" with
   no materiality threshold or marking requirement.
2. **Missing exclusion for independently developed information** (Section 3.1) —
   the standard exclusions list omits the carve-out for information independently
   developed by the Receiving Party without use of Confidential Information.

### sample_saas_agreement.txt (~20 pages, standard complexity)

SaaS agreement between Acme Cloud Inc. (Provider) and TechStart LLC (Customer).

**Intentional risks:**

1. **OBVIOUS — Broad non-compete** (Section 11) — restricts Customer from
   competing in "any jurisdiction where Provider does business," which is
   unreasonably broad for a SaaS customer agreement.
2. **OBVIOUS — Asymmetric indemnification** (Section 9) — Customer indemnifies
   Provider, but Provider provides no reciprocal indemnification (e.g., no IP
   infringement indemnity).
3. **HIDDEN — Overly broad "Work Product" definition** (Section 1.14) — defined
   as anything created by Customer "whether or not related to Provider's
   business," capturing Customer's own independent work.
4. **COMBINATION — IP assignment + perpetual license** (Sections 5.2 + 12) —
   Section 5.2 assigns all Work Product IP to Provider, while Section 12 grants
   Provider an exclusive perpetual license to all Feedback. Together, these
   eliminate Customer's IP rights over anything created or communicated during
   the agreement.
5. **HIDDEN TRAP — Non-compete survives termination** (Section 14) — the
   survival clause explicitly lists Section 11 (Non-Competition) as surviving
   termination, meaning the 24-month non-compete clock starts after termination
   and the obligation cannot be escaped by ending the contract.

**Additional notable provisions:**
- Non-refundable fees (Section 3.2)
- Provider can increase fees with only 30 days notice (Section 3.4)
- Asymmetric termination rights (Section 10.4 — Customer cannot terminate for
  convenience mid-term)
- Auto-renewal with 60-day notice requirement (Section 10.2)

### sample_employment.txt (~15 pages, IP/non-compete heavy)

Employment agreement between GlobalTech Corp. (Employer) and an individual
employee (Senior Staff Engineer).

**Intentional risks:**

1. **Broad IP assignment covering personal projects** (Section 4.1-4.2) —
   assigns all Inventions to Employer regardless of whether they are related to
   Employer's business, created during working hours, or created using Employer
   resources.
2. **Worldwide non-compete for 24 months** (Section 6.1-6.2) — applies globally
   with a two-year duration, which is aggressive for an employment agreement.
3. **No carve-out for prior inventions** (Section 4 + Exhibit A) — Exhibit A
   forces Employee to declare no prior inventions exist, effectively assigning
   everything to Employer.
4. **Perpetual confidentiality** (Section 5.1) — confidentiality obligations
   last "at all times thereafter in perpetuity," which is unusual and
   potentially unenforceable.
5. **Overly broad non-solicitation** (Section 7.2) — applies to ALL customers
   and clients of Employer, "including those with whom Employee did not have
   direct contact or responsibility."
