# 🎧 AWS Event-Driven AI Audiobook Generator (Dual-Engine)

An enterprise-grade, serverless, and event-driven pipeline that converts digital PDF books into natural, high-quality audiobooks. By leveraging a **Hybrid Voice Architecture**, this system dynamically toggles between **Amazon Polly Neural/Standard** (for cost-free bulk book synthesis) and **ElevenLabs API** (for ultra-realistic voice cloning).

The entire infrastructure is defined as code (IaC) using **Terraform**, strictly adhering to AWS security, reliability, and FinOps best practices.

---

## 🏗️ Architecture Design

![Audiobook Generator Architecture](/img/arquitectura_serveles_audiobook.png)

```mermaid
graph LR
    %% Definición de Estilos y Colores para Dark Mode
    classDef aws fill:#232F3E,stroke:#FF9900,stroke-width:2px,color:#fff;
    classDef external fill:#1F1F1F,stroke:#00A4EF,stroke-width:2px,color:#fff;
    classDef group fill:#111,stroke-width:1px,stroke-dasharray: 5 5,color:#fff;

    %% Elementos de la Arquitectura
    subgraph Ingestion ["1. INGESTION & ORCHESTRATION"]
        S3In["Amazon S3: PDF Ingest"]:::aws
        LambdaA["Lambda A: Splitter <br> pypdf"]:::aws
        DB["Amazon DynamoDB: State Table"]:::aws
    end

    subgraph Messaging ["2. MESSAGING & BUFFERING"]
        SQS["Amazon SQS: Main Queue"]:::aws
        DLQ["Amazon SQS: DLQ"]:::aws
    end

    subgraph Processing ["3. HYBRID PROCESSING"]
        LambdaB["Lambda B: Processor <br> Hybrid Engine"]:::aws
        SSM["SSM Parameter Store"]:::aws
        Polly["Amazon Polly: Neural"]:::aws
        Eleven["ElevenLabs API"]:::external
    end

    subgraph Storage ["4. STORAGE & CONSOLIDATION"]
        S3Out["Amazon S3: MP3 Outputs"]:::aws
        LambdaC["Lambda C: Consolidator"]:::aws
        SNS["Amazon SNS: Notifications"]:::aws
    end

    %% Relaciones y Flujo
    S3In -- "s3:ObjectCreated" --> LambdaA
    LambdaA -- "Registers Book State" --> DB
    LambdaA -- "Sends Page Chunks" --> SQS
    SQS -- "Redrive / Fallbacks" --> DLQ
    SQS -- "Triggers" --> LambdaB
    SSM -- "Fetches API Key" --> LambdaB
    
    LambdaB -- "MODE: POLLY" --> Polly
    LambdaB -- "MODE: ELEVENLABS" --> Eleven
    
    Polly -- "Saves page MP3" --> S3Out
    Eleven -- "Saves page MP3" --> S3Out
    
    S3Out -- "s3:ObjectCreated" --> LambdaC
    LambdaC -- "Increments ProcessedPages" --> DB
    LambdaC -- "Saves Audiobook.mp3" --> S3Out
    LambdaC -- "Publishes notification" --> SNS

    %% Aplicar clases
    style Ingestion stroke:#FF9900,fill:#0d0d0d
    style Messaging stroke:#EC407A,fill:#0d0d0d
    style Processing stroke:#FFEB3B,fill:#0d0d0d
    style Storage stroke:#4CAF50,fill:#0d0d0d

 ``` 


### ⚙️ How the Pipeline Works:
1. **Ingestion & Orchestration:** A digital PDF is uploaded to the private S3 Input bucket. S3 automatically triggers **Lambda A (Splitter)**.
2. **Fan-Out Process:** Lambda A downloads the PDF, registers metadata in **DynamoDB** (BookID, TotalPages, ProcessedPages: 0, Status: PROCESSING), extracts text page-by-page using Python's native `pypdf` library, and sends each page as an individual SQS message with numeric zero-padding (`page_001`, `page_002`) to preserve sequence.
3. **Queue & Buffer (SQS):** SQS acts as a message broker. It handles concurrency, isolates the long-running AI processes, and buffers failures using a custom **Dead Letter Queue (DLQ)** with a 360-second Visibility Timeout.
4. **Hybrid Processing (Lambda B):** SQS triggers concurrent instances of **Lambda B (Processor)**. Based on the `SYNTHESIS_ENGINE` environment variable, it executes one of two paths:
   - **Mode `POLLY` (Default/Bulk):** Asynchronously triggers **Amazon Polly Neural/Standard** (`StartSpeechSynthesisTask`) using the high-quality Brazilian voice 'Camila' to synthesize full books with zero/low cost.
   - **Mode `ELEVENLABS` (Premium/Cloning):** Securely fetches the API Key from **AWS SSM Parameter Store**, invokes the **ElevenLabs API** using Python's zero-dependency native library `urllib` to clone specific voices (e.g., Antoni or Pablo Marçal), and streams the binary MP3 bytes directly back to S3.
