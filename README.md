# 🌐 CloudShop Lite — AI-Augmented Cloud-Native Microservices Platform

CloudShop Lite is a fully cloud-native microservices platform deployed on **AWS EKS**, enhanced with AI-driven automation using a dual-brain architecture:
1. **In-cluster AI-Ops FastAPI bot**
2. **Host-level MCP (Model Context Protocol) agent**

The system modernizes a simple Docker example into a production-style distributed application with microservices, Kubernetes orchestration, Nginx gateway routing, RDS PostgreSQL database, CloudWatch observability, and AI-powered self-healing operations.

---

# 🚀 Features

### 🧩 Microservices
- Users Service (Flask)
- Catalog Service (Flask)
- Orders Service (Flask + PostgreSQL + RDS)
- AI-Ops Bot (FastAPI in Kubernetes)
- Nginx Reverse Proxy
- React + Vite Frontend Dashboard

### ☁ AWS Infrastructure
- EKS Kubernetes cluster  
- RDS PostgreSQL instance  
- ELB load balancer  
- CloudWatch log groups  

### 🤖 AI-Ops Automation
- CloudWatch error summary  
- Top endpoint analysis  
- Pod status  
- Deployment restart  
- Deployment scaling  
- Self-healing playbooks  

### 🧠 MCP Host-Level Agent
- Reads Kubernetes YAML files  
- Runs kubectl commands  
- Reads system logs  
- Validates configurations  
- Allows Claude/OpenAI to operate like an SRE assistant  

---

# 🏗 Architecture Diagram

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/7270ecc3-3d4b-4116-8753-835415a85aaa" />


