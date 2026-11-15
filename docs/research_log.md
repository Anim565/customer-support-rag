
# Research and Development Log

## Entry 001 — 15 November 2026

### Activity
Establishment of a new development environment and version-control repository.

### Objective
Create a reproducible development environment for implementing and evaluating the proposed customer-support framework.

### Activities Completed
- Verified Python 3.12.10.
- Created the project directory at C:\Projects\customer-support-rag.
- Created and activated a Python virtual environment.
- Initialized a Git repository using the main branch.
- Created a README describing the research project.
- Configured .gitignore.
- Created the first Git commit.
- Connected the local repository to GitHub.

### Evidence
Initial Git commit: a4e80fa.

GitHub repository:
https://github.com/Anim565/customer-support-rag

### Previous Research
Six website-investigation Python scripts were identified in the previous dkl-rag-capstone project.

Their contents and experimental findings are pending review.

### Next Activity
Review preliminary website investigations and document the data acquisition methodology.


### Research Log Entry 002 — WhatsApp Parser Development

**Date:** 15 November 2026

**Activity:** Development and preliminary validation of a modular WhatsApp message parser.

**Objective:** To establish a reproducible preprocessing component capable of extracting structured message information from exported WhatsApp conversations.

**Implementation:**

- Developed a Python function for extracting message dates, times, sender identifiers and message content.
- Implemented support for selected Android and iPhone WhatsApp export formats.
- Added multiline message reconstruction.
- Identified and corrected a defect in which timestamped system records were incorrectly appended to preceding customer messages.
- Introduced a preliminary audit function to count recognized user messages and other timestamped records.
- Implemented automated unit tests using pytest.

**Results:** Six automated tests passed using synthetic WhatsApp examples.

**Limitations:** The parser currently supports a restricted set of timestamp formats. System events are not yet explicitly classified, and the audit does not provide detailed exclusion reasons. The implementation has not yet been validated against the complete historical WhatsApp dataset.

**Next Steps:** Expand record classification, strengthen parsing diagnostics, test additional WhatsApp export formats and compare the improved parser with the original anonymization notebook.