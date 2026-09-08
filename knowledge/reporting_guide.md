# Brainwave reporting guide

## Available reports and questions
Brainwave supports submitted-story counts, total submitted-story revenue, and submission counts grouped by market. Example questions: "How many EMIA stories were submitted in FY26?", "What is EMIA revenue in FY26?", and "Show submissions by market this year". These numerical answers are calculated from the database, not from this document.

## Data source and limitations
The local prototype initializes an empty database with sample business stories. These are demonstration records, not verified production results. A story has a title, market, category, submission date, status, submitter, and estimated revenue. The current reports filter on submission date and include only Submitted records.

## Market filter
Supported markets are EMIA, APAC, AMER, and LATAM. Selecting a market in the app takes precedence over a market named in the question. All markets applies no explicit selection; a market mentioned in the question can still filter the report.

## Missing policies and historical changes
The knowledge base does not contain employee leave policies, expense reimbursement rules, policy approval histories, or earlier versions of business definitions. Those questions require an authoritative document before the app can answer them. Do not infer company policies from example questions.