5. **Storage:** The generated page-by-page MP3 files are saved to the output S3 bucket under the book's specific subfolder.

---

## 🛠️ Tech Stack & Keywords

- **Cloud Platform:** AWS (S3, SQS, DynamoDB, Lambda, Bedrock, Polly, SSM Parameter Store, IAM)
- **Multi-Cloud Integration:** ElevenLabs API (Voice Cloning / Neural TTS)
- **Infrastructure as Code (IaC):** Terraform (v1.5.0+, AWS Provider v5.0)
- **Programming Language:** Python 3.12 (Boto3, PyPDF, Urllib native)
- **Architectural Patterns:** Event-Driven Architecture (EDA), Fan-Out, Hybrid Cloud.

---

## 🔒 Security & Best Practices (DevOps Alignment)

- **Secure Secrets Management:** The ElevenLabs API Key is **NEVER** hardcoded in Python or pushed to GitHub. It is securely stored as a `SecureString` in **AWS Systems Manager (SSM) Parameter Store**, encrypted with KMS, and accessed via granular `ssm:GetParameter` permissions.
- **Principle of Least Privilege (PoLP):** No `*FullAccess` policies are used. Every Lambda has a dedicated IAM role restricted to specific resource ARNs (e.g., Lambda B is only allowed to perform `s3:PutObject` on the output S3 path and read the single designated SSM secret).
- **Decoupled Serverless Scaling:** Using SQS visibility timeouts prevents API Gateway and Lambda timeouts (15m limit), allowing 100+ page books to scale and process concurrently without failures.
- **Automated Builds:** Terraform's `source_code_hash` automatically detects local Python modifications in the `src/` directory, rebuilding and deploying the `.zip` packages seamlessly.

---

## 💰 FinOps: Cost Optimization

- **Dual-Engine Toggle:** The environment variable `SYNTHESIS_ENGINE` can be toggled to `"POLLY"` for bulk books (utilizing AWS Polly's 1 Million free Neural characters/month and 5 Million free Standard characters/month) or `"ELEVENLABS"` for short premium cloning.
- **On-Demand Billing:** All resources (DynamoDB, SQS, Lambdas) are configured to run purely serverless on on-demand tiering, costing $0.00 USD when idle.
- **S3 Lifecycle Rules:** (Roadmap) Automatic clean-up rules configured via Terraform to purge temporary page chunks after 24 hours.

---

## 🚀 How to Deploy Locally

### Prerequisites
1. Installed **Terraform (>= 1.5.0)** and **Python 3.12**.
2. AWS CLI configured with active credentials (`aws configure`).

### Deployment Steps
1. **Clone the repository:**
   ```bash
   git clone https://github.com/DevDan7/aws-serverless-audiobook-pipeline.git
   cd aws-serverless-audiobook-pipeline
   ```

2. **Package Lambda Splitter dependencies locally:**
   ```bash
   cd src/lambda_splitter
   pip install pypdf -t .
   cd ../..
   ```

3. **Deploy with Terraform (Pass your sensitive API Key securely):**
   ```bash
   terraform init
   terraform plan
   terraform apply -var="elevenlabs_api_key=YOUR_ELEVENLABS_API_KEY" --auto-approve
   ```

4. **Test the pipeline:**
   Set `SYNTHESIS_ENGINE` to `"POLLY"` in `lambda.tf` and run `terraform apply`. Upload any PDF book in Portuguese to your input S3 bucket. Monitor progress via **DynamoDB** and **CloudWatch**, then listen to your generated audiolibro pages in the output S3 bucket!

---

## 🗺️ Roadmap & Next Steps (Phase 3)

- [ ] **AI-driven Page Curation (Lambda A):** Integrate Bedrock as an agentic tool to automatically filter out structural pages (copyright, blank exercise pages, indexes) before processing.
- [ ] **Consolidation Engine (Lambda C):** Build an S3-triggered Lambda that monitors database state, dynamically concatenates individual page-by-page MP3s in correct order, and publishes a "Ready" notification via **Amazon SNS**.

## 👨‍💻 Autor
**Daniel Villegas**
* Cloud Engineer | AWS Certified
* [LinkedIn] https://www.linkedin.com/in/vdaniel07/