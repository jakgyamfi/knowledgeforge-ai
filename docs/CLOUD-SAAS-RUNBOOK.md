# Cloud Upgrade Runbook: Separate Private Libraries

This runbook describes how to evolve the current single-user application into a cloud-hosted, multi-user service where each user can access only their own recordings, transcripts, metadata, and search results. Billing is out of scope.

## Target architecture

```text
Phone / browser
      |
      v
HTTPS load balancer or reverse proxy
      |
      v
Stateless KnowledgeForge web/API containers
      |             |              |
      |             |              +--> Cognito/OIDC authentication
      |             +-----------------> PostgreSQL metadata and ownership
      +-------------------------------> S3 private audio/transcript objects
                         |
                         v
                    SQS job queue
                         |
                         v
                transcription workers
                         |
                         v
             CloudWatch logs, metrics, alarms
```

## Required invariants

- Every data row and object has an immutable `user_id` owner.
- Authorization is checked server-side for every read, update, download, search, and delete.
- Never accept `user_id` from request bodies; derive it from the validated identity token.
- S3 remains private. Downloads and uploads use short-lived presigned URLs or authenticated streaming.
- Workers receive internal object keys and job IDs, not public URLs.
- Search queries are always scoped by authenticated `user_id`.
- Logs never contain transcript text, audio content, access tokens, or presigned URLs.

## Phase 0: Preserve the local baseline

1. Tag the last verified local-only release.
2. Back up the private SQLite database, recordings, transcripts, and `.env` outside Git.
3. Record the current test and verification results.
4. Keep the local Docker Compose deployment as the rollback/reference environment.

Exit criterion: the tagged local release can be restored and run independently.

## Phase 1: Separate web, worker, and storage interfaces

1. Replace direct `Path` use in request handlers with `AudioStore` and `TranscriptStore` interfaces.
2. Move background polling out of the web lifespan into a dedicated worker command.
3. Define an idempotent job contract: `job_id`, `user_id`, `audio_key`, requested model, language, and checksum.
4. Add job states: `queued`, `processing`, `ready`, `failed`, and `deleted`.
5. Preserve the existing local filesystem implementation for development.

Exit criterion: web and worker processes can restart independently without losing or duplicating jobs.

## Phase 2: PostgreSQL and tenant ownership

1. Add `users`, `notes`, and `jobs` tables with foreign keys.
2. Add `user_id NOT NULL` to every user-owned row.
3. Add compound indexes such as `(user_id, created_at)` and `(user_id, status)`.
4. Replace SQLite connections with SQLAlchemy/Alembic or another migration-managed PostgreSQL layer.
5. Add repository methods that require `user_id`; do not expose unscoped list/get/update methods.
6. Test cross-user access attempts for every API route.

Exit criterion: automated tests prove User A cannot read, search, modify, download, or delete User B's data.

## Phase 3: Authentication and authorization

1. Configure Amazon Cognito or another OIDC provider.
2. Validate token issuer, audience, signature, expiry, and nonce/state where applicable.
3. Map the identity provider subject (`sub`) to the internal immutable user record.
4. Add secure session cookies or bearer-token handling appropriate to the client.
5. Require authentication for all application and API routes except health/readiness endpoints.
6. Add CSRF protection when cookie-based sessions are used.
7. Add administrative roles only when a real operational need exists.

Exit criterion: expired, forged, missing, and wrong-audience tokens are rejected consistently.

## Phase 4: S3 private object storage

1. Create separate development and production buckets with public access blocked.
2. Use keys such as `users/{user_id}/audio/{object_id}` and `users/{user_id}/transcripts/{object_id}`.
3. Enable server-side encryption, versioning, lifecycle rules, and access logging as required.
4. Limit IAM permissions to the exact bucket prefixes and operations each service needs.
5. Validate file type, maximum size, and checksum before accepting a job.
6. Configure retention and user-requested deletion for both current objects and versions.

Exit criterion: no application object is publicly accessible, and deleted-account data follows the documented retention policy.

## Phase 5: Queue and transcription workers

