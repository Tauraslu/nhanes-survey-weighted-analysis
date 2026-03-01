# NHANES 2011–2012 Survey-Weighted Hypertension Analysis

## Overview

This project demonstrates a full clinical data workflow using NHANES 2011–2012 data, integrating:

- SQL-based dataset construction
- Python ETL pipeline
- Complex survey design analysis (NHANES sampling structure)
- Survey-weighted logistic regression
- Publication-style visualization (forest plot)

The objective was to evaluate independent risk factors associated with hypertension among U.S. adults.

---

## Data Source

- National Health and Nutrition Examination Survey (NHANES) 2011–2012
- Publicly available data from CDC

Hypertension was defined as:
- SBP ≥ 140 mmHg, OR
- DBP ≥ 90 mmHg, OR
- Current use of antihypertensive medication

---

## Methods

### Data Engineering
- Python (`pandas`, `SQLAlchemy`) used to ingest XPT files
- MySQL used to construct analysis dataset
- QC checks performed (missingness, out-of-range values, duplicates)

### Statistical Analysis
- Survey design: stratified, cluster sampling
- Weights: WTMEC2YR
- R package: `survey`
- Model: survey-weighted logistic regression

Outcome:
- Hypertension (binary)

Covariates:
- BMI
- Age
- Sex
- Smoking status
- Diabetes status

---

## Key Findings

- Diabetes strongly associated with hypertension (OR 2.29, 95% CI 1.56–3.37)
- BMI and age independently associated with increased odds
- Sex and smoking were not statistically significant after adjustment

---

## Visualization

A publication-style forest plot was generated to display adjusted odds ratios:

![Forest Plot](output/forest_plot_htn.png)

---

## Project Structure
nhanes_sql/
├── data.py # Python ETL + SQL pipeline
├── Nhanes_personal_project.Rmd
├── Nhanes_personal_project.pdf
├── output/
│ ├── analysis_dataset.csv
│ ├── qc_summary.csv
│ ├── forest_plot_htn.png
│ ├── regression_table.png


---

## Reproducibility

- Python for data construction
- R for survey-weighted modeling
- Fully reproducible workflow from raw NHANES files

---

## Skills Demonstrated

- SQL data construction
- Python ETL pipeline
- Complex survey analysis
- Logistic regression modeling
- Clinical result interpretation
- Publication-quality visualization