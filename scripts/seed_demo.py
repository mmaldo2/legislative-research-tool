"""Seed a compelling demo workspace for the legislative research platform.

Creates a "Model Data Privacy Act" workspace targeting California with
precedent bills, a pre-computed outline, drafted sections with revision
history, and a research conversation.

Idempotent: skips creation if the workspace already exists.

Usage:
    python scripts/seed_demo.py
"""

import asyncio
import uuid

from sqlalchemy import select

from src.database import async_session_factory
from src.models.bill import Bill
from src.models.conversation import Conversation, ConversationMessage
from src.models.policy_workspace import (
    PolicyGeneration,
    PolicySection,
    PolicySectionRevision,
    PolicyWorkspace,
    PolicyWorkspacePrecedent,
)

WORKSPACE_TITLE = "Model Data Privacy Act"
DEMO_CLIENT_ID = "demo-user-001"


def _id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Section content used for the two drafted sections
# ---------------------------------------------------------------------------

DEFINITIONS_V1 = """\
## Section 1 — Definitions

For the purposes of this Act, the following definitions apply:

**(a) "Personal data"** means any information that identifies, relates to, or could
reasonably be linked, directly or indirectly, to a particular consumer or household.

**(b) "Consumer"** means a natural person who is a California resident.

**(c) "Business"** means a sole proprietorship, partnership, LLC, corporation, or other
legal entity that is organized under the laws of California, or that collects
consumers' personal data.

**(d) "Processing"** means any operation performed on personal data, whether by
automated means or otherwise, including collection, use, storage, disclosure,
analysis, deletion, or modification.

**(e) "Sensitive data"** means personal data that reveals racial or ethnic origin,
religious beliefs, health information, precise geolocation, or biometric data used
for identification purposes.
"""

DEFINITIONS_V2 = """\
## Section 1 — Definitions

For the purposes of this Act, the following definitions apply:

**(a) "Personal data"** means any information that identifies, relates to, describes,
is reasonably capable of being associated with, or could reasonably be linked,
directly or indirectly, to a particular consumer or household, including but not
limited to identifiers such as a real name, alias, postal address, unique personal
identifier, online identifier, IP address, email address, account name, social
security number, driver's license number, passport number, or other similar
identifiers.

**(b) "Consumer"** means a natural person who is a California resident, as defined in
Section 17014 of Title 18 of the California Code of Regulations.

**(c) "Business"** means a sole proprietorship, partnership, LLC, corporation,
association, or other legal entity that is organized or operated for the profit or
financial benefit of its shareholders or other owners and that:
  1. Has annual gross revenues in excess of twenty-five million dollars ($25,000,000);
  2. Annually buys, receives, sells, or shares the personal data of 100,000 or more
     consumers or households; or
  3. Derives 50 percent or more of its annual revenues from selling or sharing
     consumers' personal data.

**(d) "Processing"** means any operation or set of operations performed on personal data
or on sets of personal data, whether or not by automated means, including collection,
recording, organization, structuring, storage, adaptation, alteration, retrieval,
consultation, use, disclosure by transmission, dissemination, alignment, combination,
restriction, erasure, or destruction.

**(e) "Sensitive personal data"** means personal data that reveals:
  1. Racial or ethnic origin;
  2. Religious or philosophical beliefs;
  3. Citizenship or immigration status;
  4. Genetic or biometric data processed for the purpose of uniquely identifying an
     individual;
  5. Health information;
  6. Sex life or sexual orientation; or
  7. Precise geolocation data.

**(f) "De-identified data"** means data that cannot reasonably be used to infer
information about, or otherwise be linked to, an identified or identifiable consumer,
provided that the business possessing the data has implemented technical safeguards
and business processes that prohibit re-identification.

**(g) "Service provider"** means a legal entity that processes personal data on behalf
of a business pursuant to a written contract.
"""

