# Kubernetes Deployment Guide

Complete guide for deploying Google Calendar to Discord sync as a Kubernetes CronJob with secure secret management.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Kubernetes Cluster                    │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │  Namespace: gcal-to-discord             │    │
│  │                                          │    │
│  │  ┌──────────────────────────────────┐  │    │
│  │  │  CronJob (*/30 * * * *)          │  │    │
│  │  │  ├─> Pod (runs every 30 min)     │  │    │
│  │  │  │   └─> Container: sync          │  │    │
│  │  │  │       ├─ Env: ConfigMap        │  │    │
│  │  │  │       ├─ Env: Secrets          │  │    │
│  │  │  │       └─ Volumes: Credentials  │  │    │
│  │  └──────────────────────────────────┘  │    │
│  │                                          │    │
│  │  Resources:                              │    │
│  │  ├─ ConfigMap (non-sensitive config)    │    │
│  │  ├─ Secret (Discord bot token)          │    │
│  │  ├─ Secret (Google credentials)         │    │
│  │  └─ Secret (Google token - optional)    │    │
│  └────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster (1.25+ recommended for timezone support)
- `kubectl` configured to access your cluster
- Docker image built and pushed to registry
- Google OAuth2 credentials (`credentials.json`)
- Discord bot token
- Discord channel ID

## Quick Start

### 1. Build and Push Docker Image

```bash
# Build image
docker build -t your-registry/gcal-to-discord:latest .

# Push to registry
docker push your-registry/gcal-to-discord:latest
```

### 2. Create Namespace

```bash
kubectl apply -f namespace.yaml
```

### 3. Create Secrets

**Important**: Never commit secrets to version control!

#### Option A: Using kubectl (Recommended)

```bash
# Discord bot token
kubectl create secret generic gcal2discord-discord-bot-token \
  --from-literal=token=YOUR_DISCORD_BOT_TOKEN \
  -n gcal-to-discord

# Google credentials
kubectl create secret generic gcal2discord-google-credentials \
  --from-file=credentials.json=/path/to/your/credentials.json \
  -n gcal-to-discord

# Google token (optional - will be generated on first run if not provided)
kubectl create secret generic gcal2discord-google-token \
  --from-file=token.json=/path/to/your/token.json \
  -n gcal-to-discord
```

#### Option B: Using YAML (Edit secrets.yaml first)

```bash
# Edit secrets.yaml and add your base64-encoded credentials
kubectl apply -f secrets.yaml
```

### 4. Create ConfigMap

Edit `configmap.yaml` and set your Discord channel ID:

```yaml
data:
  DISCORD_CHANNEL_ID: "123456789012345678"  # Replace with your channel ID
```

Then apply:

```bash
kubectl apply -f configmap.yaml
```

### 5. Deploy CronJob

Edit `cronjob.yaml` and update the image:

```yaml
image: your-registry/gcal-to-discord:latest  # Replace with your image
```

Then apply:

```bash
kubectl apply -f cronjob.yaml
```

## Detailed Setup

### Secret Management

#### Discord Bot Token

Create the secret:

```bash
kubectl create secret generic gcal2discord-discord-bot-token \
  --from-literal=token=YOUR_DISCORD_BOT_TOKEN \
  -n gcal-to-discord
```

Verify:

```bash
kubectl get secret gcal2discord-discord-bot-token -n gcal-to-discord
kubectl describe secret gcal2discord-discord-bot-token -n gcal-to-discord
```

#### Google OAuth2 Credentials

**Step 1**: Download `credentials.json` from Google Cloud Console

**Step 2**: Create secret from file:

```bash
kubectl create secret generic gcal2discord-google-credentials \
  --from-file=credentials.json=/path/to/credentials.json \
  -n gcal-to-discord
```

**Step 3**: Verify:

```bash
kubectl get secret gcal2discord-google-credentials -n gcal-to-discord -o yaml
```

#### Google OAuth2 Token

**Option 1**: Generate token locally first (Recommended)

```bash
# Run locally to generate token.json
uv run gcal-to-discord --once

# Create secret from generated token
kubectl create secret generic gcal2discord-google-token \
  --from-file=token.json=./token.json \
  -n gcal-to-discord
```