1. Publish jobs to SQS after a successful upload record is committed.
2. Configure a dead-letter queue and bounded retries.
3. Make processing idempotent using job IDs and object checksums.
4. Set visibility timeout longer than expected processing time and extend it for long recordings.
5. Start with CPU workers; introduce GPU workers only when measured queue latency justifies them.
6. Scale workers from queue depth and oldest-message age.
7. Store model version, duration, processing time, and failure reason without logging content.

Exit criterion: duplicate delivery, worker termination, and poison files do not corrupt data or expose another user's output.

## Phase 6: Network and runtime security

1. Terminate TLS at an Application Load Balancer or hardened reverse proxy.
2. Run containers in private subnets where practical; expose only the HTTPS entry point.
3. Use security groups with least-privilege ingress and egress.
4. Store secrets in AWS Secrets Manager or Systems Manager Parameter Store.
5. Run containers as non-root with read-only root filesystems and controlled writable mounts.
6. Add upload rate limits, request-size limits, security headers, and timeouts.
7. Scan container images and pin production image versions/digests.

Exit criterion: no database, worker, internal queue, or storage endpoint is publicly reachable.

## Phase 7: Observability, backup, and recovery

1. Emit structured logs containing request/job correlation IDs and user-safe identifiers.
2. Track request latency, error rate, queue depth, job duration, failure rate, storage growth, and authentication failures.
3. Alert on unavailable service, queue backlog, repeated worker failure, database pressure, and backup failure.
4. Enable PostgreSQL automated backups and test point-in-time restoration.
5. Define S3 versioning/lifecycle/backup requirements.
6. Write recovery-time and recovery-point objectives, then run a restoration exercise.

Exit criterion: an operator can detect a failure, identify the affected job, and restore service using documented steps.

## Phase 8: Deployment pipeline

1. Build and test immutable images in GitHub Actions.
2. Generate an SBOM and run dependency/container vulnerability scans.
3. Push versioned images to Amazon ECR.
4. Provision AWS resources with Terraform or AWS CDK.
5. Deploy first to a separate staging environment.
6. Run migrations as a controlled one-off step before application rollout.
7. Use rolling or blue/green deployment with health/readiness checks.
8. Retain the previous image and migration rollback procedure.

Exit criterion: the same reviewed artifact moves from CI to staging to production without manual source changes.

## Migration of existing local data

1. Create the owner's cloud user and record its immutable ID.
2. Stop local writes and take a verified backup.
3. Upload audio/transcripts to that user's S3 prefix.
4. Import metadata into PostgreSQL with the owner's `user_id`.
5. Compare record counts and checksums.
6. Test playback, transcript access, search, update, and deletion.
7. Keep the local backup read-only until the retention window expires.

## Minimum pre-release test matrix

- Cross-user API access and object-download denial
- SQL/search tenant scoping
- Upload type, size, and malformed-media handling
- Duplicate and retried SQS jobs
- Worker crash during transcription
- Token expiry and logout
- Password/account recovery through the identity provider
- User data export and deletion
- Backup restoration
- Load test using representative audio sizes
- Dependency and container vulnerability scans

## Cost controls

- Start with one small web service and scale transcription workers from queue depth.
- Do not keep GPU workers running continuously until utilization supports it.
- Apply S3 lifecycle rules to old audio where the retention policy permits.
- Set AWS Budgets and billing alarms before public access.
- Tag every resource by environment, service, and owner.
- Review NAT Gateway, public IPv4, log-ingestion, and data-transfer charges; these often surprise small deployments.

## Recommended AWS service mapping

| Responsibility | Initial AWS choice |
|---|---|
| DNS/TLS entry | Route 53 + ACM + Application Load Balancer, or a secured VM reverse proxy |
| Web/API containers | ECS on EC2/Fargate, or Docker Compose on a hardened EC2 VM initially |
| Identity | Amazon Cognito or compatible OIDC provider |
| Metadata | RDS PostgreSQL |
| Audio/transcripts | Private Amazon S3 bucket |
| Jobs | Amazon SQS + dead-letter queue |
| Images | Amazon ECR |
| Secrets | Secrets Manager or SSM Parameter Store |
| Logs/metrics/alarms | CloudWatch |
| Infrastructure | Terraform or AWS CDK |

The simplest safe first cloud milestone is a single-user private VM deployment. Multi-user access should not be enabled until tenant-scoping tests, authentication, object-storage isolation, backups, and deletion workflows pass.
