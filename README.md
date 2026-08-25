# Uber Real-Time Demand & Surge Pricing Platform

## Overview
Production-grade real-time data platform implementing an event-driven architecture for ride demand tracking and surge pricing calculation.

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

## Environment Variables
Create a `.env` file in the root directory using the provided `.env.example` file to configure Azure credentials.

## Run Locally
docker-compose up -d

python local_run.py

## Run Tests
pytest tests/

## Azure Integration
- ADF for orchestration  
- Databricks for streaming  
- Data Lake storage  
- Synapse warehouse  
- Power BI dashboard