**Option 2**: Let first CronJob run generate it

If you don't provide a token secret, the first run will need to perform OAuth flow. This requires:
- Interactive authentication (not possible in CronJob)
- **Solution**: Use a Job (one-time) for initial OAuth, then convert to CronJob

```bash
# Create initial job for OAuth (interactive)
kubectl apply -f oauth-init-job.yaml

# Monitor logs and complete OAuth in browser
kubectl logs -f job/gcal-oauth-init -n gcal-to-discord

# After token is generated, create CronJob
kubectl apply -f cronjob.yaml
```

### ConfigMap Configuration

Edit `configmap.yaml` to customize:

```yaml
data:
  # Required: Your Discord channel ID
  DISCORD_CHANNEL_ID: "123456789012345678"
  
  # Optional: Different calendar (default: primary)
  GOOGLE_CALENDAR_ID: "your-calendar-id@group.calendar.google.com"
  
  # Optional: Sync settings
  DAYS_AHEAD: "14"  # Sync events up to 14 days ahead
  
  # Optional: Logging level
  LOG_LEVEL: "DEBUG"  # For troubleshooting
```

Apply changes:

```bash
kubectl apply -f configmap.yaml

# Restart CronJob to pick up changes (delete active pods)
kubectl delete pods -l app=gcal-to-discord -n gcal-to-discord
```

### Schedule Configuration

Edit the schedule in `cronjob.yaml`:

```yaml
spec:
  # Every 30 minutes
  schedule: "*/30 * * * *"
  
  # Or use predefined schedules:
  # Every 15 minutes: "*/15 * * * *"
  # Every hour: "0 * * * *"
  # Twice daily (9 AM, 5 PM): "0 9,17 * * *"
  # Weekdays only at 9 AM: "0 9 * * 1-5"
```

With timezone support (K8s 1.25+):

```yaml
spec:
  schedule: "0 9 * * *"
  timeZone: "America/New_York"
```

## Verification

### Check CronJob Status

```bash
# View CronJob
kubectl get cronjob gcal-to-discord-sync -n gcal-to-discord

# View schedule and last run
kubectl describe cronjob gcal-to-discord-sync -n gcal-to-discord
```

### Check Job Runs

```bash
# List all jobs created by CronJob
kubectl get jobs -n gcal-to-discord

# View recent jobs
kubectl get jobs -n gcal-to-discord --sort-by=.metadata.creationTimestamp
```

### View Logs

```bash
# Get logs from latest job
kubectl logs -l app=gcal-to-discord -n gcal-to-discord --tail=100

# Get logs from specific job
kubectl logs job/gcal-to-discord-sync-28345678 -n gcal-to-discord

# Follow logs in real-time
kubectl logs -l app=gcal-to-discord -n gcal-to-discord -f

# View logs from all job runs
kubectl logs -l component=sync-job -n gcal-to-discord --prefix=true
```

### Check Secrets and ConfigMaps

```bash
# List secrets
kubectl get secrets -n gcal-to-discord

# View ConfigMap
kubectl get configmap gcal-to-discord-config -n gcal-to-discord -o yaml

# View secret details (be careful with sensitive data!)
kubectl describe secret gcal2discord-google-credentials -n gcal-to-discord
kubectl describe secret gcal2discord-google-token -n gcal-to-discord
```

## Manual Execution

Trigger a job manually without waiting for schedule:

```bash
# Create a job from the CronJob
kubectl create job --from=cronjob/gcal-to-discord-sync manual-sync-1 -n gcal-to-discord

# Monitor the job
kubectl get job manual-sync-1 -n gcal-to-discord -w

# View logs
kubectl logs job/manual-sync-1 -n gcal-to-discord -f
```

## Monitoring and Alerting

### Prometheus Metrics

Add Prometheus annotations to CronJob pods:

```yaml
template:
  metadata:
    annotations:
      prometheus.io/scrape: "true"
      prometheus.io/port: "8000"
      prometheus.io/path: "/metrics"
```

### Health Checks

Create a monitoring Job:

```bash
kubectl apply -f monitoring/health-check.yaml
```

