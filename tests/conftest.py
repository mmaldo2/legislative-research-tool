"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_bill_text():
    return """\
AN ACT relating to data privacy.

Section 1. Short Title.
This Act may be cited as the "Consumer Data Privacy Act of 2025."

Section 2. Definitions.
(a) "Personal data" means any information that is linked or reasonably
linkable to an identified or identifiable individual.
(b) "Controller" means a natural or legal person that determines the
purposes and means of the processing of personal data.
(c) "Consumer" means a natural person who is a resident of the State.

Section 3. Consumer Rights.
(a) A consumer shall have the right to:
    (1) confirm whether or not a controller is processing the consumer's
        personal data;
    (2) access the consumer's personal data;
    (3) correct inaccuracies in the consumer's personal data;
    (4) delete personal data provided by, or obtained about, the consumer;
    (5) obtain a copy of the consumer's personal data in a portable format.

Section 4. Controller Obligations.
(a) A controller shall provide consumers with a reasonably accessible,
clear, and meaningful privacy notice.
(b) A controller shall limit the collection of personal data to what is
adequate, relevant, and reasonably necessary.

Section 5. Enforcement.
The Attorney General shall have exclusive authority to enforce the
provisions of this Act. A violation constitutes an unfair trade practice.

Section 6. Effective Date.
This Act shall take effect on January 1, 2026.
"""


@pytest.fixture
def sample_bill_xml():
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<billStatus>
  <bill>
    <billNumber>1234</billNumber>
    <billType>hr</billType>
    <title>Consumer Data Privacy Act of 2025</title>
    <congress>119</congress>
    <legislativeSubjects>
      <item><name>Right of privacy</name></item>
      <item><name>Consumer protection</name></item>
    </legislativeSubjects>
    <actions>
      <item>
        <actionDate>2025-01-15</actionDate>
        <text>Introduced in House</text>
      </item>
      <item>
        <actionDate>2025-02-10</actionDate>
        <text>Referred to the Committee on Energy and Commerce</text>
      </item>
    </actions>
  </bill>
</billStatus>
"""