CONSUMER_RIGHTS_V1 = """\
## Section 3 — Consumer Rights

**(a) Right to Know.** A consumer shall have the right to request that a business
disclose the categories and specific pieces of personal data it has collected about
the consumer.

**(b) Right to Delete.** A consumer shall have the right to request the deletion of
personal data that a business has collected from the consumer.

**(c) Right to Opt-Out.** A consumer shall have the right to direct a business that
sells or shares personal data about the consumer to third parties to stop selling or
sharing that data.
"""

CONSUMER_RIGHTS_V2 = """\
## Section 3 — Consumer Rights

**(a) Right to Know.** A consumer shall have the right to request that a business that
collects personal data about the consumer disclose to the consumer:
  1. The categories of personal data it has collected about the consumer;
  2. The categories of sources from which the personal data is collected;
  3. The business or commercial purpose for collecting, selling, or sharing personal
     data;
  4. The categories of third parties to whom the business discloses personal data; and
  5. The specific pieces of personal data it has collected about the consumer.

**(b) Right to Delete.** A consumer shall have the right to request the deletion of
any personal data about the consumer which has been collected from the consumer by a
business. Upon receiving a verifiable consumer request, a business shall delete the
consumer's personal data from its records and direct any service providers to delete
the consumer's personal data from their records.

**(c) Right to Correct.** A consumer shall have the right to request that a business
correct inaccurate personal data that it maintains about the consumer.

**(d) Right to Opt-Out of Sale and Sharing.** A consumer shall have the right to
direct a business that sells or shares personal data about the consumer to third
parties to stop selling or sharing that personal data. A business shall provide a
clear and conspicuous link on its internet homepage titled "Do Not Sell or Share My
Personal Information."

**(e) Right to Limit Use of Sensitive Personal Data.** A consumer shall have the
right to direct a business that collects sensitive personal data to limit its use of
the consumer's sensitive personal data to that use which is necessary to perform the
services or provide the goods reasonably expected by an average consumer.

**(f) Right to Data Portability.** Upon a verifiable request, a business shall provide
the consumer's personal data in a structured, commonly used, and machine-readable
format that allows the consumer to transmit the data to another entity without
hindrance.
"""


# ---------------------------------------------------------------------------
# Outline sections (the 3 non-drafted ones get only outline content)
# ---------------------------------------------------------------------------

SCOPE_CONTENT = """\
## Section 2 — Scope & Applicability

*[Outlined — not yet drafted]*

This section will establish the jurisdictional reach of the Act, including:
- Territorial applicability to businesses operating in California
- Exemptions for small businesses, nonprofits, and government entities
- Relationship to federal preemption (HIPAA, GLBA, FERPA)
- Threshold criteria for covered businesses
"""

OBLIGATIONS_CONTENT = """\
## Section 4 — Business Obligations

*[Outlined — not yet drafted]*

This section will detail the affirmative obligations of covered businesses, including:
- Privacy policy disclosure requirements
- Data minimization and purpose limitation
- Consent requirements for processing sensitive data
- Vendor and service provider contractual obligations
- Data protection impact assessments
- Record-keeping and accountability measures
"""

ENFORCEMENT_CONTENT = """\
## Section 5 — Enforcement & Remedies

*[Outlined — not yet drafted]*

This section will establish the enforcement framework, including:
- Regulatory authority (California Privacy Protection Agency)
- Civil penalties schedule and escalation
- Private right of action for data breaches
- Cure period provisions
- Interaction with existing AG enforcement powers
"""

# ---------------------------------------------------------------------------
# Conversation messages
# ---------------------------------------------------------------------------

