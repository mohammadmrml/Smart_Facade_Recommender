# Smart Facade Recommender
AI-Assisted Facade Optimization for Early-Stage Architectural Design

## Overview

Smart Facade Recommender is an AI-driven design support system developed for early-stage architectural facade optimization. The project combines parametric modeling, machine learning, and environmental performance analysis to assist architects in making faster and more informed facade design decisions.

The system predicts facade performance metrics such as daylight availability, solar exposure, and energy-related indicators without requiring time-consuming simulations during conceptual design phases.

The workflow integrates:
- Rhino + Grasshopper parametric modeling
- Machine Learning surrogate models
- Environmental performance datasets
- Interactive design feedback

---

## Research Motivation

Facade design decisions made during early design stages strongly affect:
- Energy performance
- Daylight quality
- Thermal comfort
- Solar gain
- Building sustainability

Traditional simulation workflows are often slow and computationally expensive, limiting iterative exploration during conceptual design.

This project addresses the problem by introducing a machine learning surrogate model capable of generating near-instant performance predictions.

---

## Features

- Parametric facade configuration
- Real-time ML-based performance prediction
- Rhino/Grasshopper integration
- Interactive design exploration
- Window-to-Wall Ratio (WWR) optimization
- Support for adaptive facade strategies
- Rapid evaluation of multiple facade alternatives

---

## System Workflow

1. Architect modifies facade parameters in Grasshopper
2. Parameters are extracted and sent to the ML engine
3. Trained surrogate model predicts performance indicators
4. Results are returned instantly to the interface
5. User iterates and optimizes the facade design

---

## Input Parameters

The current model uses parameters such as:

- Orientation
- Window-to-Wall Ratio (WWR)
- Panel Type
- Panel Rotation
- Panel Size
- Porosity
- Glass Transparency

---

## Technologies Used

### Design Tools
- Rhino 3D
- Grasshopper

### Programming
- Python

### Machine Learning
- Scikit-learn
- Pandas
- NumPy

### Visualization
- Streamlit

---

## Repository Structure

```text
app/                → ML application and prediction engine
rhino_plugin/       → Rhino/Grasshopper integration
dataset/            → Training datasets and documentation
docs/               → Diagrams, screenshots, and reports
models/             → Trained ML model information
examples/           → Sample inputs and outputs
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/smart-facade-recommender.git
cd smart-facade-recommender
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app/app.py
```

---

## Future Development

Future directions include:

- Multi-objective optimization
- Integration with EnergyPlus and Radiance
- Reinforcement learning for facade adaptation
- Real-time environmental feedback
- Generative AI-assisted facade creation
- BIM integration workflows

---

## Academic Context

This project is developed as part of a Master's Thesis at:
Politecnico di Milano

Research focus:
- Sustainable Architecture
- Energy-Efficient Building Design
- AI-Assisted Computational Design
- Adaptive Facade Systems

---

## Authors

Mohammadreza [Your Last Name]  
Politecnico di Milano

---

## License

MIT License
