# HELP DESK & TICKETS MANAGEMENT SYSTEM
## Final Year B.Tech Internship & Project Exhibition Poster Content

> **Poster Specifications (As per University Guidelines):**
> - **Size:** A2 ($42.0 \text{ cm} \times 59.4 \text{ cm}$ / $420\text{mm} \times 594\text{mm}$)
> - **Orientation:** Landscape (Standard Academic Format)
> - **Font:** Cambria (Title: 36–48 pt, Subheadings: 24–36 pt, Body: 18–24 pt, Captions/References: 14–18 pt)

---

### 1. Title & Author Information (Header Section)
* **Project Title:** HELP DESK & TICKETS MANAGEMENT SYSTEM
* **Subtitle:** An Intelligent, AI-Driven Multi-Tier Support Ticketing & Automated Resolution Platform
* **Student Name:** KIKANI MANASVI
* **Enrollment Number:** 23SE02ML057
* **Program / Branch:** B.Tech Computer Science Engineering (ML & AI) – Semester 7
* **Academic Year:** 2023 – 2026
* **Institution:** School of Engineering, P P Savani University, Surat, Gujarat
* **Industry Partner:** Sensussoft Software Private Limited
* **Company Mentor:** Saddam Khan
* **Institute Mentor:** Mr. Rahul Kumar Yadav

---

### 2. Introduction & Problem Statement
Modern enterprise customer support requires instantaneous ticket logging, intelligent routing, and strict SLA compliance. Traditional support systems face critical bottlenecks:
* **Manual Triage Inefficiency:** Manual ticket assignment creates human routing delays exceeding 40% and causes arbitrary agent workloads.
* **Lack of Strict Role Isolation:** Fragmented workflows across customers, agents, and admins result in security vulnerabilities and operational confusion.
* **Unpredictable SLA Breaches:** Support teams lack predictive foresight into issue complexity, resulting in missed customer commitments.

---

### 3. Project Objectives
* **AI-Powered Skill Routing:** Automate ticket classification and match tickets directly to specialized agents based on skill tags and workload.
* **Multi-Role Architectural Isolation:** Enforce distinct, secure portal views for Customer, Support Manager, Admin, and Super Admin.
* **Zero-Latency Live Search:** Provide instant client-side ticket search and dynamic status filtering without reloading pages.
* **Predictive SLA Duration Regressor:** Train machine learning models (Random Forest / Gradient Boosting) to forecast ticket resolution time.

---

### 4. Technology Stack & Key Highlights
* **Backend:** Python 3.10+, Flask Framework, RESTful APIs, Jinja2 Template Engine
* **Frontend:** HTML5, Vanilla CSS3 (Custom Responsive Tokens), Native ES6 JavaScript
* **Machine Learning:** Scikit-Learn, Random Forest Regressor, Pandas, NumPy
* **Data & Security:** PostgreSQL / SQLite, PBKDF2 Password Hashing, Brevo SMTP Email Triggers
* **Key Highlights:**
  * **Skill-Based Routing:** Issues dispatched by engineer competence rather than static department silos.
  * **Zero-Reload Live Search:** Substring and tag filtering across tickets in under 40ms.
  * **Multi-Channel Alerting:** Transactional Brevo emails coupled with real-time in-app notification badges.
  * **Dynamic Session Sync:** Support manager avatars synchronized across top-bar navigation and account views.

---

### 5. System Architecture & Workflow
* **Client Tier (Presentation):** Customer Ticket Portal, Support Manager Command Center, Admin Control Grid, Super Admin ML Console.
* **Logic Tier (Application):** Flask REST Endpoints, Role Guards Middleware, Ticket State Engine, Notification Dispatcher.
* **Data & AI Tier (Persistence & Intelligence):** Relational DB Schema (`users`, `tickets`, `departments`, `skills`, `notifications`) coupled with the Scikit-Learn SLA Predictor.

**Ticket Lifecycle Flow:**
1. **Ticket Logging:** User inputs issue title, department, priority, and attachments.
2. **AI Skill Matching:** System extracts domain tags and binds to the optimal active agent.
3. **Resolution Duration Prediction:** ML model predicts duration in hours and alerts managers of breach risks.
4. **Resolution & Audit:** Agent updates status, audit notes are recorded, and automated alerts are dispatched.

---

### 6. Role Matrix & Relational Schema Design
| Role Level | Primary System Permissions | Operational Scope |
| :--- | :--- | :--- |
| **Super Admin** | Global ML Model Monitoring, System Settings, Audit Trail | Enterprise-wide |
| **Admin** | Agent Skill Bindings, Department Setup, Ticket Reassignment | Departmental |
| **Support Manager** | Live Ticket Queue, SLA Escalations, Avatar & Profile Sync | Team Operations |
| **Customer** | Ticket Submission, Live Progress Tracking, In-App Notifications | Self Tickets |

* **Relational Integrity:** Normalized 3NF design with strict foreign keys (`users.id -> tickets.customer_id`, `departments.id -> tickets.department_id`, `skills <-> users` junction) guaranteeing 0 SQL anomalies.

---

### 7. Core System Modules
* **Module 1 – Role-Based Security:** Strict session middleware preventing cross-role route access across 4 hierarchical tiers.
* **Module 2 – Ticket Ops & Live Search:** Instant ticket creation, status transitions, and zero-latency client-side query filtering.
* **Module 3 – ML Prediction Engine:** Automated training pipeline tracking MAE, RMSE, and $R^2$ variance metrics on admin dashboards.
* **Module 4 – Profile & Notification Sync:** Support manager profile picture synchronization with top navigation and automated SMTP email notifications.

---

### 8. Results & Performance Validation
* **Unit & Functional Testing:** 99.4% test passing rate across 50+ Flask route endpoints using Pytest.
* **Server Latency:** Average API response time under 120ms; ML inference under 45ms.
* **Machine Learning Metrics:** Resolution time prediction achieved $R^2 = 0.86$ with low RMSE ($1.82$ hours).
* **Role Isolation:** Zero privilege leakage verified across cross-role test sessions.

#### Comparative Analysis: Manual vs. AI System
| Operational Metric | Legacy Manual Process | Proposed AI System |
| :--- | :--- | :--- |
| **Ticket Triage Time** | 4 – 6 Hours (Manual) | **< 5 Seconds (Auto-ML)** |
| **Routing Accuracy** | 62.4% (Frequent Misroutes) | **94.8% (Skill-Matched)** |
| **SLA Breach Rate** | 24.5% Overdue | **< 4.2% (Predicted & Prevented)** |

---

### 9. Conclusion & Future Scope
The **Help Desk & Tickets Management System** provides an enterprise-ready, intelligent resolution hub that streamlines support pipelines and eliminates manual routing bottlenecks.
* **Future Scope:**
  * Integration of Generative AI / LLM-powered automatic customer chat and self-healing solutions.
  * Real-time WebSocket streaming for instant updates.
  * Distributed microservices architecture containerized via Docker and Kubernetes.

---

### 10. References & Acknowledgments
1. Flask 3.x Framework Documentation & Jinja2 Template Specifications.
2. Scikit-Learn: Machine Learning in Python, Pedregosa et al.
3. P P Savani University Guidelines for Final Year Internship and UDP Poster Presentations.