CONVERSATION_MESSAGES = [
    {
        "role": "user",
        "content": (
            "I'm drafting a comprehensive data privacy act for California. What are "
            "the key provisions I should include to match or exceed the protections in "
            "the CCPA and CPRA?"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Based on my analysis of the CCPA (AB 375), CPRA (Prop 24), and comparable "
            "frameworks in Virginia (VCDPA), Colorado (CPA), and Connecticut (CTDPA), "
            "I'd recommend structuring your act around these core pillars:\n\n"
            "1. **Expanded Definitions** — Broaden 'personal data' to include inferred and "
            "derived data, and add a robust 'sensitive data' category covering biometric, "
            "geolocation, and health data.\n\n"
            "2. **Strengthened Consumer Rights** — Go beyond CCPA's right to know/delete/opt-out "
            "by adding rights to correction, data portability, and limiting use of sensitive data "
            "(as CPRA does).\n\n"
            "3. **Affirmative Business Obligations** — Require data minimization, purpose "
            "limitation, and mandatory data protection impact assessments for high-risk "
            "processing (modeled on GDPR Art. 35).\n\n"
            "4. **Universal Opt-Out Mechanism** — Mandate recognition of Global Privacy Control "
            "(GPC) signals, going further than CCPA's current requirement.\n\n"
            "5. **Enhanced Enforcement** — Maintain the California Privacy Protection Agency "
            "as primary enforcer, increase civil penalty caps, and expand the private right "
            "of action beyond data breaches.\n\n"
            "I found 3 relevant precedent bills in the database that we can use as "
            "reference points. "
            "Shall I pull those in and start drafting the definitions section?"
        ),
    },
    {
        "role": "user",
        "content": (
            "Yes, please add those precedents and draft the definitions section first. "
            "I want the definitions to be comprehensive enough to future-proof the act "
            "against emerging technologies like AI profiling and automated decision-making."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "I've added the precedent bills to your workspace and drafted Section 1 — Definitions. "
            "The draft includes 7 core definitions covering personal data, consumers, businesses, "
            "processing, sensitive data, de-identified data, and service providers.\n\n"
            "A few notes on the draft:\n"
            "- The **personal data** definition is intentionally broad and includes an open-ended "
            "list of identifiers, which gives room to capture novel data types.\n"
            "- The **business** definition uses a three-pronged threshold test (revenue, volume, "
            "or revenue-from-data) matching the CPRA approach.\n"
            "- I added **de-identified data** and **service provider** definitions that aren't "
            "in the original CCPA but are critical for the obligations section.\n\n"
            "For AI profiling, I'd recommend adding definitions for 'automated decision-making' "
            "and 'profiling' in the next revision — these will be important anchors for the "
            "Business Obligations section. Want me to expand the definitions now, or move on "
            "to drafting Consumer Rights?"
        ),
    },
]


