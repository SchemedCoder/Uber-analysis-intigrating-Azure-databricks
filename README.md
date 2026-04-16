# Uber-analysis-intigrating-Azure-databricks

# 🚀 Uber Real-Time Demand & Surge Pricing Platform

## Overview
Production-grade real-time data platform simulating Uber’s ride demand and surge pricing system.

## Features
- Kafka-based real-time streaming
- PySpark processing
- Surge pricing engine
- Multi-city support (5 cities)
- Data reconstruction (batch)
- Star schema data warehouse
- Advanced SQL (joins, window functions, procedures)
- ML demand prediction
- Kafka lag monitoring
- CI/CD pipeline

## Tech Stack
Python, Apache Kafka, PySpark, Azure Data Factory, Azure Databricks, Azure Data Lake, Azure Synapse, Power BI

## Architecture
Kafka → Databricks → Data Lake → Synapse → Power BI

## Run Locally
docker-compose up -d

python kafka/producer.py  
python streaming/stream_processor.py  

## Run Tests
pytest tests/

## Azure Integration
- ADF for orchestration  
- Databricks for streaming  
- Data Lake storage  
- Synapse warehouse  
- Power BI dashboard  

## Resume Impact
Built a real-time data platform with streaming ETL, data warehousing, ML prediction, and BI analytics.
