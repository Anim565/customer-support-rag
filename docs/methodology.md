
# CHAPTER THREE: RESEARCH METHODOLOGY

## 3.1 Introduction

This chapter describes the methodological approach proposed for the development and evaluation of a Retrieval-Augmented Customer Support Framework with Intelligent Escalation, using Dr. Kalebi Labs (DKL) as a diagnostic laboratory case study.

The methodology covers the research design, data sources, data acquisition and preprocessing, information retrieval, retrieval-augmented response generation, supervised escalation classification, system integration and evaluation.

The study will emphasize reproducibility, data protection, systematic model comparison and evidence-based technical decisions.

## 3.2 Research Design

The study will adopt an applied, quantitative, design-and-evaluation research approach within a diagnostic laboratory case-study setting.

The applied component addresses the practical challenge of responding to customer enquiries using organizational information while identifying requests that require human intervention.

The design component involves developing an integrated framework combining semantic information retrieval, retrieval-augmented generation and supervised machine learning for escalation classification.

The quantitative evaluation component will assess the performance of individual system components and the integrated framework using predefined metrics and representative test enquiries.

Dr. Kalebi Labs will serve as the case-study organization, providing the operational context for investigating customer-support enquiries, laboratory catalogue information and escalation requirements.

The study will distinguish between questions that can be answered using authorized organizational information and requests requiring human intervention, including case-specific enquiries, operational actions and situations where the available evidence is insufficient.

The research will compare alternative retrieval and escalation approaches to establish whether the proposed framework provides measurable improvements over defined baseline methods.

## 3.3 Methodological Framework

The proposed research will follow these stages:

1. Preliminary investigation of the laboratory website and available information sources.
2. Acquisition and validation of laboratory catalogue data.
3. Preparation and annotation of representative customer enquiries.
4. Development and evaluation of information retrieval methods.
5. Development of a retrieval-augmented response generation component.
6. Development and comparison of escalation classification models.
7. Integration of retrieval, generation and escalation components.
8. End-to-end evaluation, error analysis and prototype deployment.

The detailed procedures, experimental configurations and findings will be documented as implementation progresses.


## 3.4 Preliminary Data Acquisition Investigation

A preliminary technical investigation was undertaken to examine how laboratory test information could be acquired from the publicly accessible Dr. Kalebi Labs website.

Historical Python scripts were developed to investigate website structure, JavaScript behaviour, catalogue navigation, search functionality and browser network responses.

One historical implementation used Playwright to observe the network responses generated when the laboratory catalogue was loaded. The script targeted a structured JSON response and included procedures for extracting laboratory test attributes, standardizing text, constructing evidence documents and assessing data completeness.

The historical scripts have been preserved as research evidence. Their execution outcomes and compatibility with the current website will require verification before being reported as reproducible experimental results.

## 3.5 Data Quality and Evidence Sufficiency

The study will assess catalogue data quality using measures of field completeness, record identity, duplication, consistency and suitability for answering customer enquiries.

Field completeness will be calculated as the proportion of records containing a non-empty value for a specified attribute.

However, field completeness alone will not be treated as evidence of accuracy or sufficiency.

Evidence sufficiency will be evaluated in relation to the information required by each customer enquiry. For example, a record containing a test name and turnaround time may be sufficient for a turnaround-time enquiry but insufficient for a question concerning specimen collection instructions.

The proposed framework will distinguish between missing information, unsupported conclusions and enquiries requiring operational or clinical intervention.

The relationship between retrieved evidence and escalation decisions will be evaluated during system development.