async def seed() -> None:
    """Create the demo workspace and all related data."""

    async with async_session_factory() as session:
        # ------------------------------------------------------------------
        # Idempotency check
        # ------------------------------------------------------------------
        existing = (
            await session.execute(
                select(PolicyWorkspace).where(PolicyWorkspace.title == WORKSPACE_TITLE)
            )
        ).scalar_one_or_none()

        if existing is not None:
            print(f"[skip] Workspace '{WORKSPACE_TITLE}' already exists (id={existing.id})")
            return

        # ------------------------------------------------------------------
        # 1. Create workspace
        # ------------------------------------------------------------------
        workspace_id = _id()
        workspace = PolicyWorkspace(
            id=workspace_id,
            client_id=DEMO_CLIENT_ID,
            title=WORKSPACE_TITLE,
            target_jurisdiction_id="us-ca",
            drafting_template="standard-act",
            goal_prompt=(
                "Draft a comprehensive consumer data privacy act for California that "
                "matches or exceeds CCPA/CPRA protections, with particular attention to "
                "emerging technology and AI-driven data processing."
            ),
            status="drafting",
        )
        session.add(workspace)
        print(f"[+] Created workspace: {WORKSPACE_TITLE} (id={workspace_id})")

        # ------------------------------------------------------------------
        # 2. Find precedent bills
        # ------------------------------------------------------------------
        privacy_bills = (
            (
                await session.execute(
                    select(Bill)
                    .where(Bill.title.ilike("%privacy%") | Bill.title.ilike("%data%"))
                    .limit(4)
                )
            )
            .scalars()
            .all()
        )

        if not privacy_bills:
            print("[!] No privacy-related bills found, falling back to any bills")
            privacy_bills = (await session.execute(select(Bill).limit(4))).scalars().all()

        if not privacy_bills:
            print("[!] No bills found in database — skipping precedents")
        else:
            for idx, bill in enumerate(privacy_bills):
                precedent = PolicyWorkspacePrecedent(
                    workspace_id=workspace_id,
                    bill_id=bill.id,
                    position=idx,
                )
                session.add(precedent)
                print(f"  [+] Added precedent: {bill.identifier} — {bill.title[:60]}")

        # ------------------------------------------------------------------
        # 3. Create outline sections
        # ------------------------------------------------------------------
        sections_spec = [
            {
                "section_key": "definitions",
                "heading": "Definitions",
                "purpose": "Establish core terminology used throughout the act.",
                "position": 0,
                "content_markdown": DEFINITIONS_V2,
                "status": "drafted",
            },
            {
                "section_key": "scope",
                "heading": "Scope & Applicability",
                "purpose": ("Define jurisdictional reach, covered entities, and exemptions."),
                "position": 1,
                "content_markdown": SCOPE_CONTENT,
                "status": "outlined",
            },
            {
                "section_key": "consumer-rights",
                "heading": "Consumer Rights",
                "purpose": "Enumerate the rights granted to consumers under this act.",
                "position": 2,
                "content_markdown": CONSUMER_RIGHTS_V2,
                "status": "drafted",
            },
            {
                "section_key": "business-obligations",
                "heading": "Business Obligations",
                "purpose": (
                    "Specify affirmative obligations for businesses that process personal data."
                ),
                "position": 3,
                "content_markdown": OBLIGATIONS_CONTENT,
                "status": "outlined",
            },
            {
                "section_key": "enforcement",
                "heading": "Enforcement & Remedies",
                "purpose": (
                    "Establish enforcement authority, penalties, and private rights of action."
                ),
                "position": 4,
                "content_markdown": ENFORCEMENT_CONTENT,
                "status": "outlined",
            },
        ]

        section_objects: dict[str, PolicySection] = {}
        for spec in sections_spec:
            section_id = _id()
            section = PolicySection(id=section_id, workspace_id=workspace_id, **spec)
            session.add(section)
            section_objects[spec["section_key"]] = section

        print(f"  [+] Created {len(sections_spec)} outline sections")

        # ------------------------------------------------------------------
        # 4. Create generations and revisions for drafted sections
        # ------------------------------------------------------------------
        # --- Definitions: 2 generations, 2 revisions ---
        def_section = section_objects["definitions"]

        def_gen1_id = _id()
        def_gen1 = PolicyGeneration(
            id=def_gen1_id,
            workspace_id=workspace_id,
            section_id=def_section.id,
            action_type="draft_section",
            instruction_text="Draft the definitions section for the data privacy act.",
            output_payload={"content_markdown": DEFINITIONS_V1},
            provenance={
                "model": "claude-sonnet-4-20250514",
                "prompt_version": "composer-v1.5",
                "latency_ms": 3420,
            },
        )
        session.add(def_gen1)

        def_rev1_id = _id()
        def_rev1 = PolicySectionRevision(
            id=def_rev1_id,
            section_id=def_section.id,
            generation_id=def_gen1_id,
            change_source="ai_generation",
            content_markdown=DEFINITIONS_V1,
        )
        session.add(def_rev1)

        # Mark gen1 as accepted
        def_gen1.accepted_revision_id = def_rev1_id

        def_gen2_id = _id()
        def_gen2 = PolicyGeneration(
            id=def_gen2_id,
            workspace_id=workspace_id,
            section_id=def_section.id,
            action_type="revise_section",
            instruction_text=(
                "Expand the definitions to be more comprehensive. Add thresholds to the "
                "business definition, expand sensitive data categories, and add definitions "
                "for de-identified data and service providers."
            ),
            output_payload={"content_markdown": DEFINITIONS_V2},
            provenance={
                "model": "claude-sonnet-4-20250514",
                "prompt_version": "composer-v1.5",
                "latency_ms": 4810,
            },
        )
        session.add(def_gen2)

        def_rev2_id = _id()
        def_rev2 = PolicySectionRevision(
            id=def_rev2_id,
            section_id=def_section.id,
            generation_id=def_gen2_id,
            change_source="ai_generation",
            content_markdown=DEFINITIONS_V2,
        )
        session.add(def_rev2)

        def_gen2.accepted_revision_id = def_rev2_id

        print("  [+] Created 2 generations + 2 revisions for Definitions")

        # --- Consumer Rights: 2 generations, 2 revisions ---
        cr_section = section_objects["consumer-rights"]

        cr_gen1_id = _id()
        cr_gen1 = PolicyGeneration(
            id=cr_gen1_id,
            workspace_id=workspace_id,
            section_id=cr_section.id,
            action_type="draft_section",
            instruction_text="Draft the consumer rights section based on CCPA precedent.",
            output_payload={"content_markdown": CONSUMER_RIGHTS_V1},
            provenance={
                "model": "claude-sonnet-4-20250514",
                "prompt_version": "composer-v1.5",
                "latency_ms": 2950,
            },
        )
        session.add(cr_gen1)

        cr_rev1_id = _id()
        cr_rev1 = PolicySectionRevision(
            id=cr_rev1_id,
            section_id=cr_section.id,
            generation_id=cr_gen1_id,
            change_source="ai_generation",
            content_markdown=CONSUMER_RIGHTS_V1,
        )
        session.add(cr_rev1)

        cr_gen1.accepted_revision_id = cr_rev1_id

        cr_gen2_id = _id()
        cr_gen2 = PolicyGeneration(
            id=cr_gen2_id,
            workspace_id=workspace_id,
            section_id=cr_section.id,
            action_type="revise_section",
            instruction_text=(
                "Expand consumer rights to include right to correct, right to limit "
                "sensitive data use, and right to data portability. Add detail on the "
                "opt-out mechanism including GPC signal requirement."
            ),
            output_payload={"content_markdown": CONSUMER_RIGHTS_V2},
            provenance={
                "model": "claude-sonnet-4-20250514",
                "prompt_version": "composer-v1.5",
                "latency_ms": 3780,
            },
        )
        session.add(cr_gen2)

        cr_rev2_id = _id()
        cr_rev2 = PolicySectionRevision(
            id=cr_rev2_id,
            section_id=cr_section.id,
            generation_id=cr_gen2_id,
            change_source="ai_generation",
            content_markdown=CONSUMER_RIGHTS_V2,
        )
        session.add(cr_rev2)

        cr_gen2.accepted_revision_id = cr_rev2_id

        print("  [+] Created 2 generations + 2 revisions for Consumer Rights")

        # ------------------------------------------------------------------
        # 5. Create workspace conversation
        # ------------------------------------------------------------------
        convo_id = _id()
        convo = Conversation(
            id=convo_id,
            client_id=DEMO_CLIENT_ID,
            workspace_id=workspace_id,
            title="Data Privacy Act — Research & Planning",
        )
        session.add(convo)

        for msg_spec in CONVERSATION_MESSAGES:
            msg = ConversationMessage(
                conversation_id=convo_id,
                role=msg_spec["role"],
                content=msg_spec["content"],
            )
            session.add(msg)

        print(f"  [+] Created conversation with {len(CONVERSATION_MESSAGES)} messages")

        # ------------------------------------------------------------------
        # Commit everything
        # ------------------------------------------------------------------
        await session.commit()
        print("\n[done] Demo workspace seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
