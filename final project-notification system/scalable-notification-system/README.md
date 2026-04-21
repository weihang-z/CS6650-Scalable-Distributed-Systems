# Scalable Notification System

A **distributed notification platform** built for **Northeastern CS6650** (Scalable Systems). The goal is to practice patterns you see in real production systems: **decoupled ingestion**, **reliable messaging**, **horizontal scale**, and **observable behavior under load**—not just a CRUD API that “works on my laptop.”

## Why this project?

Notification traffic is bursty, multi-channel, and failure-prone (email APIs time out, mobile push tokens expire, third parties rate-limit you). A naive design—synchronous sends inside the HTTP request—**couples user-facing latency to downstream providers** and makes retries and ordering painful.

This project explores a **more scalable shape**:

1. **Accept quickly** — HTTP returns after persisting intent (and outbox state).
2. **Publish reliably** — **transactional outbox** moves work from the database to Kafka without “dual write” races.
3. **Process in parallel** — **Kafka** carries channel-specific work; **separate worker fleets** (email vs in-app) can scale and fail independently.
4. **Measure honestly** — **Locust** load tests (including runs from EC2) plus **Kafka consumer lag** and **CloudWatch** metrics to see where bottlenecks actually are (ingress DB pool vs broker backlog vs worker CPU).

---

## What it does (high level)

- **REST API (ingress)** — Clients `POST /notifications` to request delivery on one or more channels (e.g. email + in-app).
- **Routing** — A `notification.requested` style flow fans out to **per-channel topics** (e.g. email send vs in-app send).
- **Workers** — Channel-dedicated consumers call **mock providers** whose latency is configurable (used for isolation experiments).
- **Persistence** — **MySQL** (RDS in AWS) stores notifications, attempts, and **outbox** rows.
- **Infrastructure (AWS)** — **ALB → ECS (Fargate)** for ingress and workers, **ECR** for images, **RDS**, **Kafka on EC2** (lab-style broker), wired up with **Terraform** modules.

The Spring Boot app uses **`APP_ROLE`** (`ingress` vs `worker`) and **`CHANNEL`** (`EMAIL` vs `INAPP`) with **`@ConditionalOnProperty`** so the **same container image** can run different roles safely.

---

## Repository layout (this folder)

| Area | Purpose |
|------|--------|
| `src/main/java/...` | Domain model, application services, Kafka consumers, REST controllers |
| `src/main/resources/application-*.yml` | Local vs AWS profiles, Kafka, outbox, mock provider latency |
| `src/main/java/.../infrastructure/terraform/` | VPC, ALB, ECS ingress/workers, RDS, ECR, EC2 Kafka, security groups |
| `locust/` | Load-test scenarios (`locustfile.py`) |
| `experiment/` | Orchestration scripts for Experiments A/B/C (EC2 load gen, metrics, summaries) |
| `results/` | Generated CSV/JSON/Markdown from experiments (large; often gitignored locally) |

---

## Quick start (local)

Prerequisites: **Java 17**, **Maven**, local **MySQL** and **Kafka** (or Docker Compose if you maintain one), matching `application-local.yml`.

```bash
./mvnw test
./mvnw spring-boot:run -Dspring-boot.run.profiles=local
```

Typical local URL: `http://localhost:8080`.

For AWS-shaped settings, use profile **`aws`** and supply `DB_*`, `KAFKA_BOOTSTRAP_SERVERS`, `APP_ROLE`, `CHANNEL`, etc. (see `application-aws.yml` and your ECS task definition / Terraform outputs).

---

## Deployment (AWS, sketch)

1. Build/push image to **ECR** (e.g. Spring Boot buildpacks / Docker).
2. **`terraform apply`** from the Terraform root under `infrastructure/terraform/` (adjust `terraform.tfvars` for your account).
3. Ensure **Kafka topics** and **consumer groups** match what the app expects; partition counts affect parallelism under burst load.
4. Point Locust or clients at the **ALB DNS name**.

Exact ARNs and secrets belong in your tfvars / AWS console—not in this README.

---

## Load testing & experiments

Scripts under `experiment/` automate:

- **Experiment A** — Fixed EMAIL load while scaling **email worker** replicas; collects throughput, latency, lag, ECS CPU/memory.
- **Experiment B** — **Burst** EMAIL pattern (baseline → spike → recovery) with Kafka lag and “time to recover” style summaries.
- **Experiment C** — **Mixed channels** with **controlled mock latency** on email only, to reason about **isolation** between email and in-app paths.

Runners assume **AWS CLI**, **SSH** to a load-generator EC2, and access to Kafka for lag sampling—see each script’s constants / `os.getenv` overrides.

---

## How the project progressed (“activity over time”)

This work lives inside a **larger CS6650 Git monorepo** (`CS6650` at the course root). The **notification system** subtree has appeared in commit history as the course moved from early assignments toward the final project; the **full history of day-to-day edits** may include **local iterations** that are not yet committed—worth pushing regularly so the story is visible on GitHub.


### Milestones in the implementation (engineering narrative)

These map to how the codebase **grew in capability**, regardless of whether each step is one Git commit or many:

1. **Core Spring Boot service** — REST + persistence + Kafka basics.
2. **Transactional outbox** — Scheduled publisher to move `NEW` outbox rows to Kafka; later **batching**, **`FOR UPDATE SKIP LOCKED`**, and **indexes** to reduce DB contention.
3. **Role/channel split** — Same image, different beans via `APP_ROLE` / `CHANNEL` for **ingress vs workers** and **EMAIL vs INAPP**.
4. **Terraform on AWS** — Network, RDS, ALB, ECS services, ECR, EC2 Kafka, security groups; iterative fixes (ARM64, naming, execution roles, consumer group env vars for **correct lag measurement**).
5. **Experiment harness** — Python + Locust on EC2, CSV/JSON/Markdown summaries, burst and mixed-channel scenarios.
6. **Performance lessons** — e.g. ingress latency tied to **synchronous DB work** and **pool sizing** under load; Kafka lag sometimes staying at zero when the bottleneck is **upstream** of the broker.

### Issues, PRs, and tracking

This tree **does not include** a `.github/ISSUE_TEMPLATE` or similar—if you use GitHub for the course, consider:

- Opening **Issues** for “Kafka lag sampler wrong consumer group”, “outbox index missing”, “Experiment C attempt API returns empty”, etc.
- **Linking PRs** to those issues so reviewers see **intent → diff → verification** (Locust run artifact path in the PR description).

That gives you the “activity along the way” story the rubric asks for, in a place graders and teammates can click through.

---

## Tech stack

- **Java 17**, **Spring Boot 4.x**, **Spring Kafka**, **Spring Data JPA**
- **MySQL** (local / **AWS RDS**)
- **Apache Kafka** (Confluent images on **EC2** in the reference deployment)
- **AWS**: ECS Fargate, ALB, ECR, VPC, IAM, CloudWatch
- **Terraform**
- **Python 3** + **Locust** for load tests

---

## Author / course

Built for **CS6650 – Scalable Systems**, Northeastern University, as a **final project** exercise in scalable architecture, cloud deployment, and empirical evaluation.

---

## License

Course project—no license file is set by default. Add a `LICENSE` if you open-source the repo.
