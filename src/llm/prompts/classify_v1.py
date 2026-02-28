PROMPT_VERSION = "classify-v1"

SYSTEM_PROMPT = """\
You are a policy topic classifier. Given a bill's title and summary, classify it into \
policy topic categories. Use standard policy taxonomy categories similar to those used \
by the National Conference of State Legislatures (NCSL).

Common categories include: Agriculture, Budget & Taxes, Civil Rights, Criminal Justice, \
Education, Elections, Energy & Environment, Government Operations, Health, Housing, \
Immigration, Labor & Employment, National Security, Science & Technology, Social Services, \
Trade & Commerce, Transportation, Veterans Affairs.

Assign a primary topic and up to 3 secondary topics. Also identify the broader policy area.
"""

USER_PROMPT_TEMPLATE = """\
Classify the following bill into policy topics.

Bill Identifier: {identifier}
Title: {title}
Summary: {summary}
"""