Example health check script:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: gcal-sync-health-check
  namespace: gcal-to-discord
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: health-check
        image: bitnami/kubectl:latest
        command: ["/bin/sh", "-c"]
        args:
        - |
          # Check if last job succeeded
          LAST_JOB=$(kubectl get jobs -n gcal-to-discord \
            -l app=gcal-to-discord \
            --sort-by=.metadata.creationTimestamp \
            -o jsonpath='{.items[-1].metadata.name}')
          
          STATUS=$(kubectl get job $LAST_JOB -n gcal-to-discord \
            -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')
          
          if [ "$STATUS" != "True" ]; then
            echo "ERROR: Last job failed or is still running"
            exit 1
          fi
          
          echo "OK: Last job succeeded"
```

### Alerting

Set up alerts using Prometheus Alertmanager:

```yaml
groups:
- name: gcal-to-discord
  rules:
  - alert: CronJobFailed
    expr: kube_job_failed{job_name=~"gcal-to-discord-sync.*"} > 0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "GCal sync CronJob failed"
      description: "Job {{ $labels.job_name }} has failed"
  
  - alert: CronJobNotRunning
    expr: time() - kube_cronjob_status_last_schedule_time{cronjob="gcal-to-discord-sync"} > 3600
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "GCal sync CronJob hasn't run"
      description: "CronJob hasn't run in over 1 hour"
```

## Troubleshooting

### Pod Crashes Immediately

Check events and logs:

```bash
kubectl describe cronjob gcal-to-discord-sync -n gcal-to-discord
kubectl get events -n gcal-to-discord --sort-by='.lastTimestamp'
kubectl logs -l app=gcal-to-discord -n gcal-to-discord --previous
```

Common issues:
- Image pull errors: Check `imagePullSecrets` and registry access
- Secret not found: Verify secrets exist and names match
- Permission denied: Check `securityContext` and file permissions

### Authentication Failures

```bash
# Check if secrets are properly mounted
kubectl exec -it <pod-name> -n gcal-to-discord -- ls -la /app/secrets/google/

# Verify secret contents (be careful, this exposes secrets!)
kubectl get secret gcal2discord-google-credentials -n gcal-to-discord -o jsonpath='{.data.credentials\.json}' | base64 -d | jq .

# Check Discord token
kubectl get secret gcal2discord-discord-bot-token -n gcal-to-discord -o jsonpath='{.data.token}' | base64 -d
```

### OAuth Token Issues

If token.json is invalid or expired:

```bash
# Delete existing token secret
kubectl delete secret gcal2discord-google-token -n gcal-to-discord

# Run OAuth flow locally to generate new token
uv run gcal-to-discord --once

# Create new secret with refreshed token
kubectl create secret generic gcal2discord-google-token \
  --from-file=token.json=./token.json \
  -n gcal-to-discord

# Delete pod to force recreation with new secret
kubectl delete pods -l app=gcal-to-discord -n gcal-to-discord
```

### Token Refresh Issues

The application uses secrets for the OAuth token. If you need to refresh it:

```bash
# Delete existing token secret
kubectl delete secret gcal2discord-google-token -n gcal-to-discord

# Run OAuth flow locally to generate new token
cd /path/to/gcal-to-discord
uv run gcal-to-discord --once

# Create new secret with refreshed token
kubectl create secret generic gcal2discord-google-token \
  --from-file=token.json=./token.json \
  -n gcal-to-discord

# Next CronJob run will use the refreshed token
```

### Debug with Interactive Pod

Run a debug pod with same configuration:

```bash
kubectl run -it --rm debug \
  --image=your-registry/gcal-to-discord:latest \
  --restart=Never \
  --env=DISCORD_BOT_TOKEN=$(kubectl get secret gcal2discord-discord-bot-token -n gcal-to-discord -o jsonpath='{.data.token}' | base64 -d) \
  -n gcal-to-discord \
  -- /bin/bash
```

## Security Best Practices

### 1. Use Separate Service Account

Create a service account with minimal permissions:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: gcal-to-discord
  namespace: gcal-to-discord
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: gcal-to-discord
  namespace: gcal-to-discord
rules:
- apiGroups: [""]
  resources: ["secrets", "configmaps"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: gcal-to-discord
  namespace: gcal-to-discord
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: gcal-to-discord
subjects:
- kind: ServiceAccount
  name: gcal-to-discord
  namespace: gcal-to-discord
```

### 2. Encrypt Secrets at Rest

Enable encryption at rest for secrets:

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
    - secrets
    providers:
    - aescbc:
        keys:
        - name: key1
          secret: <base64-encoded-32-byte-key>
    - identity: {}
```

### 3. Use External Secret Management

Integrate with external secret managers:

**AWS Secrets Manager**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
  namespace: gcal-to-discord
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: gcal2discord-discord-bot-token
  namespace: gcal-to-discord
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets
    kind: SecretStore
  target:
    name: gcal2discord-discord-bot-token
  data:
  - secretKey: token
    remoteRef:
      key: gcal-to-discord/gcal2discord-discord-bot-token
```

### 4. Network Policies

Restrict network access:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gcal-to-discord-netpol
  namespace: gcal-to-discord
spec:
  podSelector:
    matchLabels:
      app: gcal-to-discord
  policyTypes:
  - Egress
  egress:
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
  # Allow HTTPS to external services
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

### 5. Pod Security Standards

Apply Pod Security Standards:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: gcal-to-discord
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

## Scaling and Performance

### Resource Tuning

Monitor resource usage:

```bash
kubectl top pods -n gcal-to-discord
```

Adjust resources based on usage:

```yaml
resources:
  requests:
    memory: "64Mi"   # Minimum needed
    cpu: "50m"
  limits:
    memory: "512Mi"  # Maximum allowed
    cpu: "1000m"
```

### Concurrent Execution

Control concurrency:

```yaml
spec:
  # Forbid: Never run multiple jobs at once
  concurrencyPolicy: Forbid
  
  # Allow: Can run multiple jobs concurrently
  # concurrencyPolicy: Allow
  
  # Replace: Kill old job and start new one
  # concurrencyPolicy: Replace
```

## Cleanup

Remove all resources:

```bash
# Delete CronJob (stops future executions)
kubectl delete cronjob gcal-to-discord-sync -n gcal-to-discord

# Delete active jobs and pods
kubectl delete jobs -l app=gcal-to-discord -n gcal-to-discord
kubectl delete pods -l app=gcal-to-discord -n gcal-to-discord

# Delete configuration
kubectl delete configmap gcal-to-discord-config -n gcal-to-discord

# Delete secrets (be careful!)
kubectl delete secret gcal2discord-discord-bot-token -n gcal-to-discord
kubectl delete secret gcal2discord-google-credentials -n gcal-to-discord
kubectl delete secret gcal2discord-google-token -n gcal-to-discord

# Delete namespace (removes everything)
kubectl delete namespace gcal-to-discord
```

## Migration from Other Platforms

### From Cron/Systemd to Kubernetes

1. Build Docker image with all dependencies
2. Test image locally: `docker run your-image --once`
3. Push to registry accessible by cluster
4. Create secrets from existing credentials
5. Deploy CronJob with same schedule
6. Verify first run succeeds
7. Disable old cron/systemd job

### From Continuous Mode to CronJob

Update deployment:

```bash
# If running as Deployment, delete it
kubectl delete deployment gcal-to-discord -n gcal-to-discord

# Deploy as CronJob instead
kubectl apply -f cronjob.yaml
```

## Cost Optimization

### Use Spot/Preemptible Nodes

Add node selector for spot instances:

```yaml
spec:
  template:
    spec:
      nodeSelector:
        cloud.google.com/gke-preemptible: "true"
        # Or for AWS:
        # node.kubernetes.io/lifecycle: spot
      tolerations:
      - key: cloud.google.com/gke-preemptible
        operator: Equal
        value: "true"
        effect: NoSchedule
```

### Reduce Resource Usage

- Use minimal base image (distroless, alpine)
- Set appropriate resource limits
- Use longer sync intervals if acceptable
- Enable cluster autoscaling

## References

- [Kubernetes CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [External Secrets Operator](https://external-secrets.io/)
